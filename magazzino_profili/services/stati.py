"""Stati del barcode (Caricato / Scaricato) e cancellazione logica.

Il tempo arriva sempre da un clock iniettabile (``now``): i test non toccano
l'orologio del computer. Tutti gli orari sono in UTC e vengono ricavati dai
dati persistenti, mai da timer in memoria.
"""

import logging
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..domain import Pezzo
from .pezzi import _pezzo_bloccato_per_id

logger = logging.getLogger(__name__)

STATI_BARCODE = frozenset({"Caricato", "Scaricato"})
DURATA_SCADENZA = timedelta(hours=48)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ora_utc(clock: Callable[[], datetime]) -> datetime:
    momento = clock()
    if momento.tzinfo is None or momento.utcoffset() is None:
        raise ValueError("Il clock deve restituire un datetime con timezone")
    return momento.astimezone(timezone.utc)


def imposta_stato(
    session: Session,
    pezzo_id: int,
    stato: str,
    *,
    now: Callable[[], datetime] = utc_now,
) -> Pezzo:
    """Imposta lo stato del barcode e, solo se cambia, l'orario dell'ultimo passaggio.

    Reimpostare lo stesso stato non tocca il timestamp: la scadenza delle 48 ore
    non si può "rinnovare" per errore. Non crea movimenti.
    """
    if not isinstance(stato, str) or stato not in STATI_BARCODE:
        raise ValueError("Stato non valido")
    with session.begin():
        pezzo = _pezzo_bloccato_per_id(session, pezzo_id)  # assente / eliminato -> eccezione
        if pezzo.stato != stato:
            momento = _ora_utc(now)
            pezzo.stato = stato
            pezzo.data_ultimo_cambio_stato = momento
            session.flush()
    return pezzo


def lista_scaduti_per_eliminazione(
    session: Session,
    *,
    now: Callable[[], datetime] = utc_now,
) -> list[int]:
    """ID dei barcode Scaricati da almeno 48 ore (scadenza raggiunta o superata)."""
    soglia = _ora_utc(now) - DURATA_SCADENZA
    return list(
        session.scalars(
            select(Pezzo.id)
            .where(
                Pezzo.eliminato_il.is_(None),
                Pezzo.stato == "Scaricato",
                Pezzo.data_ultimo_cambio_stato.is_not(None),
                Pezzo.data_ultimo_cambio_stato <= soglia,
            )
            .order_by(Pezzo.id)
        )
    )


def elimina_scaduto(
    session: Session,
    pezzo_id: int,
    *,
    now: Callable[[], datetime] = utc_now,
) -> bool:
    """Elimina logicamente il barcode solo se è ancora scaduto, in un'unica istruzione.

    Verifica e scrittura sono una sola ``UPDATE ... WHERE``: un'altra transazione
    che cambia stato nel frattempo fa sì che la condizione non sia più vera
    (0 righe, ``False``). Nessun confronto di date in Python.
    """
    momento = _ora_utc(now)
    soglia = momento - DURATA_SCADENZA
    with session.begin():
        esito = session.execute(
            update(Pezzo)
            .where(
                Pezzo.id == pezzo_id,
                Pezzo.eliminato_il.is_(None),
                Pezzo.stato == "Scaricato",
                Pezzo.data_ultimo_cambio_stato.is_not(None),
                Pezzo.data_ultimo_cambio_stato <= soglia,
            )
            .values(eliminato_il=momento),
            execution_options={"synchronize_session": False},
        )
        return esito.rowcount == 1


def elimina_manualmente(
    session: Session,
    pezzo_id: int,
    confermato: bool,
    *,
    now: Callable[[], datetime] = utc_now,
) -> Pezzo:
    """Eliminazione logica richiesta dall'utente: qualunque stato, nessun limite di 48 ore."""
    if confermato is not True:
        raise ValueError("Eliminazione non confermata")
    momento = _ora_utc(now)
    with session.begin():
        pezzo = _pezzo_bloccato_per_id(session, pezzo_id)
        pezzo.eliminato_il = momento
        session.flush()
    return pezzo


def elimina_scaduti(factory, *, now: Callable[[], datetime] = utc_now) -> int:
    """Controllo completo: elimina tutti i barcode scaduti e restituisce quanti.

    Un errore del database su un record viene registrato e non ferma gli altri;
    l'errore sull'elenco iniziale si propaga (il chiamante riproverà al giro dopo).
    """
    momento = _ora_utc(now)  # un solo istante per tutto il controllo

    def fisso() -> datetime:
        return momento

    with factory() as lettura:
        da_eliminare = lista_scaduti_per_eliminazione(lettura, now=fisso)
        lettura.rollback()
    eliminati = 0
    for pezzo_id in da_eliminare:
        with factory() as sessione:
            try:
                if elimina_scaduto(sessione, pezzo_id, now=fisso):
                    eliminati += 1
            except SQLAlchemyError:
                logger.exception("Eliminazione automatica non riuscita per il pezzo id %s", pezzo_id)
    return eliminati
