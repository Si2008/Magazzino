"""Servizi di rettifica diretta dei pezzi (scorta minima, barcode, vassoio).

La quantità NON si tocca qui: passa sempre da ``registra_movimento``.
Qui si gestiscono i dati anagrafici della riga di giacenza.

Fase 7:
- ``aggiorna_barcode``: cambia il codice del barcode di un pezzo esistente
  (id, movimenti, spezzoni e vassoio restano invariati);
- ``imposta_numero_vassoio``: imposta o cancella il numero di vassoio
  (testo libero, max 128 caratteri).

I pezzi eliminati logicamente (``eliminato_il`` valorizzato) non sono
modificabili: ``PezzoEliminatoError``.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..barcode.generazione import valida_per_barcode
from ..domain import Pezzo
from .eccezioni import (
    BarcodeDuplicatoError,
    PezzoEliminatoError,
    PezzoNonTrovatoError,
)

_VINCOLO_BARCODE = "uq_pezzi_barcode"


def imposta_scorta_minima(
    session: Session,
    pezzo_id: int,
    scorta_minima: int | None,
) -> Pezzo:
    """Imposta (o cancella) la scorta minima del pezzo indicato.

    - ``scorta_minima=None``: cancella la soglia (campo ``NULL``);
    - valore intero non negativo: nuova soglia;
    - valore negativo: ``ValueError`` (nessun dato modificato).

    Il pezzo deve esistere: altrimenti ``ValueError``.
    Restituisce il pezzo aggiornato.
    """
    if scorta_minima is not None:
        if (
            not isinstance(scorta_minima, int)
            or isinstance(scorta_minima, bool)
            or scorta_minima < 0
        ):
            raise ValueError("La scorta minima deve essere un intero non negativo")

    with session.begin():
        pezzo = session.get(Pezzo, pezzo_id)
        if pezzo is None:
            raise ValueError(f"Pezzo non trovato: id {pezzo_id}")
        pezzo.scorta_minima = scorta_minima

    return pezzo


def _testo_opzionale(valore: str | None, nome: str, massimo: int = 128) -> str | None:
    """Normalizza un testo opzionale: ``None``/vuoto → ``None``, altrimenti strip + limite."""
    if valore is None:
        return None
    if not isinstance(valore, str):
        raise ValueError(f"{nome} deve essere un testo")
    pulito = valore.strip()
    if not pulito:
        return None
    if len(pulito) > massimo:
        raise ValueError(f"{nome} non può superare {massimo} caratteri")
    return pulito


def _pezzo_bloccato_per_id(session: Session, pezzo_id: int) -> Pezzo:
    """Il pezzo con blocco di riga e dati aggiornati; errore se assente o eliminato."""
    pezzo = session.scalar(
        select(Pezzo)
        .where(Pezzo.id == pezzo_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if pezzo is None:
        raise PezzoNonTrovatoError(f"id {pezzo_id}")
    if pezzo.eliminato_il is not None:
        raise PezzoEliminatoError(pezzo_id)
    return pezzo


def _e_conflitto_barcode(errore: IntegrityError) -> bool:
    """True solo se l'IntegrityError riguarda l'unicità del barcode (PostgreSQL o SQLite)."""
    originale = getattr(errore, "orig", None)
    nome = getattr(getattr(originale, "diag", None), "constraint_name", None)
    if nome == _VINCOLO_BARCODE:
        return True
    testo = str(originale) if originale is not None else str(errore)
    return "pezzi.barcode" in testo or "uq_pezzi_barcode" in testo


def aggiorna_barcode(session: Session, pezzo_id: int, barcode: str) -> Pezzo:
    """Cambia il codice del barcode di un pezzo esistente.

    Il record si cerca per ``Pezzo.id`` e si aggiorna: id, movimenti, spezzoni
    e vassoio restano invariati. Barcode duplicato → ``BarcodeDuplicatoError``
    (anche se il conflitto emerge dal vincolo di unicità per una gara tra
    transazioni); pezzo eliminato → ``PezzoEliminatoError``.
    """
    if not isinstance(barcode, str):
        raise ValueError("Il barcode deve essere un testo")
    barcode_n = barcode.strip().upper()
    if not barcode_n:
        raise ValueError("Il barcode non può essere vuoto")
    if len(barcode_n) > 255:
        raise ValueError("Il barcode non può superare 255 caratteri")
    if not valida_per_barcode(barcode_n):
        raise ValueError("Il barcode può contenere solo lettere, cifre e trattino")

    with session.begin():
        pezzo = _pezzo_bloccato_per_id(session, pezzo_id)
        if pezzo.barcode == barcode_n:
            return pezzo
        duplicato = session.scalar(
            select(Pezzo.id).where(Pezzo.barcode == barcode_n, Pezzo.id != pezzo_id)
        )
        if duplicato is not None:
            raise BarcodeDuplicatoError(barcode_n)
        pezzo.barcode = barcode_n
        try:
            session.flush()
        except IntegrityError as errore:
            if _e_conflitto_barcode(errore):
                raise BarcodeDuplicatoError(barcode_n) from errore
            raise
    return pezzo


def imposta_numero_vassoio(
    session: Session,
    pezzo_id: int,
    numero_vassoio: str | None,
) -> Pezzo:
    """Imposta (o cancella, con ``None`` o stringa vuota) il numero di vassoio.

    Non tocca ``ubicazione``, ``barcode``, ``quantita``, stato o movimenti.
    """
    valore = _testo_opzionale(numero_vassoio, "Il numero di vassoio")
    with session.begin():
        pezzo = _pezzo_bloccato_per_id(session, pezzo_id)
        pezzo.numero_vassoio = valore
        session.flush()
    return pezzo
