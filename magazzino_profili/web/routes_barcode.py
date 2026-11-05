"""API telefono ad accesso libero. Creazione di barcode unitari, consultazione, carico, scarico e consegna al PC con conferma."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StrictInt, field_validator

from sqlalchemy import select

from ..domain import Pezzo, ScansioneTelefono
from ..domain.pezzo import QuantitaInsufficienteError
from ..services import consultazione
from ..services.carico import carica
from ..services.eccezioni import PezzoNonTrovatoError, ProfiloNonTrovatoError
from ..services.scarico import scarica
from ..services import telefono as servizio_telefono
from .accesso_libero import Operatore as UtenteAutenticato, operatore_corrente
from .sicurezza_web import ProtezioneLogin


class RichiestaMovimento(BaseModel):
    """Dati di una richiesta di carico o scarico da telefono."""

    richiesta_id: str | None = Field(default=None, min_length=1, max_length=64)
    barcode: str = Field(min_length=1, max_length=255, description="Barcode del pezzo")
    quantita: StrictInt = Field(gt=0, description="Quantità, numero intero positivo")
    causale: str | None = Field(
        default=None,
        max_length=512,
        description="Causale (facoltativa) per la traccia contabile",
    )

    @field_validator("barcode")
    @classmethod
    def barcode_valido(cls, valore):
        return _barcode_pulito(valore)


class RichiestaScansione(BaseModel):
    """Barcode letto dal telefono in modalità "Lettore" (non modifica il magazzino)."""

    richiesta_id: str | None = Field(default=None, min_length=1, max_length=64)
    destinatario: str | None = Field(default=None, pattern="^[a-f0-9]{32}$")
    barcode: str = Field(min_length=1, max_length=255, description="Barcode letto")

    @field_validator("barcode")
    @classmethod
    def barcode_valido(cls, valore):
        return _barcode_pulito(valore)


def _barcode_pulito(valore):
    if any(ord(c) < 32 or ord(c) == 127 for c in valore):
        raise ValueError("Il barcode contiene caratteri di controllo non ammessi")
    valore = valore.strip().upper()
    if not valore:
        raise ValueError("Il barcode non può essere vuoto")
    return valore


class NuovoProfilo(BaseModel):
    descrizione: str = Field(min_length=1, max_length=2000)
    peso_kg_per_metro: float = Field(ge=0.0001, le=999999.9999, allow_inf_nan=False)
    lunghezza_standard_mm: StrictInt = Field(gt=0, le=2147483647)


class RichiestaNuovoPezzo(BaseModel):
    richiesta_id: str = Field(min_length=1, max_length=64)
    codice_profilo: str = Field(min_length=1, max_length=64)
    colore: str = Field(min_length=1, max_length=64)
    lunghezza_mm: StrictInt = Field(gt=0, le=2147483647)
    quantita: StrictInt = Field(gt=0, le=1000)
    numero_vassoio: str = Field(min_length=1, max_length=128)
    ubicazione: str | None = Field(default=None, max_length=128)
    scorta_minima: StrictInt | None = Field(default=None, ge=0, le=2147483647)
    causale: str = Field(min_length=1, max_length=512)
    nuovo_profilo: NuovoProfilo | None = None


def _dettagli_pezzo(pezzo: Pezzo, esito: str) -> dict:
    """Corpo di risposta di successo: esito + dettagli del pezzo.

    Da leggere con la sessione ancora aperta (relazioni caricate).
    """
    return {
        "dettaglio": esito,
        "barcode": pezzo.barcode,
        "codice_profilo": pezzo.profilo.codice,
        "descrizione": pezzo.profilo.descrizione,
        "colore": pezzo.colore.nome_visualizzato,
        "lunghezza_mm": pezzo.lunghezza_mm,
        "quantita_giacenza": pezzo.quantita,
        "numero_vassoio": pezzo.numero_vassoio,
        "stato": pezzo.stato,
        "unitario": pezzo.unitario,
        "ubicazione": pezzo.ubicazione,
        "data_ultimo_cambio_stato": pezzo.data_ultimo_cambio_stato.isoformat() if pezzo.data_ultimo_cambio_stato else None,
    }


def crea_router(
    session_factory,
    segrete_token: bytes,
    durata_token_secondi: int,
    protezione_login: ProtezioneLogin | None = None,
) -> APIRouter:
    """Costruisce il router ``/api`` con i servizi iniettati.

    ``session_factory`` è il factory di sessioni SQLAlchemy sullo stesso
    PostgreSQL dell'app desktop (o un altro engine, nei test).
    """

    router = APIRouter(prefix="/api")
    utente_autenticato = operatore_corrente

    def mutazione(payload, utente, nome, azione):
        from ..services.idempotenza import esegui
        dati = payload.model_dump(exclude={"richiesta_id"})
        try:
            return esegui(session_factory, utente.username, payload.richiesta_id, nome, dati, azione)
        except (PezzoNonTrovatoError, ProfiloNonTrovatoError) as errore:
            raise HTTPException(status_code=404, detail=str(errore)) from errore
        except QuantitaInsufficienteError as errore:
            raise HTTPException(status_code=409, detail=str(errore)) from errore
        except ValueError as errore:
            raise HTTPException(status_code=409, detail=str(errore)) from errore

    @router.get("/profili")
    def elenco_profili(cerca: str = "", utente: UtenteAutenticato = Depends(utente_autenticato)):
        from ..domain import Profilo
        from ..db.normalizzazione import normalizza_codice
        from ..services.immagini import immagine_del_profilo
        from urllib.parse import quote
        with session_factory() as session:
            righe = session.scalars(select(Profilo).where(
                Profilo.codice.startswith(normalizza_codice(cerca[:64]), autoescape=True)
            ).order_by(Profilo.codice).limit(30))
            return [{"codice": p.codice, "descrizione": p.descrizione,
                     "peso_kg_per_metro": float(p.peso_kg_per_metro),
                     "lunghezza_standard_mm": p.lunghezza_standard_mm,
                     "url_immagine": "/api/profili/" + quote(p.codice, safe="") + "/sezione" if immagine_del_profilo(p) else None} for p in righe]

    @router.get("/profili/{codice}/sezione")
    def sezione_profilo(codice: str):
        from fastapi.responses import FileResponse
        from ..domain import Profilo
        from ..db.normalizzazione import normalizza_codice
        from ..services.immagini import immagine_del_profilo
        with session_factory() as session:
            p = session.scalar(select(Profilo).where(Profilo.codice == normalizza_codice(codice)))
            percorso = immagine_del_profilo(p) if p is not None else None
            if percorso is None:
                raise HTTPException(status_code=404, detail="Sezione del profilo non disponibile")
            return FileResponse(percorso, media_type="image/png")

    @router.post("/pezzi")
    def nuovo_pezzo(payload: RichiestaNuovoPezzo, utente: UtenteAutenticato = Depends(utente_autenticato)):
        """Creazione esplicita; una combinazione esistente non viene ricaricata."""
        from ..domain import Profilo, Colore
        from ..db.normalizzazione import normalizza_codice, normalizza_colore, genera_barcode
        from ..services.carico import _carica_in_transazione
        from ..barcode.generazione import valida_per_barcode
        codice = normalizza_codice(payload.codice_profilo)
        colore = normalizza_colore(payload.colore)
        if not codice or not colore or not payload.numero_vassoio.strip() or not payload.causale.strip():
            raise HTTPException(status_code=422, detail="Profilo, colore, vassoio e causale sono obbligatori")
        def azione(session):
            # Lo stesso lock è condiviso da tutte le creazioni remote, anche con
            # chiavi idempotenza differenti. Il vincolo DB resta l'ultima difesa.
            if session.get_bind().dialect.name == "postgresql":
                from sqlalchemy import text
                session.execute(text("SELECT pg_advisory_xact_lock(727003)"))
            profilo = session.scalar(select(Profilo).where(Profilo.codice == codice))
            if profilo is None:
                if not payload.nuovo_profilo:
                    raise ProfiloNonTrovatoError(codice)
                dati = payload.nuovo_profilo
                if not dati.descrizione.strip():
                    raise ValueError("Descrizione obbligatoria")
                profilo = Profilo(codice=codice, descrizione=dati.descrizione.strip(),
                    peso_kg_per_metro=dati.peso_kg_per_metro, lunghezza_standard_mm=dati.lunghezza_standard_mm)
                session.add(profilo)
                session.flush()
                from ..services.catalogo_immagini import CatalogoImmagini
                from ..services.anagrafica import _associa_in_transazione
                immagine = CatalogoImmagini().trova(codice)
                if immagine:
                    _associa_in_transazione(session, profilo.id, immagine, None)
            elif payload.nuovo_profilo:
                raise ValueError("Profilo già esistente: selezionalo senza creare una nuova anagrafica")
            from ..services.pezzi_unitari import _crea_in_transazione
            pezzi = _crea_in_transazione(session, codice, colore, payload.lunghezza_mm,
                payload.quantita, utente.username, payload.causale.strip(), payload.ubicazione,
                numero_vassoio=payload.numero_vassoio.strip(), scorta_minima=payload.scorta_minima)
            dettagli = [_dettagli_pezzo(p, "Barcode del singolo pezzo creato.") for p in pezzi]
            return {"dettaglio": f"Creati {len(pezzi)} pezzi, ciascuno con barcode univoco.", "pezzi": dettagli}
        return mutazione(payload, utente, "nuovo_pezzo", azione)

    @router.get("/barcode/{barcode}/immagine")
    def immagine_barcode(barcode: str, utente: UtenteAutenticato = Depends(utente_autenticato)):
        from fastapi.responses import Response
        from ..barcode.generazione import valida_per_barcode
        from barcode import Code128
        from barcode.writer import ImageWriter
        from io import BytesIO
        # Ogni ruolo ammesso può leggere il dettaglio del singolo barcode.
        with session_factory() as session:
            pezzo = consultazione.pezzo_per_barcode(session, barcode.strip().upper())
            if pezzo is None:
                raise HTTPException(status_code=404, detail="Barcode non trovato")
            if not valida_per_barcode(pezzo.barcode):
                raise HTTPException(status_code=422, detail="Barcode storico non rappresentabile in Code 128")
            dati = BytesIO()
            Code128(pezzo.barcode, writer=ImageWriter()).write(dati)
        return Response(dati.getvalue(), media_type="image/png",
                        headers={"Cache-Control": "no-store"})

    @router.post("/carico")
    def api_carico(payload: RichiestaMovimento, utente: UtenteAutenticato = Depends(utente_autenticato)):
        from ..services.carico import _carica_in_transazione
        def azione(session):
            trovato = session.scalar(select(Pezzo).where(Pezzo.barcode == payload.barcode.strip().upper(),
                                  Pezzo.eliminato_il.is_(None)).with_for_update())
            if trovato is None:
                raise PezzoNonTrovatoError("Pezzo non trovato: creare prima il pezzo dal programma desktop")
            from ..domain import registra_movimento, TipoMovimento
            registra_movimento(session, trovato, TipoMovimento.CARICO, payload.quantita,
                                payload.causale or "Rientro da telefono", utente.username)
            pezzo = trovato
            return _dettagli_pezzo(pezzo, "Carico registrato.")
        return mutazione(payload, utente, "carico", azione)

    @router.post("/scarico")
    def api_scarico(payload: RichiestaMovimento, utente: UtenteAutenticato = Depends(utente_autenticato)):
        from ..services.scarico import _scarica_in_transazione
        def azione(session):
            movimento = _scarica_in_transazione(session, payload.barcode.strip().upper(), payload.quantita,
                          utente.username, payload.causale or "Scarico da telefono")
            return _dettagli_pezzo(movimento.pezzo, "Scarico registrato.")
        return mutazione(payload, utente, "scarico", azione)

    @router.get("/pezzi/{barcode}")
    def api_dettaglio_pezzo(
        barcode: str,
        utente: UtenteAutenticato = Depends(utente_autenticato),
    ) -> dict:
        """Dettaglio di sola lettura di un pezzo: nessun movimento, nessuna modifica.

        Barcode vuoto o troppo lungo → 422; inesistente o eliminato → 404.
        Ruoli senza il permesso ``inventario`` → 403.
        """
        barcode_n = barcode.strip().upper()
        if not barcode_n:
            raise HTTPException(status_code=422, detail="Dati non validi: il barcode non può essere vuoto.")
        if len(barcode_n) > 255:
            raise HTTPException(
                status_code=422, detail="Dati non validi: il barcode non può superare 255 caratteri."
            )
        with session_factory() as session:
            pezzo = consultazione.pezzo_per_barcode(session, barcode_n)
            if pezzo is None:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        f"Pezzo non trovato: il barcode '{barcode_n}' non corrisponde a "
                        "nessun pezzo in magazzino."
                    ),
                )
            return _dettagli_pezzo(pezzo, "Dettaglio disponibile.")

    @router.post("/scansione")
    def api_scansione(payload: RichiestaScansione, utente: UtenteAutenticato = Depends(utente_autenticato)):
        if not payload.barcode.strip():
            raise HTTPException(status_code=422, detail="Il barcode non può essere vuoto")
        def azione(session):
            riga = ScansioneTelefono(barcode=payload.barcode.strip().upper(), utente=utente.username,
                                    destinatario=payload.destinatario)
            session.add(riga)
            session.flush()
            return {"dettaglio": "Scansione accodata; attendo conferma dal PC.", "id": riga.id,
                    "barcode": riga.barcode, "esito": "in_attesa"}
        return mutazione(payload, utente, "scansione", azione)

    @router.get("/scansioni/{id_}")
    def esito_scansione(id_: int, utente: UtenteAutenticato = Depends(utente_autenticato)):
        with session_factory() as session:
            riga = session.get(ScansioneTelefono, id_)
            if riga is None or riga.utente != utente.username:
                raise HTTPException(status_code=404, detail="Scansione non disponibile")
            esito, dettaglio = riga.esito or "in_attesa", riga.dettaglio or "In attesa della conferma dal PC"
            from datetime import datetime, timedelta, timezone
            from ..services.telefono import _aware, ETA_MASSIMA_SCANSIONE_S
            adesso = datetime.now(timezone.utc)
            if not riga.letta and riga.presa_il is None and _aware(riga.creata_il) < adesso - timedelta(seconds=ETA_MASSIMA_SCANSIONE_S):
                esito, dettaglio = "scaduta", "Il PC non ha ricevuto la scansione: apri il nuovo QR dal programma e riprova"
            elif not riga.letta and riga.presa_il is not None and _aware(riga.presa_il) < adesso - timedelta(minutes=5):
                esito, dettaglio = "incerto", "Consegna interrotta: controlla lo stato del pezzo prima di ripetere"
            return {"id": riga.id, "barcode": riga.barcode, "esito": esito, "dettaglio": dettaglio}

    @router.post("/telefono/ping")
    def api_ping(destinatario: str | None = None, utente: UtenteAutenticato = Depends(utente_autenticato)):
        if destinatario is not None:
            import re
            if not re.fullmatch(r"[a-f0-9]{32}", destinatario):
                raise HTTPException(status_code=422, detail="Destinatario non valido")
        with session_factory() as session:
            servizio_telefono.registra_ping(session, destinatario=destinatario)
        with session_factory() as session:
            presente = servizio_telefono.pc_collegato(session, destinatario)
        return {"dettaglio": "ok", "pc_collegato": presente}

    return router
