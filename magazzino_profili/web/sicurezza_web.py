"""Protezioni del modulo web: segrete dei token, limite ai tentativi di login,
intestazioni di sicurezza e limite alla dimensione delle richieste.

Tutto in memoria e nella libreria standard: nessuna dipendenza nuova.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict, deque
from typing import Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

SEGRETE_MIN_CARATTERI = 32
SEGRETE_MIN_CARATTERI_DISTINTI = 10
# Valori di esempio pubblicati in config.example.toml: chi li usa ha una segrete NOTA.
SEGNAPOSTO_NOTI = frozenset({"SEGRETE_LUNGA_E_CASUALE_MINIMO_32_CARATTERI"})
MAX_CORPO_BYTE = 64 * 1024  # le richieste JSON dell'API sono di poche centinaia di byte


def valida_segrete_token(segrete: object) -> str:
    """Restituisce la segrete se è accettabile, altrimenti ``ValueError`` (in italiano)."""
    if not isinstance(segrete, str) or len(segrete) < SEGRETE_MIN_CARATTERI:
        raise ValueError(
            f"[web] segrete_token deve avere almeno {SEGRETE_MIN_CARATTERI} caratteri. "
            'Generarne una con: python -c "import secrets; print(secrets.token_hex(32))"'
        )
    if segrete in SEGNAPOSTO_NOTI:
        raise ValueError(
            "[web] segrete_token è ancora il valore di esempio di config.example.toml: "
            "chiunque potrebbe falsificare i token. Sostituirlo con una segrete casuale."
        )
    if len(set(segrete)) < SEGRETE_MIN_CARATTERI_DISTINTI:
        raise ValueError("[web] segrete_token è troppo ripetitiva: usare una segrete casuale.")
    return segrete


class TentativiEccessiviError(Exception):
    def __init__(self, attesa_secondi: int) -> None:
        self.attesa_secondi = attesa_secondi
        super().__init__(f"Troppi tentativi: riprovare tra {attesa_secondi} secondi.")


class LimitatoreTentativi:
    """Blocca una chiave dopo ``max_tentativi`` fallimenti entro ``finestra_secondi``.

    Thread-safe; la memoria è limitata da ``max_chiavi`` (le più vecchie vengono scartate).
    """

    def __init__(
        self,
        max_tentativi: int = 5,
        finestra_secondi: int = 300,
        blocco_secondi: int = 300,
        *,
        adesso: Callable[[], float] = time.monotonic,
        max_chiavi: int = 10_000,
    ) -> None:
        if min(max_tentativi, finestra_secondi, blocco_secondi, max_chiavi) < 1:
            raise ValueError("I parametri del limitatore devono essere interi positivi.")
        self._max, self._finestra, self._blocco = max_tentativi, finestra_secondi, blocco_secondi
        self._adesso, self._max_chiavi = adesso, max_chiavi
        self._fallimenti: OrderedDict[object, deque[float]] = OrderedDict()
        self._bloccati: dict[object, float] = {}
        self._lock = threading.Lock()

    def controlla(self, chiave: object) -> None:
        with self._lock:
            ora = self._adesso()
            fino = self._bloccati.get(chiave)
            if fino is not None:
                if ora < fino:
                    raise TentativiEccessiviError(max(1, int(fino - ora) + 1))
                del self._bloccati[chiave]
                self._fallimenti.pop(chiave, None)

    def registra_fallimento(self, chiave: object) -> None:
        with self._lock:
            ora = self._adesso()
            coda = self._fallimenti.setdefault(chiave, deque())
            self._fallimenti.move_to_end(chiave)
            coda.append(ora)
            while coda and ora - coda[0] > self._finestra:
                coda.popleft()
            if len(coda) >= self._max:
                self._bloccati[chiave] = ora + self._blocco
            while len(self._fallimenti) > self._max_chiavi:
                vecchia, _ = self._fallimenti.popitem(last=False)
                self._bloccati.pop(vecchia, None)

    def azzera(self, chiave: object) -> None:
        with self._lock:
            self._fallimenti.pop(chiave, None)
            self._bloccati.pop(chiave, None)


class ProtezioneLogin:
    """Due limiti: per coppia (indirizzo, utente) e per solo indirizzo.

    Il secondo impedisce di aggirare il primo cambiando nome utente a ogni tentativo.
    """

    def __init__(
        self,
        per_utente: LimitatoreTentativi | None = None,
        per_indirizzo: LimitatoreTentativi | None = None,
    ) -> None:
        self._per_utente = per_utente or LimitatoreTentativi(5, 300, 300)
        self._per_indirizzo = per_indirizzo or LimitatoreTentativi(20, 300, 300)

    @staticmethod
    def _chiave(indirizzo: str, utente: str) -> tuple[str, str]:
        return indirizzo, utente.strip().lower()[:64]

    def controlla(self, indirizzo: str, utente: str) -> None:
        """Solleva HTTP 429 (con ``Retry-After``) se l'accesso è bloccato."""
        try:
            self._per_indirizzo.controlla(indirizzo)
            self._per_utente.controlla(self._chiave(indirizzo, utente))
        except TentativiEccessiviError as errore:
            raise HTTPException(
                status_code=429,
                detail=f"Troppi tentativi di accesso. Riprovare tra {errore.attesa_secondi} secondi.",
                headers={"Retry-After": str(errore.attesa_secondi)},
            ) from None

    def fallimento(self, indirizzo: str, utente: str) -> None:
        self._per_indirizzo.registra_fallimento(indirizzo)
        self._per_utente.registra_fallimento(self._chiave(indirizzo, utente))

    def successo(self, indirizzo: str, utente: str) -> None:
        self._per_utente.azzera(self._chiave(indirizzo, utente))


_CSP = (
    "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
    "connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; "
    "frame-ancestors 'none'"
)
INTESTAZIONI_SICUREZZA = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(self), microphone=(), geolocation=()",
    "Content-Security-Policy": _CSP,
}


def installa_protezioni_http(app: FastAPI, max_corpo_byte: int = MAX_CORPO_BYTE) -> None:
    """Intestazioni di sicurezza su ogni risposta, ``no-store`` sull'API, limite al corpo."""

    @app.middleware("http")
    async def protezioni(request: Request, call_next):
        if request.url.path.startswith("/api"):
            if "transfer-encoding" in request.headers:
                return JSONResponse(status_code=411, content={"detail": "Dimensione della richiesta non dichiarata."})
            lunghezza = request.headers.get("content-length")
            if lunghezza is not None:
                try:
                    valore = int(lunghezza)
                except ValueError:
                    return JSONResponse(status_code=400, content={"detail": "Richiesta non valida."})
                if valore > max_corpo_byte:
                    return JSONResponse(status_code=413, content={"detail": "Richiesta troppo grande."})
        risposta = await call_next(request)
        risposta.headers.update(INTESTAZIONI_SICUREZZA)
        if request.url.path.startswith("/api"):
            risposta.headers["Cache-Control"] = "no-store"
        return risposta
