"""Anagrafica dei colori (finiture) dei profili."""

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .pezzo import Pezzo


class Colore(Base):
    """Colore/finitura di un profilo, con codice normalizzato univoco."""

    __tablename__ = "colori"

    id: Mapped[int] = mapped_column(primary_key=True)
    codice_normalizzato: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    nome_visualizzato: Mapped[str] = mapped_column(String(128))

    # Collegamento verso i pezzi in giacenza.
    pezzi: Mapped[list["Pezzo"]] = relationship(back_populates="colore")

    def __repr__(self) -> str:
        return f"<Colore {self.codice_normalizzato!r} ({self.nome_visualizzato!r})>"
