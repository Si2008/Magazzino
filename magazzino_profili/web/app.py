"""Avvio del server web di scansione da telefono (processo separato).

AVVIO
-----
    python -m magazzino_profili.web.app

Il server legge da ``config.toml``:
- la sezione ``[database]`` (stesso PostgreSQL dell'app desktop);
- la sezione ``[web]`` per host, porta, certificato, chiave privata,
  durata del token e segrete di firma.

HTTPS OBBLIGATORIO
-------------------
Il server NON accetta connessioni HTTP in chiaro: uvicorn è avviato con
``ssl_certfile``/``ssl_keyfile``, quindi ogni connessione è cifrata.
Questo è anche un requisito tecnico della pagina di scansione: la
fotocamera del telefono (``getUserMedia``) funziona solo in un secure
context (HTTPS).

ESPOSIZIONE SU INTERNET (fuori dal perimetro di questo modulo)
---------------------------------------------------------------
Il telefono si collega SEMPRE da remoto (rete dati mobile): il PC che
gira questo server deve essere raggiungibile da internet. Il modo in
cui accade — port forwarding sul router, VPN o un servizio di tunnel
(es. Cloudflare Tunnel, Tailscale, ngrok) — è una configurazione di
RETE esterna al codice e NON è compito di questo modulo. Questo file
si limita a ascoltare su ``host:porta`` con TLS.
"""

from __future__ import annotations

import secrets
import tomllib
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ..db import crea_engine, crea_session_factory, leggi_config
from .routes_barcode import crea_router

# Percorsi delle risorse web, relativi a questo pacchetto.
_RADICE_PACCHETTO = Path(__file__).resolve().parent
_TEMPLATE_SCANSIONE = _RADICE_PACCHETTO / "templates" / "scansione.html"
_CARTELLA_STATIC = _RADICE_PACCHETTO / "static"

# Valori di default per la sezione [web] (i certificati NON hanno default:
# senza certificato il server non deve partire in HTTP chiaro).
_DEFAULT_WEB: dict[str, Any] = {
    "host": "0.0.0.0",  # tutte le interfacce: il telefono arriva da fuori
    "porta": 8443,
    "durata_token_secondi": 3600,
}


def _candidati_config() -> list[Path]:
    """Stesse regole di ricerca di ``db/config.py``: cwd poi radice progetto."""
    radice_progetto = Path(__file__).resolve().parents[2]
    return [Path.cwd() / "config.toml", radice_progetto / "config.toml"]


def leggi_sezione_web(percorso: str | Path | None = None) -> dict[str, Any]:
    """Legge la sezione ``[web]`` di ``config.toml`` (con i default).

    Solleva ``ValueError`` con messaggio in italiano se il file non
    esiste o la sezione è assente (i certificati possono però mancare
    solo a valle: ``main`` li controlla prima dell'avvio).
    """
    candidati = [Path(percorso)] if percorso is not None else _candidati_config()
    file = next((p for p in candidati if p.is_file()), None)
    if file is None:
        cercati = ", ".join(str(p) for p in candidati)
        raise ValueError(f"File di configurazione non trovato. Percorsi cercati: {cercati}")

    with open(file, "rb") as fonte:
        dati = tomllib.load(fonte)
    sezione = dati.get("web", {})

    configurazione = dict(_DEFAULT_WEB)
    configurazione.update(
        {
            "host": sezione.get("host", _DEFAULT_WEB["host"]),
            "porta": int(sezione.get("porta", _DEFAULT_WEB["porta"])),
            "certificato_pem": sezione.get("certificato_pem"),
            "chiave_privata": sezione.get("chiave_privata"),
            "durata_token_secondi": int(
                sezione.get("durata_token_secondi", _DEFAULT_WEB["durata_token_secondi"])
            ),
            "segrete_token": sezione.get("segrete_token"),
            "url_pubblico": sezione.get("url_pubblico"),  # informativa: QR "Collega telefono"
        }
    )
    return configurazione


def _messaggio_422(exc: RequestValidationError) -> str:
    """Traduce i principali errori di validazione in italiano."""
    problemi: list[str] = []
    for errore in exc.errors():
        campo = ".".join(str(p) for p in errore.get("loc", ()) if str(p) not in ("body",))
        tipo = str(errore.get("type", ""))
        if "quantita" in campo:
            if "parsing" in tipo:
                problemi.append("la quantità deve essere un numero intero")
            elif "greater" in tipo:
                problemi.append("la quantità deve essere maggiore di zero")
            else:
                problemi.append("la quantità deve essere un numero intero positivo")
        elif "barcode" in campo:
            problemi.append("il barcode non può essere vuoto")
        else:
            problemi.append(f"il campo '{campo}' non è valido")
    unici = list(dict.fromkeys(problemi))  # dedup preservando l'ordine
    if not unici:
        return "Dati non validi: controllare i campi inviati."
    return "Dati non validi: " + "; ".join(unici) + "."


def crea_app(
    session_factory: Any | None = None,
    durata_token_secondi: int = 3600,
    segrete_token: str | None = None,
) -> FastAPI:
    """Costruisce l'applicazione FastAPI (usa anche nei test).

    Se ``session_factory`` non è fornita, viene creata da ``config.toml``
    (stesso PostgreSQL dell'app desktop). ``segrete_token`` deve essere
    una stringa lunga e casuale; se assente, ne viene generata una
    valida solo per la durata di questo avvio (avviso a video).
    """
    if session_factory is None:
        engine = crea_engine(config=leggi_config())
        session_factory = crea_session_factory(engine)

    if segrete_token is None:
        segrete_token = secrets.token_hex(32)
        print(
            "AVVISO: [web] segrete_token non definito in config.toml: "
            "i token saranno validi solo per la durata di questo avvio."
        )
    segrete = segrete_token.encode("utf-8")

    app = FastAPI(
        title="Magazzino Profili — scansione da telefono",
        version="1.0",
        # Documentazione API automatici NON esposti: non è un servizio
        # pubblico anonimo, deve restare una superficie minima.
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.exception_handler(RequestValidationError)
    async def gestore_validazione(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Errori 422 con messaggio in italiano (invece di quello predefinito)."""
        return JSONResponse(status_code=422, content={"detail": _messaggio_422(exc)})

    app.include_router(
        crea_router(session_factory, segrete, durata_token_secondi)
    )

    @app.get("/", include_in_schema=False)
    def pagina_scansione() -> FileResponse:
        """Pagina mobile di scansione (HTML + JS statico)."""
        return FileResponse(_TEMPLATE_SCANSIONE, media_type="text/html")

    app.mount("/static", StaticFiles(directory=_CARTELLA_STATIC), name="static")
    return app


def main() -> int:
    """Punto d'ingresso: ``python -m magazzino_profili.web.app``."""
    try:
        web = leggi_sezione_web()
    except ValueError as errore:
        print(f"ERRORE: {errore}")
        return 1

    # HTTPS obbligatorio: senza i due file il server NON parte in chiaro.
    certificato = Path(web["certificato_pem"]) if web["certificato_pem"] else None
    chiave = Path(web["chiave_privata"]) if web["chiave_privata"] else None
    if certificato is None or chiave is None:
        print(
            "ERRORE: HTTPS obbligatorio. Definire in config.toml la sezione [web] "
            "con le chiavi 'certificato_pem' e 'chiave_privata' (percorso dei file)."
        )
        return 1
    if not Path(certificato).is_file() or not Path(chiave).is_file():
        print(f"ERRORE: certificati non trovati: '{certificato}' / '{chiave}'")
        return 1

    app = crea_app(
        durata_token_secondi=web["durata_token_secondi"],
        segrete_token=web["segrete_token"],
    )
    print(
        f"Server web Magazzino Profili: https://{web['host']}:{web['porta']}/ "
        "(accesso solo remoto, HTTPS)"
    )
    try:
        uvicorn.run(
            app,
            host=web["host"],
            port=web["porta"],
            ssl_certfile=str(certificato),
            ssl_keyfile=str(chiave),
        )
    except KeyboardInterrupt:
        print("Server web arrestato.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
