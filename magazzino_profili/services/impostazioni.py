"""Impostazioni globali: soglia di sotto scorta."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..domain import Impostazione

CHIAVE_SOGLIA = "soglia_sotto_scorta"
SOGLIA_DEFAULT = 5
SOGLIA_MIN = 1
SOGLIA_MAX = 99
#: "In esaurimento" arriva fino a MOLTIPLICATORE volte il riferimento di sotto scorta.
MOLTIPLICATORE_ESAURIMENTO = 3


def leggi_soglia(session: Session) -> int:
    """Soglia globale di sotto scorta (default 5 se mai impostata o se il valore è illeggibile)."""
    riga = session.get(Impostazione, CHIAVE_SOGLIA)
    if riga is None:
        return SOGLIA_DEFAULT
    try:
        valore = int(riga.valore)
    except (TypeError, ValueError):
        return SOGLIA_DEFAULT
    return max(SOGLIA_MIN, min(SOGLIA_MAX, valore))


def imposta_soglia(session: Session, valore: int) -> int:
    """Salva la soglia globale e restituisce il valore effettivamente salvato (limitato a 1..99)."""
    if isinstance(valore, bool) or not isinstance(valore, int):
        raise ValueError("La soglia deve essere un numero intero.")
    valore = max(SOGLIA_MIN, min(SOGLIA_MAX, valore))
    with session.begin():
        riga = session.get(Impostazione, CHIAVE_SOGLIA)
        if riga is None:
            session.add(Impostazione(chiave=CHIAVE_SOGLIA, valore=str(valore)))
        else:
            riga.valore = str(valore)
    return valore


def soglia_esaurimento(soglia: int) -> int:
    """Limite alto di "in esaurimento" per la soglia globale (soglia × 3)."""
    return soglia * MOLTIPLICATORE_ESAURIMENTO
