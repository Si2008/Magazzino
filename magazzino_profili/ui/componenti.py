"""Componenti riutilizzabili dell'interfaccia.

- :func:`icona_colore`: pallino colorato deterministico (tab colori);
- :class:`CardKPI`: card riepilogo con icona, valore ed etichetta.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from .tema import colore_di_codice, px, tema_attivo


def _disegna_pallino(hx: str, d: int) -> QPixmap:
    """Pallino colorato con gradiente, bordo e riflesso (stile mockup)."""
    t = tema_attivo()
    img = QPixmap(d, d)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    corpo = QColor(hx)
    grad = QLinearGradient(0, 0, 0, d)
    grad.setColorAt(0.0, corpo.lighter(125))
    grad.setColorAt(1.0, corpo.darker(120))
    p.setBrush(grad)
    p.setPen(QPen(QColor(t.bordo_forte), float(max(1, d // 16))))
    margine = max(1, d // 16)
    p.drawEllipse(margine, margine, d - 2 * margine, d - 2 * margine)
    # riflesso
    p.setPen(Qt.NoPen)
    r = max(2, d // 5)
    p.setBrush(QColor(255, 255, 255, 90))
    p.drawEllipse(margine + r // 2, margine + r // 2, r, r)
    p.end()
    return img


def icona_colore(codice: str, diametro: int | None = None, sbiadita: bool = False) -> QIcon:
    """Icona "pallino colore" per un codice colore (deterministica).

    Il colore viene dal modulo ``tema`` (mappa nota + derivazione HSL),
    quindi è stabile tra sessioni e non dipende dal database.
    Con ``sbiadita=True`` il pallino si mescola con lo sfondo (tab senza pezzi).
    """
    d = diametro or px(16)
    hx = colore_di_codice(codice)
    if sbiadita:
        from .tema import colore_sbiadito, tema_attivo

        hx = colore_sbiadito(hx, tema_attivo().carta2)
    return QIcon(_disegna_pallino(hx, d))


def icona_tessera(testo: str, colore_hx: str, diametro: int | None = None) -> QIcon:
    """Tessera quadrata con una sigla al centro (icone card KPI)."""
    from PySide6.QtGui import QFont

    d = diametro or px(34)
    t = tema_attivo()
    img = QPixmap(d, d)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor(t.bordo), float(max(1, d // 20))))
    p.setBrush(QColor(t.carta2))
    raggio = d // 5
    p.drawRoundedRect(1, 1, d - 2, d - 2, raggio, raggio)
    p.setPen(QPen(QColor(colore_hx)))
    font = QFont("Segoe UI", d // 4)
    font.setBold(True)
    p.setFont(font)
    p.drawText(img.rect(), Qt.AlignCenter, testo)
    p.end()
    return QIcon(img)


class CardKPI(QWidget):
    """Card riepilogo: icona in alto, valore ed etichetta sotto.

    ``variante``: ``"ok"`` (verde), ``"bad"`` (rosso), ``"good"`` (blu),
    ``"neutro"`` (accento).
    """

    def __init__(
        self,
        icona: QIcon | None,
        valore: str,
        etichetta: str,
        variante: str = "neutro",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        t = tema_attivo()
        colore_variante = {
            "ok": t.ok,
            "bad": t.pericolo,
            "good": t.accento,
            "neutro": t.accento,
        }.get(variante, t.accento)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(14), px(12), px(14), px(12))
        layout.setSpacing(px(6))

        self._icona = QLabel(self)
        self._icona.setFixedSize(QSize(px(34), px(34)))
        if icona is not None:
            self._icona.setPixmap(icona.pixmap(px(34), px(34)))
        self._icona.setAlignment(Qt.AlignCenter)
        self._icona.setStyleSheet(
            f"background: {t.carta2}; border: 1px solid {t.bordo}; border-radius: {px(9)}px;"
        )

        self._valore = QLabel(valore, self)
        self._valore.setObjectName("KPIValore")
        self._valore.setStyleSheet(
            f"font-size: {px(20)}px; font-weight: 800; color: {colore_variante};"
        )

        self._etichetta = QLabel(etichetta, self)
        self._etichetta.setObjectName("KPILabel")
        self._etichetta.setStyleSheet(f"font-size: {px(13)}px; color: {t.testo_dim};")

        layout.addWidget(self._icona)
        layout.addWidget(self._valore)
        layout.addWidget(self._etichetta)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

    def set_valore(self, valore: str) -> None:
        self._valore.setText(valore)

    def set_etichetta(self, etichetta: str) -> None:
        self._etichetta.setText(etichetta)

    def set_colore_valore(self, colore_hx: str) -> None:
        self._valore.setStyleSheet(
            f"font-size: {px(20)}px; font-weight: 800; color: {colore_hx};"
        )
