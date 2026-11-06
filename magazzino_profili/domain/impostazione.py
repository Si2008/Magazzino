"""Impostazioni globali dell'applicazione (coppie chiave/valore)."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Impostazione(Base):
    """Una impostazione globale: chiave univoca e valore testuale."""

    __tablename__ = "impostazioni"

    chiave: Mapped[str] = mapped_column(String(64), primary_key=True)
    valore: Mapped[str] = mapped_column(String(255))

    def __repr__(self) -> str:
        return f"<Impostazione {self.chiave!r}={self.valore!r}>"
