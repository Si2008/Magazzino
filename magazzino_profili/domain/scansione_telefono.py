"""Barcode letti dal telefono e in attesa di essere consegnati al programma desktop."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, false, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ScansioneTelefono(Base):
    """Una scansione inviata dal telefono (modalità "Lettore")."""

    __tablename__ = "scansioni_telefono"

    id: Mapped[int] = mapped_column(primary_key=True)
    barcode: Mapped[str] = mapped_column(String(255))
    utente: Mapped[str] = mapped_column(String(64))
    creata_il: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    letta: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())

    def __repr__(self) -> str:
        return f"<ScansioneTelefono {self.id} {self.barcode!r} letta={self.letta}>"
