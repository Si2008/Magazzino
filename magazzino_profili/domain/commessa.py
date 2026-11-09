"""Commesse ufficiali, righe originali e associazione dei barcode fisici."""
from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class Commessa(Base):
    __tablename__ = 'commesse'
    id: Mapped[int] = mapped_column(primary_key=True)
    identita: Mapped[str] = mapped_column(String(64), unique=True)
    cognome: Mapped[str] = mapped_column(String(200))
    cognome_chiave: Mapped[str] = mapped_column(String(200), index=True)
    nome: Mapped[str] = mapped_column(String(250))
    creata_il: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=lambda: datetime.now(timezone.utc))


class RigaCommessa(Base):
    __tablename__ = 'righe_commessa'
    id: Mapped[int] = mapped_column(primary_key=True)
    commessa_id: Mapped[int] = mapped_column(ForeignKey('commesse.id'), index=True)
    profilo: Mapped[str] = mapped_column(String(128))
    colore: Mapped[str] = mapped_column(String(128))
    lunghezza: Mapped[int] = mapped_column(Integer)
    quantita: Mapped[int] = mapped_column(Integer)
    riferimento: Mapped[str] = mapped_column(Text, default='')
    barra_intera: Mapped[bool] = mapped_column(Boolean, default=False)


class AssegnazioneCommessa(Base):
    __tablename__ = 'assegnazioni_commessa'
    id: Mapped[int] = mapped_column(primary_key=True)
    commessa_id: Mapped[int] = mapped_column(ForeignKey('commesse.id'), index=True)
    pezzo_id: Mapped[int] = mapped_column(ForeignKey('pezzi.id'), unique=True)
