"""Utenti e permessi del magazzino (ruoli).

Ruoli:
- AMMINISTRATORE: tutto (inventario, carico, scarico, profili, avvisi,
  report);
- OPERATORE: solo carico e scarico;
- SOLA_LETTURA: solo inventario e report.

Le password sono salvate con hash bcrypt: in chiaro non vengono mai
scritte in database.
"""

from __future__ import annotations

import enum

import bcrypt
from sqlalchemy import String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..domain.base import Base


class Ruolo(str, enum.Enum):
    """Ruoli ammessi dal sistema di permessi."""

    AMMINISTRATORE = "AMMINISTRATORE"
    OPERATORE = "OPERATORE"
    SOLA_LETTURA = "SOLA_LETTURA"


class Utente(Base):
    """Utente del sistema con ruolo e password cifrata (hash bcrypt)."""

    __tablename__ = "utenti"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # bcrypt produce hash di 60 caratteri.
    password_hash: Mapped[str] = mapped_column(String(128))
    ruolo: Mapped[str] = mapped_column(String(32), default=Ruolo.OPERATORE.value)

    def __repr__(self) -> str:  # pragma: no cover
        return f"Utente(username={self.username!r}, ruolo={self.ruolo!r})"


# ---------------------------------------------------------------------------
# Password (hash bcrypt)
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Restituisce l'hash bcrypt della password (in chiaro mai salvata)."""
    if not password:
        raise ValueError("La password non può essere vuota")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verifica_password(password: str, password_hash: str) -> bool:
    """Verifica la password in chiaro contro l'hash salvato."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Operazioni su utente (transazioni esplicite)
# ---------------------------------------------------------------------------

def crea_utente(
    session: Session,
    username: str,
    password: str,
    ruolo: Ruolo | str,
) -> Utente:
    """Crea un nuovo utente con la password cifrata in hash bcrypt."""
    username_pulito = username.strip()
    if not username_pulito:
        raise ValueError("Il nome utente non può essere vuoto")
    ruolo_valore = ruolo.value if isinstance(ruolo, Ruolo) else Ruolo(ruolo).value

    with session.begin():
        esistente = session.scalar(select(Utente).where(Utente.username == username_pulito))
        if esistente is not None:
            raise ValueError(f"Il nome utente '{username_pulito}' è già in uso")
        utente = Utente(
            username=username_pulito,
            password_hash=hash_password(password),
            ruolo=ruolo_valore,
        )
        session.add(utente)

    return utente


def autentica(session: Session, username: str, password: str) -> Utente | None:
    """Verifica le credenziali; restituisce l'utente o ``None``."""
    utente = session.scalar(
        select(Utente).where(Utente.username == username.strip())
    )
    if utente is None:
        return None
    if not verifica_password(password, utente.password_hash):
        return None
    return utente


# ---------------------------------------------------------------------------
# Permessi
# ---------------------------------------------------------------------------

# Schede della finestra principale consentite a ciascun ruolo.
SCHEDE_CONSENTITE: dict[Ruolo, tuple[str, ...]] = {
    Ruolo.AMMINISTRATORE: ("inventario", "carico", "scarico", "profili", "avvisi"),
    Ruolo.OPERATORE: ("carico", "scarico"),
    Ruolo.SOLA_LETTURA: ("inventario",),
}

# Azioni consentite (incluse quelle di menu, es. report).
AZIONI_CONSENTITE: dict[Ruolo, frozenset[str]] = {
    Ruolo.AMMINISTRATORE: frozenset(
        {"inventario", "carico", "scarico", "profili", "avvisi", "report"}
    ),
    Ruolo.OPERATORE: frozenset({"carico", "scarico"}),
    Ruolo.SOLA_LETTURA: frozenset({"inventario", "report"}),
}


def schede_consenti(ruolo: Ruolo | str) -> tuple[str, ...]:
    """Schede della finestra principale visibili per il ruolo."""
    ruolo = ruolo if isinstance(ruolo, Ruolo) else Ruolo(ruolo)
    return SCHEDE_CONSENTITE[ruolo]


def puo(ruolo: Ruolo | str, azione: str) -> bool:
    """Indica se il ruolo può compiere l'azione (es. ``"carico"``, ``"report"``)."""
    ruolo = ruolo if isinstance(ruolo, Ruolo) else Ruolo(ruolo)
    return azione in AZIONI_CONSENTITE[ruolo]
