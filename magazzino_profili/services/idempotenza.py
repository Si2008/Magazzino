"""Mutazione e risultato salvati nello stesso commit, anche in caso di retry."""
import hashlib
import json
import threading
from sqlalchemy import select, text
from ..domain import RichiestaAPI

_sqlite_lock = threading.RLock()


def esegui(factory, utente, chiave, operazione, dati, azione):
    if chiave is not None and (not isinstance(chiave, str) or not 1 <= len(chiave) <= 64):
        raise ValueError("Identificativo richiesta non valido")
    impronta = hashlib.sha256(json.dumps([operazione, dati], sort_keys=True,
                                        ensure_ascii=False, default=str).encode()).hexdigest()
    with _sqlite_lock, factory() as sessione, sessione.begin():
        if chiave:
            if sessione.get_bind().dialect.name == "postgresql":
                lock = int.from_bytes(hashlib.sha256((utente + ":" + chiave).encode()).digest()[:8], "big", signed=True)
                sessione.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": lock})
            precedente = sessione.get(RichiestaAPI, (utente, chiave))
            if precedente is not None:
                if precedente.impronta != impronta:
                    raise ValueError("Identificativo richiesta già usato per un'altra operazione")
                return precedente.risposta
        risposta = azione(sessione)
        if chiave:
            sessione.add(RichiestaAPI(utente=utente, chiave=chiave, impronta=impronta, risposta=risposta))
        return risposta
