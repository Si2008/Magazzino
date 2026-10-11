"""Anagrafica dei profili in alluminio/PVC."""

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .pezzo import Pezzo


class Profilo(Base):
    """Tipo di profilato (es. 'ALU 40x80', 'PVC FINESTRA 70')."""

    __tablename__ = "profili"

    id: Mapped[int] = mapped_column(primary_key=True)
    codice: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    descrizione: Mapped[str] = mapped_column(Text)
    # Percorso del PNG con il disegno della sezione trasversale.
    immagine_sezione: Mapped[str | None] = mapped_column(String(512), nullable=True)
    peso_kg_per_metro: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    lunghezza_standard_mm: Mapped[int] = mapped_column(Integer)

    # Collegamento verso i pezzi in giacenza.
    pezzi: Mapped[list["Pezzo"]] = relationship(back_populates="profilo")

    def __repr__(self) -> str:  # comodo nei log e nel debugger
        return f"<Profilo {self.codice!r}>"
