"""Componenti riutilizzabili dell'interfaccia (stile del mockup).

- :func:`icona_colore`: pallino colorato deterministico (tab colori);
- :func:`icona_linea` / :func:`icona_tessera`: wrapper per compatibilità;
- :func:`bottone`, :func:`chip`: pulsanti dello stile del mockup;
- :class:`Pillola` (+ :func:`pillola`): badge a pillola con pallino;
- :class:`CardKPI`: tessera riepilogo orizzontale (icona a sinistra);
- :class:`Stepper`: campo numerico con pulsanti − e +;
- :class:`MessaggioErrore`, :class:`Anteprima`, :func:`divisore`,
  :func:`campo_con_etichetta`: form e riquadri;
- :class:`ListaMovimenti`: ultimi movimenti del magazzino;
- :class:`Toast`: notifica in basso a destra.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QIcon,
    QIntValidator,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import animazioni, registro_colori
from .icone import ic_px, icona_svg, pixmap_icona
from .tema import M, alfa, colore_da_css, px, rem, tema_attivo


# ---------------------------------------------------------------- pallino colore
def icona_colore(
    codice: str | None,
    diametro: int | None = None,
    sbiadita: bool = False,
) -> QIcon:
    """Icona "pallino colore" per un codice colore (Fase 8: colore REALE).

    Il pallino viene dal registro unico (:mod:`.registro_colori`): colore
    confermato → suggerimento dal codice → non definito (tratteggiato con «?»).
    Tinta unita ESATTA, bicolore diviso a metà, «sbiadita» = solo trasparenza.
    """
    d = diametro or px(16)
    swatch = registro_colori.registro().swatch(codice)
    return QIcon(registro_colori.pixmap_swatch(swatch, d, tema_attivo(), sbiadito=sbiadita))


def icona_linea(nome: str, colore_hx: str, d: int | None = None, margine: float = 0.0) -> QIcon:
    """Compatibilità con il codice precedente: delega al sistema SVG del mockup."""
    return icona_svg(nome, colore_hx, d or px(20))


def icona_tessera(testo: str, colore_hx: str, diametro: int | None = None) -> QIcon:
    """Tessera quadrata con una sigla al centro."""
    from PySide6.QtGui import QIcon

    d = diametro or px(34)
    t = tema_attivo()
    img = QPixmap(d, d)

    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(t.bordo), float(max(1, d // 20))))
    p.setBrush(QColor(t.carta2))
    raggio = d // 5
    p.drawRoundedRect(1, 1, d - 2, d - 2, raggio, raggio)
    p.setPen(QPen(QColor(colore_hx)))
    font = QFont("Segoe UI", d // 4)
    font.setBold(True)
    p.setFont(font)
    p.drawText(img.rect(), Qt.AlignmentFlag.AlignCenter, testo)
    p.end()
    return QIcon(img)


# ---------------------------------------------------------------- pulsanti
def bottone(
    testo: str,
    classe: str | None = None,
    dim: str | None = None,
    icona: str | None = None,
    parent: QWidget | None = None,
) -> QPushButton:
    """Pulsante nello stile del mockup.

    ``classe``: None (ghost) | "primario" | "ok" | "pericolo" | "chip" | "link"
    ``dim``: None | "sm" | "lg" | "icona";  ``icona``: nome in ``icone.ICONE``.
    L'icona prende il colore del testo del pulsante (come ``currentColor`` nel mockup).
    """
    t = tema_attivo()
    b = QPushButton(testo, parent)
    if classe:
        b.setProperty("classe", classe)
    if dim:
        b.setProperty("dim", dim)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if icona:
        b.setProperty("nome_icona", icona)
        colore = {
            "primario": t.accento_inchiostro,
            "ok": t.ok_inchiostro,
            "pericolo": t.pericolo_inchiostro,
        }.get(classe or "", t.testo)
        s = {"sm": 13, "lg": 16}.get(dim or "", 16)  # misure ic(...) del mockup
        b.setIcon(icona_svg(icona, colore, ic_px(s)))
        b.setIconSize(QSize(ic_px(s), ic_px(s)))
    return b


def chip(testo: str, campo: QLineEdit, parent: QWidget | None = None) -> QPushButton:
    """Suggerimento rapido: un clic scrive ``testo`` nel ``campo``."""
    b = bottone(testo, classe="chip", parent=parent)
    b.clicked.connect(lambda: (campo.setText(testo), campo.setFocus()))
    return b


# ---------------------------------------------------------------- pillola di stato
class Pillola(QLabel):
    """Badge a pillola con pallino: ``ok`` | ``avviso`` | ``pericolo`` | ``neutro``."""

    def __init__(self, testo: str, variante: str = "neutro", parent: QWidget | None = None) -> None:
        super().__init__(testo, parent)
        self.setObjectName("Pillola")
        self._variante = variante
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def _font(self) -> QFont:
        """Font proprio della pillola. NON usare self.font(): il QSS globale `QWidget{font-size}` lo
        sovrascrive DOPO sizeHint() e il testo risulterebbe più largo della pillola (tagliato)."""
        f = QFont(self.font())
        f.setPixelSize(M.FONT_XS)
        f.setWeight(QFont.Weight.DemiBold)
        return f

    def _colori(self) -> tuple[QColor, QColor]:
        t = tema_attivo()
        primo, velo = {
            "ok": (t.ok, t.ok_vel),
            "avviso": (t.avviso, t.avviso_vel),
            "pericolo": (t.pericolo, t.pericolo_vel),
        }.get(self._variante, (t.testo_dim, t.carta2))
        from .tema import composito_su
        return QColor(primo), composito_su(velo, t.carta)

    def sizeHint(self) -> QSize:
        fm = QFontMetrics(self._font())
        larghezza = M.PILL_PH + M.PILL_PUNTO + rem(0.375) + fm.horizontalAdvance(self.text()) + M.PILL_PH
        return QSize(larghezza, fm.height() + 2 * M.PILL_PV)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def paintEvent(self, _evento) -> None:
        primo, velo = self._colori()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(velo)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        d = float(M.PILL_PUNTO)
        p.setBrush(primo)
        p.drawEllipse(QPointF(M.PILL_PH + d / 2, r.height() / 2), d / 2, d / 2)
        p.setPen(primo)
        p.setFont(self._font())
        testo = QRectF(M.PILL_PH + d + rem(0.375), 0, r.width(), r.height())
        p.drawText(testo, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), self.text())
        p.end()


def pillola(testo: str, variante: str = "neutro") -> Pillola:
    """Compatibilità con il codice esistente."""
    return Pillola(testo, variante)


# ---------------------------------------------------------------- card KPI (icona a sinistra)
class CardKPI(QFrame):
    """Tessera riepilogo del mockup: riquadro icona a sinistra, valore e etichetta a destra.

    ``tono``: "accento" (default) | "bad" (rosso) | "good" (verde). Se la tessera è cliccabile
    emette ``cliccata``.
    """

    cliccata = Signal()

    def __init__(
        self,
        icona: str,
        valore: str,
        etichetta: str,
        tono: str = "accento",
        cliccabile: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("CardKPI")  # il test esistente lo richiede
        self.setProperty("cliccabile", "true" if cliccabile else "false")
        if cliccabile:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._icona_nome = icona
        riga = QHBoxLayout(self)
        riga.setContentsMargins(M.KPI_PH, M.KPI_PV, M.KPI_PH, M.KPI_PV)
        riga.setSpacing(M.KPI_GAP)

        self._ico = QLabel(self)
        self._ico.setObjectName("KpiIco")
        self._ico.setFixedSize(M.KPI_ICO, M.KPI_ICO)
        self._ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        riga.addWidget(self._ico, 0, Qt.AlignmentFlag.AlignVCenter)

        colonna = QVBoxLayout()
        colonna.setContentsMargins(0, 0, 0, 0)
        colonna.setSpacing(2)
        self._valore = QLabel(valore, self)
        self._valore.setObjectName("KpiValore")
        self._etichetta = QLabel(etichetta, self)
        self._etichetta.setObjectName("KpiEtichetta")
        colonna.addWidget(self._valore)
        colonna.addWidget(self._etichetta)
        riga.addLayout(colonna, 1)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.set_tono(tono)

    def set_tono(self, tono: str, icona: str | None = None) -> None:
        self._tono = tono
        t = tema_attivo()
        if icona:
            self._icona_nome = icona
        colore = {"bad": t.pericolo, "good": t.ok}.get(tono, t.accento)
        self._ico.setProperty("tono", tono)
        self._ico.style().unpolish(self._ico)
        self._ico.style().polish(self._ico)
        self._ico.setPixmap(pixmap_icona(self._icona_nome, colore, M.KPI_ICO_SVG))

    def set_valore(self, valore: str) -> None:
        self._valore.setText(valore)

    def set_etichetta(self, etichetta: str) -> None:
        self._etichetta.setText(etichetta)

    def mouseReleaseEvent(self, evento) -> None:
        if self.property("cliccabile") == "true" and evento.button() == Qt.MouseButton.LeftButton:
            self.cliccata.emit()
        super().mouseReleaseEvent(evento)


# ---------------------------------------------------------------- stepper  [-] [ 1 ] [+]
class Stepper(QWidget):
    """Campo numerico con pulsanti − e +. ``campo`` è un QLineEdit con QIntValidator."""

    def __init__(self, valore: int = 1, minimo: int = 1, massimo: int = 99_999_999, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        t = tema_attivo()
        self._minimo, self._massimo = minimo, massimo
        riga = QHBoxLayout(self)
        riga.setContentsMargins(0, 0, 0, 0)
        riga.setSpacing(0)
        self.meno = QPushButton(self)
        self.piu = QPushButton(self)
        for b, nome, lato in ((self.meno, "minus", "sx"), (self.piu, "plus", "dx")):
            b.setProperty("classe", "stepper")
            b.setProperty("lato", lato)
            b.setFixedWidth(M.STEP_BTN)
            b.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)  # alto quanto il campo
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setIcon(icona_svg(nome, t.testo, ic_px(14)))
            b.setIconSize(QSize(ic_px(14), ic_px(14)))
        self.campo = QLineEdit(str(valore), self)
        self.campo.setProperty("classe", "stepper")
        self.campo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.campo.setValidator(QIntValidator(minimo, massimo, self))
        riga.addWidget(self.meno)
        riga.addWidget(self.campo, 1)
        riga.addWidget(self.piu)
        self.meno.clicked.connect(lambda: self._passo(-1))
        self.piu.clicked.connect(lambda: self._passo(+1))


    def _passo(self, delta: int) -> None:
        try:
            v = int(self.campo.text() or 0)
        except ValueError:
            v = self._minimo
        self.campo.setText(str(max(self._minimo, min(self._massimo, v + delta))))


# ---------------------------------------------------------------- messaggio d'errore in linea
class MessaggioErrore(QFrame):
    """Barra rossa con icona di avviso; nascosta finché non c'è un testo."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Messaggio")
        riga = QHBoxLayout(self)
        riga.setContentsMargins(M.MSG_PH, M.MSG_PV, M.MSG_PH, M.MSG_PV)
        riga.setSpacing(rem(0.5))
        self._ico = QLabel(self)
        self._ico.setPixmap(pixmap_icona("alert", tema_attivo().pericolo, ic_px(15)))
        self._testo = QLabel(self)
        self._testo.setWordWrap(True)
        riga.addWidget(self._ico, 0, Qt.AlignmentFlag.AlignTop)
        riga.addWidget(self._testo, 1)
        self.hide()

    def mostra(self, testo: str) -> None:
        era_visibile = self.isVisible()
        self._testo.setText(testo)
        self.setVisible(bool(testo))
        if testo:
            if not era_visibile:
                animazioni.dissolvenza(self, animazioni.DURATA_BREVE)
            # dopo che il layout si è assestato, altrimenti la posizione di partenza è sbagliata
            QTimer.singleShot(0, lambda: animazioni.scuoti(self) if self.isVisible() else None)

    def text(self) -> str:
        return self._testo.text()


# ---------------------------------------------------------------- riquadro anteprima
class Anteprima(QFrame):
    """Riquadro grigio con testo ricco (anteprima giacenza). API come una QLabel: setText/text/clear."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Anteprima")
        riga = QVBoxLayout(self)
        riga.setContentsMargins(M.ANT_PH, M.ANT_PV, M.ANT_PH, M.ANT_PV)
        self._label = QLabel(self)
        self._label.setTextFormat(Qt.TextFormat.RichText)
        self._label.setWordWrap(True)
        riga.addWidget(self._label)

    def setText(self, html: str) -> None:
        self._label.setText(html)

    def text(self) -> str:
        return self._label.text()

    def clear(self) -> None:
        self._label.clear()


# ---------------------------------------------------------------- divisore con testo
def divisore(testo: str, parent: QWidget | None = None) -> QWidget:
    w = QWidget(parent)
    riga = QHBoxLayout(w)
    riga.setContentsMargins(0, 2, 0, M.CAMPO_MB)
    riga.setSpacing(rem(0.625))
    for i in range(2):
        linea = QFrame(w)
        linea.setObjectName("Linea")
        linea.setFixedHeight(1)
        if i == 0:
            riga.addWidget(linea, 1)
            lab = QLabel(testo, w)
            lab.setObjectName("Divisore")
            riga.addWidget(lab)
        else:
            riga.addWidget(linea, 1)
    return w


def campo_con_etichetta(testo: str, widget: QWidget, parent: QWidget | None = None) -> QWidget:
    """Etichetta sopra il campo (``.field`` del mockup): gap 9 px, spazio sotto 21 px."""
    c = QWidget(parent)
    v = QVBoxLayout(c)
    v.setContentsMargins(0, 0, 0, M.CAMPO_MB)
    v.setSpacing(M.CAMPO_GAP)
    lab = QLabel(testo, c)
    lab.setObjectName("Etichetta")
    lab.setWordWrap(True)
    v.addWidget(lab)
    v.addWidget(widget)
    return c


# ---------------------------------------------------------------- ultimi movimenti
_TIPO_MOVIMENTO = {
    "CARICO": ("CARICATO", "ok", "up", "+"),
    "SCARICO": ("SCARICATO", "pericolo", "down", "−"),
    "RETTIFICA": ("RETTIFICA", "avviso", "refresh", "−"),
}


class ListaMovimenti(QWidget):
    """Ultimi movimenti del magazzino (una riga per movimento, come nel mockup).

    ``imposta(movimenti)`` popola la lista; ``toPlainText()`` restituisce le
    righe di testo (compatibilità con i test esistenti).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._v = QVBoxLayout(self)
        self._v.setContentsMargins(0, 0, 0, 0)
        self._v.setSpacing(M.MOV_PV)
        self._vuoto = QLabel("Nessun movimento", self)
        self._vuoto.setObjectName("Debole")
        self._righe: list[QFrame] = []
        self._testi: list[str] = []

    # ------------------------------------------------------------------ API
    def imposta(self, movimenti: list) -> None:
        t = tema_attivo()
        for w in self._righe:
            w.deleteLater()
        self._righe.clear()
        self._testi.clear()
        if self._vuoto.parent() is self:
            self._v.removeWidget(self._vuoto)
            self._vuoto.hide()
        for m in movimenti:
            riga = self._riga(m, t)
            self._righe.append(riga)
            self._v.addWidget(riga)
        if not self._righe:
            self._v.addWidget(self._vuoto)
            self._vuoto.show()

    def toPlainText(self) -> str:
        return "\n".join(self._testi)

    # ------------------------------------------------------------------ riga
    def _riga(self, m, t) -> QFrame:
        from datetime import datetime

        valore = m.tipo.value
        (etichetta, variante, nome_icona, segno) = _TIPO_MOVIMENTO.get(
            valore, (valore, "neutro", "refresh", "")
        )
        colore = {"ok": t.ok, "pericolo": t.pericolo, "avviso": t.avviso}.get(variante, t.testo_dim)
        data_ora = m.data_ora if isinstance(m.data_ora, datetime) else datetime.fromisoformat(m.data_ora)
        from datetime import timezone
        if data_ora.tzinfo is None:
            data_ora = data_ora.replace(tzinfo=timezone.utc)
        ora = data_ora.astimezone().strftime("%d/%m %H:%M %Z")
        pz = m.pezzo
        titolo = f"{pz.profilo.codice} · {pz.colore.nome_visualizzato} · {pz.lunghezza_mm} mm"
        sottotitolo = f"{etichetta} · {m.causale or ''}"

        riga = QFrame()
        riga.setObjectName("RigaMov")
        h = QHBoxLayout(riga)
        h.setContentsMargins(M.MOV_GAP, M.MOV_PV, M.MOV_GAP, M.MOV_PV)
        h.setSpacing(M.MOV_GAP)

        ico = QLabel(riga)
        ico.setObjectName("MovIco")
        ico.setProperty("tono", variante)
        ico.setFixedSize(M.MOV_ICO, M.MOV_ICO)
        ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico.setPixmap(pixmap_icona(nome_icona, colore, ic_px(14)))
        ico.style().unpolish(ico)
        ico.style().polish(ico)
        h.addWidget(ico, 0, Qt.AlignmentFlag.AlignVCenter)

        colonna = QVBoxLayout()
        colonna.setContentsMargins(0, 0, 0, 0)
        colonna.setSpacing(1)
        lab_t = QLabel(titolo, riga)
        lab_t.setObjectName("MovTitolo")
        lab_s = QLabel(sottotitolo, riga)
        lab_s.setObjectName("MovSotto")
        lab_s.setTextFormat(Qt.TextFormat.PlainText)  # la causale va mostrata come testo
        colonna.addWidget(lab_t)
        colonna.addWidget(lab_s)
        h.addLayout(colonna, 1)

        destra = QVBoxLayout()
        destra.setContentsMargins(0, 0, 0, 0)
        destra.setSpacing(1)
        lab_q = QLabel(f"{segno} {m.quantita}", riga)
        lab_q.setObjectName("MovQta")
        lab_q.setProperty("tono", variante)
        f = QFont(lab_q.font())
        f.setWeight(QFont.Weight.DemiBold)
        lab_q.setFont(f)
        lab_q.style().unpolish(lab_q)
        lab_q.style().polish(lab_q)
        lab_o = QLabel(ora, riga)
        lab_o.setObjectName("MovOra")
        lab_o.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        lab_q.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        destra.addWidget(lab_q)
        destra.addWidget(lab_o)
        h.addLayout(destra)

        causale = m.causale or ""
        self._testi.append(f"{etichetta} {segno} {m.quantita} — {titolo}" + (f" · {causale}" if causale else ""))
        return riga


# ---------------------------------------------------------------- toast
_ICONE_TOAST = {"ok": "check", "warn": "alert", "info": "info", "danger": "alert"}
_COLORE_TOAST = {}  # riempito al volo dal tema


class Toast(QFrame):
    """Notifica in basso a destra della finestra; si chiude da sola dopo ~4,5 s.

    ``tono``: "ok" | "warn" | "info" | "danger".
    """

    DURATA_MS = 4500
    MASSIMO_VISIBILI = 3

    def __init__(self, testo: str, tono: str = "ok", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setProperty("tono", tono)
        t = tema_attivo()
        riga = QHBoxLayout(self)
        riga.setContentsMargins(M.MOV_GAP, M.TD_PV, M.MOV_GAP, M.TD_PV)
        riga.setSpacing(M.MOV_GAP)
        self._ico = QLabel(self)
        self._ico.setPixmap(pixmap_icona(_ICONE_TOAST.get(tono, "info"), t.testo, ic_px(14)))
        self._testo = QLabel(testo, self)
        riga.addWidget(self._ico, 0, Qt.AlignmentFlag.AlignVCenter)
        riga.addWidget(self._testo, 1)
        chiudi = QPushButton(self)
        chiudi.setProperty("classe", "link")
        chiudi.setIcon(icona_svg("x", t.testo_dim, ic_px(12)))
        chiudi.setIconSize(QSize(ic_px(12), ic_px(12)))
        chiudi.setFixedSize(M.STEP_BTN, M.STEP_BTN)
        chiudi.clicked.connect(self.chiudi)
        riga.addWidget(chiudi, 0, Qt.AlignmentFlag.AlignVCenter)
        self.setMaximumWidth(M.TOAST_MAXW)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def mostra(self, finestra: QWidget) -> None:
        if self.parent() is not finestra:
            self.setParent(finestra)
        self.style().unpolish(self)
        self.style().polish(self)
        self.adjustSize()
        x = finestra.width() - M.TOAST_DX - self.width()
        y = finestra.height() - M.TOAST_BASSO - self.height()
        self.move(max(0, x), max(0, y))
        self.show()
        QTimer.singleShot(self.DURATA_MS, self.chiudi)

    def entra(self) -> None:
        """Ingresso animato (solo alla prima comparsa: ``mostra`` viene richiamato anche al resize)."""
        animazioni.entra_da_destra(self)

    def chiudi(self) -> None:
        try:
            animazioni.esci_e_chiudi(self)
        except RuntimeError:  # widget già distrutto (timer scaduto dopo una chiusura manuale)
            pass
