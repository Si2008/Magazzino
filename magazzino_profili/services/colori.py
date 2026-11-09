"""Anagrafica colori: lettura e impostazione del colore mostrato (``colore_hex``)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain import Colore
from .colori_base import normalizza_hex


def elenco_colori(session: Session) -> list[Colore]:
    """Tutti i colori ordinati per codice (sono poche decine: nessuna paginazione)."""
    return list(session.scalars(select(Colore).order_by(Colore.codice_normalizzato)))


def imposta_colore_hex(session: Session, colore_id: int, valore: str | None) -> str | None:
    """Imposta (``#rrggbb``) o rimuove (``None`` o stringa vuota) il colore di un colore.

    Solleva ``ValueError`` se ``valore`` non è un esadecimale valido e ``LookupError``
    se il colore non esiste. Restituisce il valore salvato.
    """
    if valore is None or not str(valore).strip():
        nuovo = None
    else:
        nuovo = normalizza_hex(str(valore))
        if nuovo is None:
            raise ValueError("Colore non valido: usare il formato #RRGGBB.")
    with session.begin():
        colore = session.get(Colore, colore_id)
        if colore is None:
            raise LookupError(f"Colore {colore_id} inesistente.")
        colore.colore_hex = nuovo
    return nuovo
