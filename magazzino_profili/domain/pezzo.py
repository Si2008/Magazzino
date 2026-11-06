"""Giacenza: un pezzo è la combinazione profilo + colore + lunghezza."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.normalizzazione import normalizza_codice
from .base import Base

if TYPE_CHECKING:
    from .colore import Colore
    from .movimento import Movimento
    from .profilo import Profilo
    from .spezzone import Spezzone


class QuantitaInsufficienteError(Exception):
    """Sollevata quando un movimento porterebbe la quantità sotto zero."""

    def __init__(
        self,
        quantita_corrente: int,
        quantita_richiesta: int,
        descrizione: str = "",
    ) -> None:
        self.quantita_corrente = quantita_corrente
        self.quantita_richiesta = quantita_richiesta
        super().__init__(
            f"Quantità insufficiente: disponibile {quantita_corrente}, "
            f"richiesta {quantita_richiesta} {descrizione}".strip()
        )


class Pezzo(Base):
    """Riga di giacenza: quanti pezzi di una combinazione specifica ci sono.

    La quantità NON va mai modificata direttamente: usare
    ``registra_movimento`` (vedi ``domain/movimento.py``), che applica
    la regola anti-sottozero e registra la traccia contabile.
    """

    __tablename__ = "pezzi"
    __table_args__ = (
        Index("combinazione_legacy", "profilo_id", "colore_id", "lunghezza_mm", unique=True,
              postgresql_where=text("NOT unitario"), sqlite_where=text("unitario = 0")),
        Index("pezzi_materiale_attivo", "profilo_id", "colore_id", "lunghezza_mm",
              postgresql_where=text("eliminato_il IS NULL"), sqlite_where=text("eliminato_il IS NULL")),
        CheckConstraint("NOT unitario OR quantita IN (0,1)", name="pezzo_unitario_quantita"),
        CheckConstraint("quantita >= 0", name="quantita_non_negativa"),
        # Solo i due stati persistiti sono ammessi; NULL = record storico
        # privo di una transizione dimostrabile (migrazioni 004/005).
        CheckConstraint(
            "stato IS NULL OR stato IN ('Caricato', 'Scaricato')",
            name="stato_valido",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    profilo_id: Mapped[int] = mapped_column(ForeignKey("profili.id"), index=True)
    colore_id: Mapped[int] = mapped_column(ForeignKey("colori.id"), index=True)
    lunghezza_mm: Mapped[int] = mapped_column(Integer)
    quantita: Mapped[int] = mapped_column(Integer, default=0)
    # Testo libero: scaffale, corsia, magazzino, ecc.
    ubicazione: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Scorta minima per gli avvisi di scorte basse (Prompt 3).
    # Aggiunta come migrazione (migrations/001_scorta_minima.sql):
    # nullable per compatibilità con i dati già presenti in tabella.
    scorta_minima: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Generato dal sistema: CODICE-NORMALIZZATO-COLORE-NORMALIZZATO-lunghezza_mm.
    barcode: Mapped[str] = mapped_column(String(255), unique=True)
    # Campi della Fase 6: nullable per i record esistenti (NULL = storico).
    # Testo libero (es. "4", "Vassoio 4"): nessuna unicità richiesta.
    numero_vassoio: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # "Caricato" | "Scaricato" | None (storico). Vincolato da stato_valido.
    stato: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # Ultimo cambio di stato (UTC); valorizzata solo insieme a ``stato``.
    data_ultimo_cambio_stato: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Cancellazione logica: valorizzata => il record non è più attivo.
    eliminato_il: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    # I record storici restano aggregati. Le nuove etichette identificano un
    # singolo pezzo fisico: giacenza 0/1, barcode seriale senza quantità.
    unitario: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))

    profilo: Mapped["Profilo"] = relationship(back_populates="pezzi")
    colore: Mapped["Colore"] = relationship(back_populates="pezzi")
    movimenti: Mapped[list["Movimento"]] = relationship(back_populates="pezzo")
    spezzoni: Mapped[list["Spezzone"]] = relationship(back_populates="pezzo_origine")

    def __repr__(self) -> str:
        return f"<Pezzo {self.barcode!r} x{self.quantita}>"


def nome_file_sezione(codice: str) -> str:
    """Restituisce il nome del file PNG atteso per il disegno della sezione.

    Funzione pura: codice normalizzato (vedi ``db/normalizzazione.py``)
    seguito dall'estensione ``.png``.

    Esempio: ``"ab/12"`` -> ``"AB-12.png"``.
    """
    return normalizza_codice(codice) + ".png"
