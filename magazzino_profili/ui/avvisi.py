"""Scheda Avvisi: pezzi esauriti o sotto scorta minima.

- "Dettagli" emette :attr:`vai_a_colore` con l'id del colore del pezzo:
  la finestra principale passa alla scheda Inventario e seleziona la
  scheda colore corrispondente (azzera ricerca e combo).
- "Carica" emette :attr:`vai_a_scheda` con ``("Carico", barcode)``:
  la finestra principale passa alla scheda Carico con il barcode compilato.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..services import consultazione
from .componenti import bottone
from . import animazioni
from .icone import ic_px, pixmap_icona
from .tema import M, rem, tema_attivo


class _MeterBarra(QFrame):
    """Barra di avanzamento: la larghezza è una frazione della barra."""

    def __init__(self, frazione: float, gravita: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MeterBarra")
        self.setProperty("gravita", gravita)
        self._frazione = max(0.0, min(1.0, frazione))
        self._frazione_finale = self._frazione
        self._animata = False
        self.setFixedHeight(M.METER_H)
        self.setMaximumWidth(M.METER_MAXW)
        self.style().unpolish(self)
        self.style().polish(self)

    def _aggiorna(self) -> None:
        sfondo_larghezza = self.parent().width() if self.parent() else self.width()
        self.setFixedWidth(int(round(sfondo_larghezza * self._frazione)))

    def _imposta(self, v: float) -> None:
        self._frazione = v
        self._aggiorna()

    def showEvent(self, evento) -> None:  # noqa: N802
        super().showEvent(evento)
        if not self._animata:  # la barra "cresce" solo alla prima comparsa
            self._animata = True
            animazioni.anima_valore(0.0, self._frazione_finale, self._imposta, animazioni.DURATA_LUNGA, ritardo=120)

    def resizeEvent(self, _evento) -> None:  # noqa: N802
        self._aggiorna()
        super().resizeEvent(_evento)


def _riga_avviso(
    z,  # noqa: ANN001 - modello di dominio (Pezzo)
    scheda: "SchedaAvvisi",
    parent: QWidget,
) -> QFrame:
    """Una riga ``QFrame#RigaAvviso`` per un pezzo da riordinare."""
    t = tema_attivo()
    stato = consultazione.stato_scorta(z)
    etichetta = "Esaurito" if stato == "esaurito" else "Sotto scorta"
    colore = z.colore.nome_visualizzato or z.colore.codice_normalizzato
    lunghezza = f"{z.lunghezza_mm:,}".replace(",", ".") if z.lunghezza_mm else "—"
    titolo = f"{z.profilo.codice} · {colore} · {lunghezza} mm — {etichetta}"

    sotto = [z.profilo.descrizione or ""]
    if z.ubicazione:
        sotto.append(z.ubicazione)
    if z.quantita:
        sotto.append(f"{z.quantita} {'pezzo' if z.quantita == 1 else 'pezzi'} rimasti")
    else:
        sotto.append("nessun pezzo disponibile")

    riga = QFrame(parent)
    riga.setObjectName("RigaAvviso")
    riga.setProperty("gravita", "pericolo")  # nel mockup anche "Sotto scorta" è rosso

    h = QHBoxLayout(riga)
    h.setContentsMargins(M.AVV_PH, M.AVV_PV, M.AVV_PH, M.AVV_PV)
    h.setSpacing(M.GAP)

    ico = QLabel(riga)
    ico.setObjectName("AvvIco")
    ico.setFixedSize(M.AVV_ICO, M.AVV_ICO)
    ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
    ico.setPixmap(pixmap_icona("alert", t.pericolo, ic_px(26)))
    h.addWidget(ico, 0, Qt.AlignmentFlag.AlignVCenter)

    colonna = QVBoxLayout()
    colonna.setContentsMargins(0, 0, 0, 0)
    colonna.setSpacing(rem(0.25))
    lab_t = QLabel(titolo, riga)
    lab_t.setObjectName("AvvTitolo")
    lab_s = QLabel(" · ".join(s for s in sotto if s), riga)
    lab_s.setObjectName("AvvSotto")
    lab_s.setTextFormat(Qt.TextFormat.PlainText)
    colonna.addWidget(lab_t)
    colonna.addWidget(lab_s)

    scorta = z.scorta_minima
    frazione = (z.quantita / scorta) if (scorta and scorta > 0 and z.quantita) else 0.0
    sfondo = QFrame(riga)
    sfondo.setObjectName("MeterSfondo")
    sfondo.setFixedHeight(M.METER_H)
    sfondo.setMaximumWidth(M.METER_MAXW)
    barra = _MeterBarra(frazione, "pericolo", sfondo)
    sfondo_lay = QHBoxLayout(sfondo)
    sfondo_lay.setContentsMargins(0, 0, 0, 0)
    sfondo_lay.addWidget(barra)
    sfondo_lay.addStretch(1)
    colonna.addWidget(sfondo)
    h.addLayout(colonna, 1)

    btn_dettagli = bottone("Dettagli", dim="sm", parent=riga)
    btn_dettagli.clicked.connect(lambda _c=False, cid=z.colore.id: scheda.vai_a_colore.emit(cid))
    btn_carica = bottone("Carica", "ok", "sm", "up", riga)
    btn_carica.clicked.connect(
        lambda _c=False, bc=z.barcode or "": scheda.vai_a_scheda.emit("Carico", bc)
    )
    h.addWidget(btn_dettagli, 0, Qt.AlignmentFlag.AlignVCenter)
    h.addWidget(btn_carica, 0, Qt.AlignmentFlag.AlignVCenter)
    return riga


class SchedaAvvisi(QWidget):
    """Righe dei pezzi da riordinare (esauriti o sotto scorta)."""

    #: emesso da "Dettagli" di una riga: id del colore del pezzo
    vai_a_colore = Signal(int)
    #: emesso da "Carica" di una riga: nome scheda e barcode
    vai_a_scheda = Signal(str, str)

    def __init__(self, factory, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._factory = factory

        root = QVBoxLayout(self)
        root.setContentsMargins(M.PAG_H, M.PAG_T, M.PAG_H, M.PAG_B)
        root.setSpacing(M.GAP)

        # intestazione
        intest = QFrame(self)
        intest.setObjectName("Card")
        vi = QVBoxLayout(intest)
        vi.setContentsMargins(M.CARD_PAD, M.CARD_PAD, M.CARD_PAD, M.CARD_PAD)
        vi.setSpacing(rem(0.375))
        h = QHBoxLayout()
        h.setSpacing(M.GAP)
        colonna = QVBoxLayout()
        colonna.setContentsMargins(0, 0, 0, 0)
        colonna.setSpacing(rem(0.25))
        titolo = QLabel("Avvisi scorte", intest)
        titolo.setObjectName("TitoloCard")
        self.contatore = QLabel(intest)
        self.contatore.setObjectName("Dim")
        colonna.addWidget(titolo)
        colonna.addWidget(self.contatore)
        h.addLayout(colonna, 1)
        self.aggiorna_btn = bottone("Aggiorna", icona="refresh", parent=intest)
        self.aggiorna_btn.clicked.connect(self.aggiorna)
        h.addWidget(self.aggiorna_btn)
        vi.addLayout(h)
        root.addWidget(intest)

        # lista avvisi (scroll)
        self._corpo = QWidget(self)
        self._v_corpo = QVBoxLayout(self._corpo)
        self._v_corpo.setContentsMargins(0, 0, 0, 0)
        self._v_corpo.setSpacing(M.GAP_SM)
        area = QScrollArea(self)
        area.setWidgetResizable(True)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        area.setContentsMargins(0, 0, 0, 0)
        area.setWidget(self._corpo)
        root.addWidget(area, 1)

        # segnaposto vuoto
        self._vuoto = QFrame(self._corpo)
        self._vuoto.setObjectName("Card")
        vv = QVBoxLayout(self._vuoto)
        vv.setContentsMargins(rem(3.0), rem(3.0), rem(3.0), rem(3.0))
        vv.setSpacing(rem(0.5))
        ico = QLabel(self._vuoto)
        t = tema_attivo()
        ico.setPixmap(pixmap_icona("check", t.ok, ic_px(34)))
        ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lab_t = QLabel("Nessun avviso", self._vuoto)
        lab_t.setObjectName("AvvTitolo")
        lab_s = QLabel("Tutte le referenze sono sopra la soglia di scorta.", self._vuoto)
        lab_s.setObjectName("AvvSotto")
        for w in (ico, lab_t, lab_s):
            w.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vv.addWidget(ico)
        vv.addWidget(lab_t)
        vv.addWidget(lab_s)
        vv.addStretch(1)
        self._v_corpo.addWidget(self._vuoto)
        self._v_corpo.addStretch(1)  # le righe NON devono allungarsi a tutta l'altezza

        self.aggiorna()

    # ------------------------------------------------------------------
    def _vuole_mostrare(self) -> None:
        """Crea/rigenera le righe (chiamato da ``aggiorna``)."""
        sessione = self._factory()
        try:
            lista = consultazione.pezzi_da_riordinare(sessione)
        finally:
            sessione.close()

        # rimuovi le righe precedenti
        i = 0
        while i < self._v_corpo.count():
            voce = self._v_corpo.itemAt(i)
            if voce is not None:
                w = voce.widget()
                if isinstance(w, QFrame) and w.objectName() == "RigaAvviso":
                    self._v_corpo.removeWidget(w)
                    w.deleteLater()
                    continue
            i += 1

        for z in lista:
            riga = _riga_avviso(z, self, self._corpo)
            self._v_corpo.insertWidget(self._v_corpo.count() - 1, riga)  # prima dello stretch

        n = len(lista)
        self._vuoto.setVisible(n == 0)
        if n == 0:
            self.contatore.setText("Nessun avviso: tutte le giacenze sono sopra la scorta minima.")
        else:
            self.contatore.setText(
                f"{n} {'pezzo' if n == 1 else 'pezzi'} da riordinare (esauriti o sotto scorta)."
            )

    def aggiorna(self) -> None:
        self._vuole_mostrare()
