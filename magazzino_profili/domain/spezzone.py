"""Scarti derivati da un taglio: i pezzi residui di una lavorazione."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .pezzo import Pezzo


class Spezzone(Base):
    """Tronco residuo prodotto tagliando un pezzo di giacenza."""

    __tablename__ = "spezzoni"
    __table_args__ = (
        CheckConstraint("lunghezza_mm > 0", name="lunghezza_positiva"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Il pezzo da cui è stato ricavato lo spezzone.
    pezzo_origine_id: Mapped[int] = mapped_column(ForeignKey("pezzi.id"), index=True)
    # Utente che ha registrato lo spezzone (per la tracciabilità).
    utente: Mapped[str] = mapped_column(String, nullable=False)
    lunghezza_mm: Mapped[int] = mapped_column(Integer)
    data_creazione: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    # True quando lo spezzone è stato riutilizzato in un successivo lavoro.
    utilizzato: Mapped[bool] = mapped_column(Boolean, default=False)

    pezzo_origine: Mapped["Pezzo"] = relationship(back_populates="spezzoni")

    def __repr__(self) -> str:
        return f"<Spezzone {self.lunghezza_mm} mm da pezzo {self.pezzo_origine_id}>"
