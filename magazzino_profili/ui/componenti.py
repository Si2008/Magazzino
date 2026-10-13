"""Componenti riutilizzabili dell'interfaccia.

- :func:`icona_colore`: pallino colorato deterministico (tab colori);
- :class:`CardKPI`: card riepilogo con icona, valore ed etichetta.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QPointF, QRectF, QSize
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


def _disegna_icona(nome: str, p: QPainter) -> None:
    """Disegno a tratto dell'icona ``nome`` su griglia logica 24x24 (stile del mockup)."""
    pt = QPointF
    if nome == "grid":
        for x, y in ((3, 3), (13, 3), (3, 13), (13, 13)):
            p.drawRoundedRect(QRectF(x, y, 8, 8), 1.5, 1.5)
    elif nome == "arrow-up":
        p.drawLine(pt(12, 19), pt(12, 5))
        p.drawPolyline([pt(5.5, 11.5), pt(12, 5), pt(18.5, 11.5)])
    elif nome == "arrow-down":
        p.drawLine(pt(12, 5), pt(12, 19))
        p.drawPolyline([pt(5.5, 12.5), pt(12, 19), pt(18.5, 12.5)])
    elif nome == "alert":
        p.drawPolygon([pt(12, 3.5), pt(21.5, 20), pt(2.5, 20)])
        p.drawLine(pt(12, 9.5), pt(12, 13.5))
        p.drawLine(pt(12, 17), pt(12, 17.2))
    elif nome == "layers":
        p.drawPolygon([pt(12, 3), pt(21, 8), pt(12, 13), pt(3, 8)])
        p.drawPolyline([pt(3, 13), pt(12, 18), pt(21, 13)])
        p.drawPolyline([pt(3, 17.5), pt(12, 22), pt(21, 17.5)])
    elif nome == "tag":
        p.drawPolygon([pt(3, 3), pt(12.5, 3), pt(21, 11.5), pt(12.5, 20), pt(3, 11.5)])
        p.drawEllipse(pt(8, 8), 1.6, 1.6)
    elif nome == "weight":
        p.drawPolygon([pt(5, 8), pt(19, 8), pt(21, 21), pt(3, 21)])
        p.drawPolyline([pt(9, 8), pt(9, 5.5), pt(15, 5.5), pt(15, 8)])
    elif nome == "search":
        p.drawEllipse(pt(11, 11), 7, 7)
        p.drawLine(pt(16.2, 16.2), pt(21, 21))
    elif nome == "layout":
        p.drawRoundedRect(QRectF(3, 3, 18, 18), 2, 2)
        p.drawLine(pt(3, 9), pt(21, 9))
        p.drawLine(pt(9, 9), pt(9, 21))


def icona_linea(nome: str, colore_hx: str, d: int | None = None, margine: float = 0.22) -> QIcon:
    """Icona a tratto disegnata con QPainter (nessuna risorsa esterna).

    ``margine`` è la frazione di spazio vuoto attorno al disegno (0 = a filo).
    """
    d = d or px(20)
    img = QPixmap(d, d)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    scala = d * (1.0 - 2 * margine) / 24.0
    p.translate(d * margine, d * margine)
    p.scale(scala, scala)
    pen = QPen(QColor(colore_hx), 2.0)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    _disegna_icona(nome, p)
    p.end()
    return QIcon(img)


def _rgba(hx: str, alfa: float) -> str:
    c = QColor(hx)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {alfa})"


def pillola(testo: str, variante: str = "neutro") -> QLabel:
    """Etichetta a pillola per lo stato: ``ok``, ``avviso``, ``pericolo`` o ``neutro``.

    Non riceve eventi del mouse, così il click arriva alla riga della tabella.
    """
    t = tema_attivo()
    colori = {
        "ok": (t.ok, _rgba(t.ok, 0.14)),
        "avviso": (t.avviso, _rgba(t.avviso, 0.15)),
        "pericolo": (t.pericolo, _rgba(t.pericolo, 0.14)),
        "neutro": (t.testo_dim, t.carta2),
    }
    primo, sfondo = colori.get(variante, colori["neutro"])
    etichetta = QLabel(testo)
    etichetta.setObjectName("Pillola")
    etichetta.setAlignment(Qt.AlignCenter)
    etichetta.setAttribute(Qt.WA_TransparentForMouseEvents)
    etichetta.setStyleSheet(
        f"color: {primo}; background: {sfondo}; border-radius: {px(10)}px;"
        f" padding: {px(2)}px {px(10)}px; font-size: {px(12.5)}px; font-weight: 700;"
    )
    return etichetta


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
        # Stile applicato solo a questo widget (vedi #CardKPI in tema.qss_globale):
        # uno stylesheet senza selettore si propagherebbe alle etichette figlie.
        self.setObjectName("CardKPI")
        self.setAttribute(Qt.WA_StyledBackground, True)
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
