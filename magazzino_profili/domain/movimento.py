"""Movimenti di magazzino (carichi, scarichi, rettifiche) e servizio
di aggiornamento della quantità dei pezzi."""

import enum
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Enum as SQLAlchemyEnum
from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.orm import Session

from .base import Base
from .pezzo import QuantitaInsufficienteError

if TYPE_CHECKING:
    from .pezzo import Pezzo


class TipoMovimento(str, enum.Enum):
    """Tipi ammessi di movimento di magazzino.

    - CARICO: aumenta la quantità.
    - SCARICO: diminuisce la quantità.
    - RETTIFICA: correzione contabile verso il basso (accertamento
      scarti, errori di carico, ecc.).
    """

    CARICO = "CARICO"
    SCARICO = "SCARICO"
    RETTIFICA = "RETTIFICA"


class Movimento(Base):
    """Traccia contabile immutabile di un'operazione su un pezzo."""

    __tablename__ = "movimenti"
    __table_args__ = (
        CheckConstraint("quantita > 0", name="quantita_positiva"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    pezzo_id: Mapped[int] = mapped_column(ForeignKey("pezzi.id"), index=True)
    tipo: Mapped[TipoMovimento] = mapped_column(
        SQLAlchemyEnum(TipoMovimento, native_enum=False, length=16)
    )
    quantita: Mapped[int] = mapped_column(Integer)
    data_ora: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    causale: Mapped[str] = mapped_column(Text)
    utente: Mapped[str] = mapped_column(Text)

    pezzo: Mapped["Pezzo"] = relationship(back_populates="movimenti")

    def __repr__(self) -> str:
        return (
            f"<Movimento {self.tipo.value} {self.quantita:+} "
            f"sul pezzo {self.pezzo_id}>"
        )


def registra_movimento(
    session: Session,
    pezzo: "Pezzo",
    tipo: TipoMovimento,
    quantita: int,
    causale: str,
    utente: str = "",
    *,
    now=None,
) -> Movimento:
    """Unica via ammessa per modificare la quantità di un pezzo.

    Regole applicate:
    - ``quantita`` deve essere strettamente positiva;
    - CARICO somma, SCARICO e RETTIFICA sottraggono;
    - se la nuova quantità sarebbe negativa si solleva
      :class:`QuantitaInsufficienteError` lasciando intatta la
      sessione: è il chiamante a decidere se annullare la
      transazione (``session.rollback()``) o continuare.
    """
    if not isinstance(quantita, int) or isinstance(quantita, bool) or quantita <= 0:
        raise ValueError("La quantità del movimento deve essere un intero positivo")
    if not isinstance(tipo, TipoMovimento):
        raise ValueError("Tipo movimento non valido")
    momento = now() if now is not None else datetime.now(timezone.utc)
    if momento.tzinfo is None or momento.utcoffset() is None:
        raise ValueError("L'orario del movimento deve avere un fuso orario")
    momento = momento.astimezone(timezone.utc)

    if tipo is TipoMovimento.CARICO:
        nuova_quantita = pezzo.quantita + quantita
    else:  # SCARICO e RETTIFICA
        nuova_quantita = pezzo.quantita - quantita
        if nuova_quantita < 0:
            raise QuantitaInsufficienteError(
                quantita_corrente=pezzo.quantita,
                quantita_richiesta=quantita,
            )

    if pezzo.unitario and nuova_quantita not in (0, 1):
        raise ValueError("Il barcode identifica un singolo pezzo: giacenza ammessa 0 oppure 1")

    if nuova_quantita > 2147483647:
        raise ValueError("Giacenza fuori dall'intervallo supportato")
    movimento = Movimento(
        pezzo=pezzo,
        tipo=tipo,
        quantita=quantita,
        causale=causale,
        utente=utente,
        data_ora=momento,
    )
    session.add(movimento)
    pezzo.quantita = nuova_quantita
    nuovo_stato = "Caricato" if nuova_quantita > 0 else "Scaricato"
    if pezzo.stato != nuovo_stato or pezzo.data_ultimo_cambio_stato is None:
        pezzo.stato = nuovo_stato
        pezzo.data_ultimo_cambio_stato = momento
    session.flush()
    return movimento
