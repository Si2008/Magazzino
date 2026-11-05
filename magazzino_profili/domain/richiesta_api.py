"""Registro transazionale delle richieste, per impedire movimenti duplicati."""
from datetime import datetime
from sqlalchemy import String, JSON, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class RichiestaAPI(Base):
    __tablename__ = "richieste_api"
    utente: Mapped[str] = mapped_column(String(64), primary_key=True)
    chiave: Mapped[str] = mapped_column(String(64), primary_key=True)
    impronta: Mapped[str] = mapped_column(String(64))
    risposta: Mapped[dict] = mapped_column(JSON)
    creata_il: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
