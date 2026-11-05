"""Colori mostrati nell'interfaccia: un'unica fonte per chip, tabelle e pillole.

Priorità: colore confermato dall'utente (``colori.colore_hex``) → suggerimento dedotto
dal codice → "non definito" (cerchio tratteggiato con "?"). Mai un colore casuale.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from PySide6.QtCore import QObject, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap

from ..services.colori_base import normalizza_hex, suggerisci_colori

CONFERMATO = "confermato"
SUGGERITO = "suggerito"
NON_DEFINITO = "non_definito"


@dataclass(frozen=True)
class Swatch:
    colori: tuple[str, ...]      # 0 = non definito, 1 = tinta unita, 2 = bicolore
    origine: str

    @property
    def definito(self) -> bool:
        return bool(self.colori)

    def css(self, neutro: str = "#9aa0a8") -> str:
        """Valore CSS per sfondo (QSS/HTML): tinta unita o gradiente a metà."""
        if not self.colori:
            return neutro
        if len(self.colori) == 1:
            return self.colori[0]
        a, b = self.colori
        return f"qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {a},stop:0.5 {a},stop:0.5 {b},stop:1 {b})"

    def descrizione(self) -> str:
        if not self.colori:
            return "Colore non definito"
        testo = " / ".join(self.colori)
        return f"{testo} (confermato)" if self.origine == CONFERMATO else f"{testo} (suggerito, non confermato)"


class RegistroColori:
    """Mappa codice colore → :class:`Swatch`, caricata con una sola query."""

    def __init__(self) -> None:
        self._righe: dict[str, tuple[str, str | None]] = {}

    def carica(self, righe: Iterable[tuple[str, str, str | None]]) -> None:
        """``righe``: ``(codice_normalizzato, nome_visualizzato, colore_hex)``."""
        self._righe = {(c or "").upper().strip(): (n or "", h) for c, n, h in righe}

    def swatch(self, codice: str) -> Swatch:
        chiave = (codice or "").upper().strip()
        nome, esadecimale = self._righe.get(chiave, ("", None))
        confermato = normalizza_hex(esadecimale)
        if confermato:
            return Swatch((confermato,), CONFERMATO)
        suggerito = suggerisci_colori(chiave, nome)
        if suggerito:
            return Swatch(tuple(suggerito), SUGGERITO)
        return Swatch((), NON_DEFINITO)


_REGISTRO = RegistroColori()


class _Segnalatore(QObject):
    """Fase 8: emesso dopo ogni cambio colore → Inventario/Scarico aggiornano l'interfaccia."""

    colori_cambiati = Signal()


SEGNALATORE = _Segnalatore()


def registro() -> RegistroColori:
    return _REGISTRO


def ricarica_da_database(session) -> None:
    """Rilegge i colori dal database (una query). Da chiamare in ``aggiorna()`` delle schede."""
    from sqlalchemy import select

    from ..domain import Colore

    righe = session.execute(
        select(Colore.codice_normalizzato, Colore.nome_visualizzato, Colore.colore_hex)
    ).all()
    _REGISTRO.carica((c, n, h) for c, n, h in righe)


def dipingi_swatch(p: QPainter, x: float, y: float, d: float, swatch: Swatch, tema, opacita: float = 1.0) -> None:
    """Disegna il pallino con il colore ESATTO (niente gradiente né riflesso)."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setOpacity(p.opacity() * opacita)
    rect = QRectF(x + 0.5, y + 0.5, d - 1.0, d - 1.0)
    if not swatch.definito:
        p.setPen(QPen(QColor(tema.testo_dim), 1.2, Qt.PenStyle.DashLine))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(rect)
        carattere = p.font()
        carattere.setPixelSize(max(8, int(d * 0.62)))
        carattere.setBold(True)
        p.setFont(carattere)
        p.setPen(QColor(tema.testo_dim))
        p.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), "?")
    else:
        forma = QPainterPath()
        forma.addEllipse(rect)
        p.setPen(Qt.PenStyle.NoPen)
        if len(swatch.colori) == 1:
            p.fillPath(forma, QColor(swatch.colori[0]))
        else:
            p.setClipPath(forma)
            meta = rect.width() / 2
            p.fillRect(QRectF(rect.left(), rect.top(), meta, rect.height()), QColor(swatch.colori[0]))
            p.fillRect(QRectF(rect.left() + meta, rect.top(), meta, rect.height()), QColor(swatch.colori[1]))
            p.setClipping(False)
        p.setPen(QPen(QColor(tema.bordo_campo), 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(rect)
    p.restore()


def pixmap_swatch(swatch: Swatch, d: int, tema, sbiadito: bool = False) -> QPixmap:
    img = QPixmap(d, d)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    dipingi_swatch(p, 0, 0, d, swatch, tema, opacita=0.45 if sbiadito else 1.0)
    p.end()
    return img
