"""Autenticazione del modulo web: login e token con scadenza.

Il token è *stateless*: un payload JSON firmato con HMAC-SHA256
(nome utente, ruolo, scadenza assoluta). La segrete si legge da
``config.toml`` (sezione ``[web]``, chiave ``segrete_token``): non è
mai hardcoded nel codice. Non serve alcuno stato in memoria o in
database: il token resta valido anche dopo un riavvio del server.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Callable

from fastapi import Header, HTTPException
from sqlalchemy import select

from ..sicurezza import Ruolo, Utente, autentica, puo

MESSAGGIO_NON_AUTENTICATO = "Non autenticato: effettuare il login."
MESSAGGIO_TOKEN_INVALIDO = "Sessione scaduta o non valida: effettuare nuovamente il login."


@dataclass(frozen=True)
class UtenteAutenticato:
    """Utente identificato da un token valido e non scaduto."""

    username: str
    ruolo: str
    scadenza: int


def _firma(payload_b64: str, segrete: bytes) -> str:
    """Firma HMAC-SHA256 (hex) del payload codificato in base64url."""
    return hmac.new(segrete, payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()


def crea_token(
    username: str,
    ruolo: str,
    durata_secondi: int,
    segrete: bytes,
) -> str:
    """Crea un token valido per ``durata_secondi`` secondi.

    Formato: ``<payload base64url>.<firma esadecimale>``; il payload è
    un JSON con nome utente, ruolo e tempo di scadenza assoluto (epoch).
    """
    scadenza = int(time.time()) + int(durata_secondi)
    payload = json.dumps(
        {"u": username, "r": ruolo, "exp": scadenza},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    payload_b64 = (
        base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")
    )
    return f"{payload_b64}.{_firma(payload_b64, segrete)}"


def verifica_token(
    token: str,
    segrete: bytes,
    adesso: float | None = None,
) -> UtenteAutenticato | None:
    """Verifica firma e scadenza del token.

    Restituisce l'utente autenticato, oppure ``None`` se il token è
    malformato, alterato, firmato con una segrete diversa o scaduto.
    """
    if not token or "." not in token:
        return None
    payload_b64, _, firma = token.partition(".")
    # Confronto in tempo costante: non rivela quanta parte della firma era corretta.
    if not hmac.compare_digest(firma, _firma(payload_b64, segrete)):
        return None
    try:
        padding = "=" * (-len(payload_b64) % 4)
        dati = json.loads(base64.urlsafe_b64decode(payload_b64 + padding))
        scadenza = int(dati["exp"])
        username = str(dati["u"])
        ruolo = str(dati["r"])
    except (ValueError, KeyError, TypeError):
        return None
    if adesso is None:
        adesso = time.time()
    if adesso >= scadenza:
        return None
    return UtenteAutenticato(username=username, ruolo=ruolo, scadenza=scadenza)


def prova_login(session, username: str, password: str):
    """Delega la verifica delle credenziali al modulo sicurezza esistente.

    Restituisce l'``Utente`` se le credenziali sono valide, altrimenti
    ``None`` (la password non viene mai loggata né restituita).
    """
    return autentica(session, username, password)


def verifica_permesso(utente: UtenteAutenticato, azione: str) -> None:
    """Solleva HTTP 403 se il ruolo non può compiere l'azione.

    Riutilizza la matrice di permessi esistente
    (``sicurezza.utenti.puo``): OPERATORE e AMMINISTRATORE possono
    carico e scarico; SOLA_LETTURA non può farli da remoto.
    """
    try:
        ruolo = Ruolo(utente.ruolo)
    except ValueError:
        ruolo = None
    if ruolo is None or not puo(ruolo, azione):
        raise HTTPException(
            status_code=403,
            detail=f"Il ruolo {utente.ruolo} non è autorizzato a questa operazione.",
        )


def crea_dipendenza_utente(segrete: bytes, session_factory=None) -> Callable:
    """Crea la dipendenza FastAPI che valida il token Bearer di ogni richiesta.

    Gestisce: intestazione assente, formato non ``Bearer <token>``,
    token alterato e token scaduto — in tutti i casi HTTP 401 con
    messaggio in italiano.

    Se ``session_factory`` è fornita, a ogni richiesta l'utente viene
    riletto dal database: un utente cancellato non è più accettato
    (401) e il ruolo usato è quello attuale, non quello nel token (che
    resta valido per un'ora dopo un cambio di permessi).
    """

    def utente_da_token(
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> UtenteAutenticato:
        if authorization is None or not authorization.strip():
            raise HTTPException(status_code=401, detail=MESSAGGIO_NON_AUTENTICATO)
        parti = authorization.strip().split(None, 1)
        if len(parti) != 2 or parti[0].lower() != "bearer":
            raise HTTPException(
                status_code=401,
                detail="Intestazione Authorization non valida (atteso: Bearer <token>).",
            )
        utente = verifica_token(parti[1].strip(), segrete)
        if utente is None:
            raise HTTPException(status_code=401, detail=MESSAGGIO_TOKEN_INVALIDO)
        if session_factory is not None:
            with session_factory() as sessione:
                attuale = sessione.scalar(select(Utente).where(Utente.username == utente.username))
            if attuale is None:
                raise HTTPException(status_code=401, detail=MESSAGGIO_TOKEN_INVALIDO)
            utente = UtenteAutenticato(
                username=attuale.username,
                ruolo=attuale.ruolo,
                scadenza=utente.scadenza,
            )
        return utente

    return utente_da_token
