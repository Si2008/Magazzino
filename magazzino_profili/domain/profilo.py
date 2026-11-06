"""Anagrafica dei profili in alluminio/PVC."""

from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from sqlalchemy import Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from ..db.normalizzazione import normalizza_codice

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
    # Dato storico conservato per compatibilità dello schema. I nuovi flussi
    # non lo chiedono né lo mostrano; il default tecnico rispetta il CHECK esistente.
    peso_kg_per_metro: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("1.0000"))
    lunghezza_standard_mm: Mapped[int] = mapped_column(Integer)

    # Collegamento verso i pezzi in giacenza.
    pezzi: Mapped[list["Pezzo"]] = relationship(back_populates="profilo")

    @validates("codice")
    def _codice_valido(self, chiave, valore):
        valore = normalizza_codice(valore)
        if not valore or len(valore) > 64 or any(ord(c) < 32 for c in valore):
            raise ValueError("Codice profilo obbligatorio, massimo 64 caratteri senza caratteri di controllo")
        return valore

    @validates("peso_kg_per_metro")
    def _peso_valido(self, chiave, valore):
        try:
            peso = Decimal(str(valore))
        except (InvalidOperation, ValueError, TypeError) as errore:
            raise ValueError("Peso del profilo finito e positivo obbligatorio") from errore
        if not peso.is_finite() or not Decimal("0.0001") <= peso <= Decimal("999999.9999"):
            raise ValueError("Peso del profilo finito e positivo obbligatorio")
        return peso.quantize(Decimal("0.0001"))

    @validates("lunghezza_standard_mm")
    def _lunghezza_valida(self, chiave, valore):
        if isinstance(valore, bool) or not isinstance(valore, int) or not 1 <= valore <= 2147483647:
            raise ValueError("La lunghezza standard deve essere un intero positivo")
        return valore

    def __repr__(self) -> str:  # comodo nei log e nel debugger
        return f"<Profilo {self.codice!r}>"
