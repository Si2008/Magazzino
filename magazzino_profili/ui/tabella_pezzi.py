"""Scheda Inventario: card KPI, chip colore, tabella e pannello laterale.

Layout (come nel mockup):

- riga di 4 card KPI (pezzi a magazzino, referenze, peso complessivo,
  da riordinare/scorte ok — l'ultima è cliccabile e attiva il filtro);
- chip colore: "Tutti" + un chip per colore con pallino e conteggio;
- card tabella: barra strumenti (cerca, Profilo, Ubicazione, Stato,
  Azzera), tabella unica, piè di pagina "N di M referenze";
- pannello laterale: senza selezione mostra "Nessun pezzo selezionato"
  e gli ultimi movimenti; con una riga selezionata mostra il pezzo
  (barcode, dettagli, movimenti) e pulsanti Carica/Scarica/etichetta.

La colonna Barcode resta la colonna 0 del contratto ma è nascosta
(non compare nel mockup). Dopo un carico/scarico la scheda selezionata
resta invariata: :func:`TabellaPezzi.aggiorna` ricostruisce le tab
conservando la selezione corrente.
"""

from __future__ import annotations

import logging
import os
import tempfile
from decimal import Decimal

from sqlalchemy.exc import SQLAlchemyError

from PySide6.QtCore import QEvent, QRect, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QStyle,
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QStyledItemDelegate,
    QTabBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..services import consultazione, impostazioni
from . import animazioni, tema
from .tema import M, colore_di_codice, rem, tema_attivo
from .icone import ic_px, icona_svg, pixmap_icona
from .componenti import (
    CardKPI,
    ListaMovimenti,
    Pillola,
    bottone,
    icona_colore,
    icona_tessera,
)

_COLONNE = ["Barcode", "Profilo", "Colore", "Lunghezza", "Pezzi", "Peso tot.", "Ubicazione", "Stato"]
_COLORE = 2  # indice colonna "Colore" (contratto test: item(0, 2))
_BARCODE = 0
_TUTTE_UBICAZIONI = "Tutte le ubicazioni"

_STATI_COMBO = [
    ("Stato: tutti", None),
    ("Stato: OK", "ok"),
    ("Stato: sotto scorta", "sotto"),
    ("Stato: esauriti", "esaurito"),
    ("Stato: da riordinare", "riordino"),
]

_STATO_INFO = {
    "ok": ("OK", "ok"),
    "sotto": ("Sotto scorta", "pericolo"),
    "esaurito": ("Esaurito", "pericolo"),
}


logger = logging.getLogger(__name__)


def _testo_peso(peso: Decimal | float) -> str:
    """Peso in formato italiano: ≥ 1000 kg → "3,4 t", altrimenti "112,5 kg"."""
    peso = Decimal(str(peso or 0))
    if peso >= 1000:
        valore = f"{float(peso) / 1000.0:,.1f}"
        unita = "t"
    elif peso == peso.to_integral_value():
        valore = f"{int(peso):,}"
        unita = "kg"
    else:
        valore = f"{float(peso):,.1f}"
        unita = "kg"
    return valore.replace(",", "@").replace(".", ",").replace("@", ".") + " " + unita


class DelegatoProfilo(QStyledItemDelegate):
    """Colonna Profilo: codice in grassetto sopra la descrizione (testo_dim).

    La riga selezionata mostra una barra verticale ``t.accento`` larga 3 px
    sul bordo sinistro (il QSS non può fare inset box-shadow).
    """

    def paint(self, painter, option, index) -> None:
        t = tema_attivo()
        testo = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        descrizione = str(index.data(Qt.ItemDataRole.UserRole + 1) or "")
        codice = testo.split(" — ", 1)[0] if " — " in testo else testo

        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor(t.accento_vel))
            painter.fillRect(option.rect.x(), option.rect.y(), 3, option.rect.height(), QColor(t.accento))

        riga = option.rect.adjusted(M.TD_PH, 0, -M.TD_PH // 2, 0)  # stesso padding delle altre colonne
        painter.setPen(QColor(t.bordo))
        painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())  # linea di riga come QSS ::item
        fm = painter.fontMetrics()
        if descrizione:
            y = riga.y() + max(0, (riga.height() - fm.height() * 2) // 2)
            f = painter.font()
            f.setBold(True)
            painter.setFont(f)
            painter.setPen(QColor(t.testo))
            painter.drawText(riga.x(), y, riga.width(), fm.height(),
                             int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                             fm.elidedText(codice, Qt.TextElideMode.ElideRight, riga.width()))
            painter.setPen(QColor(t.testo_dim))
            f.setBold(False)
            f.setPixelSize(M.FONT_SMALL)
            painter.setFont(f)
            fm2 = painter.fontMetrics()
            painter.drawText(riga.x(), y + fm.height() + 1, riga.width(), fm.height(),
                             int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                             fm2.elidedText(descrizione, Qt.TextElideMode.ElideRight, riga.width()))
        else:
            painter.setPen(QColor(t.testo))
            f = painter.font()
            f.setBold(True)
            painter.setFont(f)
            painter.drawText(riga, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), codice)

    def sizeHint(self, option, index) -> "object":
        return super().sizeHint(option, index)


class DelegatoColore(QStyledItemDelegate):
    """Colonna Colore: pallino (colore_di_codice) + nome."""

    def paint(self, painter, option, index) -> None:
        t = tema_attivo()
        nome = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        codice = str(index.data(Qt.ItemDataRole.UserRole + 1) or "")
        hx = colore_di_codice(codice) if codice else t.testo_dim
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor(t.accento_vel))
        painter.setPen(QColor(t.bordo))
        painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())
        d = int(M.PILL_PUNTO) + ic_px(1)
        cx = option.rect.x() + M.TD_PH
        cy = option.rect.y() + option.rect.height() // 2 - d // 2
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)  # noqa
        painter.setPen(QPen(QColor(t.bordo_campo), 1))
        painter.setBrush(QColor(hx))
        painter.drawEllipse(cx, cy, d, d)
        painter.setPen(QColor(t.testo))
        painter.drawText(
            option.rect.adjusted(int(M.TD_PH + d + rem(0.5)), 0, -2, 0),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            nome,
        )


def _cella_pillola(testo: str, variante: str) -> QWidget:
    """Badge di stato centrato nella cella (la cella resta cliccabile)."""
    contenitore = QWidget()
    contenitore.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    riga = QHBoxLayout(contenitore)
    riga.setContentsMargins(rem(0.375), rem(0.25), rem(0.375), rem(0.25))
    riga.addWidget(Pillola(testo, variante), 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    return contenitore


class TabellaPezzi(QWidget):
    """Scheda Inventario con card KPI, chip colore, tabella e pannello laterale."""

    cambiato = Signal()  # emesso dopo ogni aggiornamento completo
    vai_a_scheda = Signal(str, str)  # (nome scheda, barcode)

    def __init__(self, factory, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._factory = factory
        # Soglia globale di sotto scorta (rilessa in ``aggiorna``).
        self._soglia = impostazioni.SOGLIA_DEFAULT
        self._colore_selezionato: int | None = None  # None = "Tutti"
        self._id_tab: list[int | None] = []
        self._barcode_selezionato: str | None = None
        self._liste_mov: list = []

        root = QVBoxLayout(self)
        root.setContentsMargins(M.PAG_H, M.PAG_T, M.PAG_H, M.PAG_B)
        root.setSpacing(M.GAP)

        root.addLayout(self._costruisci_kpi())
        self._tabbar = self._costruisci_tabbar()
        root.addWidget(self._tabbar)

        riga = QHBoxLayout()
        riga.setContentsMargins(0, 0, 0, 0)
        riga.setSpacing(M.GAP)
        riga.addWidget(self._costruisci_card_tabella(), 1)
        riga.addWidget(self._costruisci_laterale(), 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(riga, 1)

        self._tabbar.currentChanged.connect(self._su_cambio_tab)
        self.cerca.textChanged.connect(lambda _t: self._rinfresca_tabella())
        self.combo_ubicazione.editTextChanged.connect(lambda _t: self._rinfresca_tabella())
        for c in (self.combo_profilo, self.combo_stato):
            c.currentIndexChanged.connect(lambda _i: self._rinfresca_tabella())

        self.aggiorna()

    # ------------------------------------------------------------------
    # KPI
    # ------------------------------------------------------------------
    def _costruisci_kpi(self) -> QHBoxLayout:
        h = QHBoxLayout()
        h.setSpacing(M.GAP_SM)

        self.kpi_pezzi = CardKPI("layers", "0", "Pezzi a magazzino")
        self.kpi_profili = CardKPI("tag", "0", "Referenze")
        self.kpi_peso = CardKPI("weight", "0 kg", "Peso complessivo")
        self.kpi_riordino = CardKPI("alert", "0", "Da riordinare", "bad", cliccabile=True)
        self.kpi_riordino.cliccata.connect(self._filtrare_da_riordinare)

        for card in (self.kpi_pezzi, self.kpi_profili, self.kpi_peso, self.kpi_riordino):
            h.addWidget(card, 1)
        return h

    def _filtrare_da_riordinare(self) -> None:
        i = self.combo_stato.findData("riordino")
        if i >= 0:
            self.combo_stato.setCurrentIndex(i)

    def _aggiorna_kpi(self, r: dict) -> None:
        # i numeri "salgono" dal valore precedente (a fine corsa il testo è esattamente quello di prima)
        animazioni.conta_su(self.kpi_pezzi, int(r["pezzi_totali"]), lambda v: f"{int(v):,}")
        animazioni.conta_su(self.kpi_profili, int(r["referenze"]), lambda v: f"{int(v):,}")
        animazioni.conta_su(self.kpi_peso, float(r["peso_kg"] or 0), _testo_peso)
        n_riordino = int(r["da_riordinare"])
        animazioni.conta_su(self.kpi_riordino, n_riordino, lambda v: f"{int(v):,}")
        if n_riordino > 0:
            self.kpi_riordino.set_tono("bad", "alert")
            self.kpi_riordino.set_etichetta("Da riordinare")
        else:
            self.kpi_riordino.set_tono("good", "check")
            self.kpi_riordino.set_etichetta("Scorte ok")

    # ------------------------------------------------------------------
    # chip colore
    # ------------------------------------------------------------------
    def _costruisci_tabbar(self) -> QTabBar:
        bar = QTabBar(self)
        bar.setObjectName("TabColori")  # lo stile è nel QSS globale
        bar.setExpanding(False)
        bar.setDrawBase(False)
        bar.setUsesScrollButtons(True)
        bar.setElideMode(Qt.TextElideMode.ElideNone)
        return bar

    def _aggiorna_tab_colori(self, colori: list) -> None:
        bar = self._tabbar
        precedente = self._colore_selezionato
        bar.blockSignals(True)
        while bar.count():
            bar.removeTab(0)
        self._id_tab = []

        bar.addTab(icona_tessera("T", tema_attivo().testo_dim), "Tutti")
        self._id_tab.append(None)

        for colore, referenze, _pezzi in colori:
            nome = colore.nome_visualizzato or colore.codice_normalizzato
            etichetta = f"{nome} ({referenze})"
            icone = icona_colore(colore.codice_normalizzato, sbiadita=(referenze == 0))
            bar.addTab(icone, etichetta)
            self._id_tab.append(colore.id)

        indice = 0
        if precedente is not None and precedente in self._id_tab:
            indice = self._id_tab.index(precedente)
        bar.setCurrentIndex(indice)
        self._colore_selezionato = self._id_tab[indice]
        bar.blockSignals(False)
        self._applica_colonna_colore()

    # ------------------------------------------------------------------
    # card tabella
    # ------------------------------------------------------------------
    def _costruisci_card_tabella(self) -> QWidget:
        t = tema_attivo()
        card = QFrame(self)
        card.setObjectName("Card")
        v = QVBoxLayout(card)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        barra = QFrame(card)
        barra.setObjectName("BarraStrumenti")
        h = QHBoxLayout(barra)
        h.setContentsMargins(M.TOOLBAR_PAD, M.TOOLBAR_PAD, M.TOOLBAR_PAD, M.TOOLBAR_PAD)
        h.setSpacing(M.TOOLBAR_GAP)

        self.cerca = QLineEdit(barra)
        self.cerca.setPlaceholderText("Cerca per profilo, colore, barcode, ubicazione…")
        self.cerca.setClearButtonEnabled(True)
        self.cerca.setMinimumWidth(rem(12.5))
        self.cerca.addAction(icona_svg("search", t.testo_debole, ic_px(15)), QLineEdit.ActionPosition.LeadingPosition)
        h.addWidget(self.cerca, 3)

        self.combo_profilo = QComboBox(barra)
        h.addWidget(self.combo_profilo)

        self.combo_ubicazione = QComboBox(barra)
        self.combo_ubicazione.setEditable(True)
        self.combo_ubicazione.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.combo_ubicazione.lineEdit().setPlaceholderText("Ubicazione")
        h.addWidget(self.combo_ubicazione)

        self.combo_stato = QComboBox(barra)
        for etichetta, valore in _STATI_COMBO:
            self.combo_stato.addItem(etichetta, valore)
        h.addWidget(self.combo_stato)

        self.azzera = bottone("Azzera", icona="refresh", parent=barra)
        self.azzera.clicked.connect(self._azzera_filtri)
        h.addWidget(self.azzera)
        # i filtri si accorciano invece di sovrapporsi alla ricerca quando la card è stretta
        for combo in (self.combo_profilo, self.combo_ubicazione, self.combo_stato):
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(11)
            combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.cerca.setMinimumWidth(rem(10))

        v.addWidget(barra)
        v.addWidget(self._costruisci_tabella(), 1)

        self._footer = QLabel(card)
        self._footer.setObjectName("Piede")
        v.addWidget(self._footer)

        # vuoto centrato (lista vuota con filtri attivi)
        self._vuoto = QWidget(card)
        self._vuoto.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        vv = QVBoxLayout(self._vuoto)
        vv.setContentsMargins(0, 0, 0, 0)
        vv.setSpacing(M.GAP_SM)
        lab = QLabel("Nessun risultato — Prova a modificare la ricerca o i filtri.", self._vuoto)
        lab.setObjectName("Debole")
        lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn = bottone("Azzera filtri", icona="refresh", parent=self._vuoto)
        btn.clicked.connect(self._azzera_filtri)
        vv.addWidget(lab)
        vv.addWidget(btn, 0, Qt.AlignmentFlag.AlignCenter)
        self._vuoto.hide()

        self._tabella.viewport().installEventFilter(self)
        return card

    def _costruisci_tabella(self) -> QTableWidget:
        self._tabella = QTableWidget(0, len(_COLONNE), self)
        tab = self._tabella
        tab.setHorizontalHeaderLabels([s.upper() for s in _COLONNE])
        tab.verticalHeader().setVisible(False)
        tab.setAlternatingRowColors(False)
        tab.setShowGrid(False)
        tab.setMouseTracking(True)
        tab.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tab.setSelectionBehavior(QAbstractItemView.SelectRows)
        tab.setSelectionMode(QAbstractItemView.SingleSelection)
        tab.setSortingEnabled(False)
        tab.setWordWrap(False)
        tab.verticalHeader().setDefaultSectionSize(M.RIGA_INV)
        header = tab.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Profilo assorbe lo spazio
        header.setMinimumSectionSize(rem(3))
        header.setStretchLastSection(False)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        # larghezza = pillola più lunga ("Sotto scorta") + margini della cella, qualunque sia il font
        tab.setColumnWidth(7, Pillola("Sotto scorta", "pericolo").sizeHint().width() + 2 * rem(0.375) + M.TD_PH)
        tab.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        tab.setItemDelegateForColumn(1, DelegatoProfilo(tab))
        tab.setItemDelegateForColumn(_COLORE, DelegatoColore(tab))
        tab.itemSelectionChanged.connect(self._su_selezione)
        return tab

    def eventFilter(self, oggetto, evento) -> bool:
        if oggetto is self._tabella.viewport() and evento.type() == QEvent.Type.Resize:
            self._centra_vuoto()
        return super().eventFilter(oggetto, evento)

    def _centra_vuoto(self) -> None:
        if not self._vuoto.isVisible():
            return
        vp = self._tabella.viewport()
        self._vuoto.adjustSize()
        x = max(0, (vp.width() - self._vuoto.width()) // 2)
        y = max(0, (vp.height() - self._vuoto.height()) // 2)
        self._vuoto.move(x, y)
        self._vuoto.raise_()

    # ------------------------------------------------------------------
    # pannello laterale
    # ------------------------------------------------------------------
    def _costruisci_laterale(self) -> QFrame:
        card = QFrame(self)
        card.setObjectName("Card")
        card.setFixedWidth(M.ASIDE_W)
        card.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Maximum)
        v = QVBoxLayout(card)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        self._pannello = QWidget(card)
        self._pannello_l = QVBoxLayout(self._pannello)
        self._pannello_l.setContentsMargins(0, 0, 0, 0)
        self._pannello_l.setSpacing(0)
        v.addWidget(self._pannello)
        v.addStretch(1)
        return card

    def _sezioni_laterali(self) -> None:
        """Ricostruisce il pannello laterale (selezione corrente)."""
        while self._pannello_l.count():
            elemento = self._pannello_l.takeAt(0)
            w = elemento.widget()
            if w is not None:
                w.deleteLater()
        self._riempi_laterale()

    def _riempi_laterale(self) -> None:
        t = tema_attivo()
        barcode = self._barcode_selezionato
        pezzo = None
        if barcode:
            sessione = self._factory()
            try:
                pezzo = consultazione.pezzo_per_barcode(sessione, barcode)
            finally:
                sessione.close()

        if pezzo is None:
            self._sezione_vuota()
            self._sezione_movimenti("ULTIMI MOVIMENTI", None, 5)
            return

        # --- sezione 1: identificativo + barcode
        s1 = QFrame(self._pannello)
        s1.setObjectName("Lat")
        v1 = QVBoxLayout(s1)
        v1.setContentsMargins(M.LAT_PH, M.LAT_PV, M.LAT_PH, M.LAT_PV)
        v1.setSpacing(M.GAP_SM)

        riga = QHBoxLayout()
        riga.setContentsMargins(0, 0, 0, 0)
        riga.setSpacing(M.GAP_SM)
        colonna = QVBoxLayout()
        colonna.setContentsMargins(0, 0, 0, 0)
        colonna.setSpacing(1)
        codice = QLabel(pezzo.profilo.codice or "", s1)
        codice.setObjectName("LatTitolo")
        descrizione = QLabel(pezzo.profilo.descrizione or "", s1)
        descrizione.setObjectName("Dim")
        colonna.addWidget(codice)
        colonna.addWidget(descrizione)
        riga.addLayout(colonna, 1)
        stato = consultazione.stato_scorta(pezzo, self._soglia)
        testo_stato, variante = _STATO_INFO.get(stato, ("OK", "ok"))
        riga.addWidget(Pillola(testo_stato, variante), 0, Qt.AlignmentFlag.AlignTop)
        v1.addLayout(riga)

        cb = QFrame(s1)
        cb.setObjectName("CasellaBarcode")
        vc = QVBoxLayout(cb)
        vc.setContentsMargins(M.GAP_SM, M.GAP_SM, M.GAP_SM, M.GAP_SM)
        vc.setSpacing(M.GAP_SM)
        img = QLabel(cb)
        img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        try:
            percorso = os.path.join(tempfile.gettempdir(), "magazzino_profili_bc", f"bc_{abs(hash(barcode))}.png")
            os.makedirs(os.path.dirname(percorso), exist_ok=True)
            from ..barcode import generazione as bc_gen

            bc_gen.genera_immagine_barcode(barcode, percorso)
            img.setPixmap(QPixmap(percorso))
        # ``genera_immagine_barcode`` documenta ValueError; i guasti di
        # Pillow/ImageWriter non sono esaustibili: si mantiene il catch largo
        # e si registra il traceback (B-03).
        except Exception:
            logger.exception("Generazione immagine barcode non riuscita")
            img.clear()
        lab_bc = QLabel(barcode or "", cb)
        lab_bc.setObjectName("Debole")
        lab_bc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if img.pixmap() is not None:
            vc.addWidget(img)
        vc.addWidget(lab_bc)
        v1.addWidget(cb)
        self._pannello_l.addWidget(s1)

        # --- sezione DETTAGLI
        s2 = QFrame(self._pannello)
        s2.setObjectName("Lat")
        v2 = QVBoxLayout(s2)
        v2.setContentsMargins(M.LAT_PH, M.LAT_PV, M.LAT_PH, M.LAT_PV)
        v2.setSpacing(M.GAP_SM)
        titolo2 = QLabel("DETTAGLI", s2)
        titolo2.setObjectName("LatSezione")
        v2.addWidget(titolo2)

        griglia = QGridLayout()
        griglia.setContentsMargins(0, 0, 0, 0)
        griglia.setHorizontalSpacing(M.GAP)
        griglia.setVerticalSpacing(M.GAP_SM)
        righe = [
            ("Colore", self._etichetta_colore(pezzo)),
            ("Lunghezza", f"{pezzo.lunghezza_mm:,}".replace(",", "X").replace(".", ",").replace("X", ".") + " mm"),
            ("Giacenza", f"{pezzo.quantita or 0} pezzi"),
            ("Peso unitario", _testo_peso(consultazione.peso_unitario_kg(pezzo))),
            ("Peso totale", _testo_peso(consultazione.peso_totale_kg(pezzo))),
            ("Ubicazione", pezzo.ubicazione or "—"),
        ]
        for i, (etichetta, valore) in enumerate(righe):
            lab_e = QLabel(etichetta, s2)
            lab_e.setObjectName("Debole")
            griglia.addWidget(lab_e, i, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            griglia.addWidget(valore, i, 1, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        v2.addLayout(griglia)

        pulsanti = QGridLayout()
        pulsanti.setContentsMargins(0, 0, 0, 0)
        pulsanti.setSpacing(M.GAP_SM)
        carica = bottone("Carica", "ok", icona="up", parent=s2)
        scarica = bottone("Scarica", "pericolo", icona="down", parent=s2)
        carica.clicked.connect(lambda: self.vai_a_scheda.emit("Carico", barcode or ""))
        scarica.clicked.connect(lambda: self.vai_a_scheda.emit("Scarico", barcode or ""))
        etichetta_pdf = bottone("Stampa etichetta", icona="printer", parent=s2)
        etichetta_pdf.clicked.connect(lambda: self._stampa_etichetta(barcode))
        pulsanti.addWidget(carica, 0, 0)
        pulsanti.addWidget(scarica, 0, 1)
        pulsanti.addWidget(etichetta_pdf, 1, 0, 1, 2)
        v2.addLayout(pulsanti)
        self._pannello_l.addWidget(s2)

        # --- sezione MOVIMENTI DI QUESTO PEZZO
        self._sezione_movimenti("MOVIMENTI DI QUESTO PEZZO", pezzo.id, 4)

    def _etichetta_colore(self, pezzo) -> QLabel:
        lab = QLabel(pezzo.colore.nome_visualizzato or pezzo.colore.codice_normalizzato, self._pannello)
        return lab

    def _sezione_vuota(self) -> None:
        t = tema_attivo()
        s = QFrame(self._pannello)
        s.setObjectName("Lat")
        v = QVBoxLayout(s)
        v.setContentsMargins(M.LAT_PH, M.LAT_PV, M.LAT_PH, M.LAT_PV)
        v.setSpacing(M.GAP_SM)
        img = QLabel(s)
        img.setFixedSize(M.AVV_ICO, M.AVV_ICO)
        img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img.setPixmap(pixmap_icona("box", t.testo_debole, ic_px(26)))
        v.addWidget(img, 0, Qt.AlignmentFlag.AlignHCenter)
        titolo = QLabel("Nessun pezzo selezionato", s)
        titolo.setObjectName("LatTitolo")
        v.addWidget(titolo, 0, Qt.AlignmentFlag.AlignHCenter)
        sotto = QLabel("Scegli una riga per vedere barcode, peso e movimenti.", s)
        sotto.setObjectName("Dim")
        sotto.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sotto.setWordWrap(True)
        v.addWidget(sotto)
        self._pannello_l.addWidget(s)

    def _sezione_movimenti(self, titolo: str, pezzo_id: int | None, limite: int) -> None:
        s = QFrame(self._pannello)
        s.setObjectName("Lat")
        v = QVBoxLayout(s)
        v.setContentsMargins(M.LAT_PH, M.LAT_PV, M.LAT_PH, M.LAT_PV)
        v.setSpacing(M.GAP_SM)
        lab = QLabel(titolo, s)
        lab.setObjectName("LatSezione")
        v.addWidget(lab)

        lista = ListaMovimenti(s)
        try:
            sessione = self._factory()
            try:
                mov = consultazione.ultimi_movimenti(sessione, limite=limite, pezzo_id=pezzo_id)
            finally:
                sessione.close()
            lista.imposta(mov)
        except SQLAlchemyError:
            logger.exception("Caricamento ultimi movimenti non riuscito")
            lista.imposta([])
        v.addWidget(lista)
        self._pannello_l.addWidget(s)

    def _stampa_etichetta(self, barcode: str | None) -> None:
        if not barcode:
            return
        sessione = self._factory()
        try:
            pezzo = consultazione.pezzo_per_barcode(sessione, barcode)
        finally:
            sessione.close()
        if pezzo is None:
            return
        percorso, _ = QFileDialog.getSaveFileName(self, "Salva etichetta", f"etichetta_{barcode}.pdf", "PDF (*.pdf)")
        if not percorso:
            return
        try:
            from ..barcode import etichette

            etichette.genera_etichetta_pdf(pezzo, percorso)
            self._footer.setText("Etichetta PDF generata")
        except ValueError as errore:
            self._footer.setText(f"Etichetta: {errore}")

    # ------------------------------------------------------------------
    # aggiornamento dati
    # ------------------------------------------------------------------
    def aggiorna(self) -> None:
        """Rilegge tutto dal database: KPI, chip colore, filtri, tabella."""
        sessione = self._factory()
        try:
            self._soglia = impostazioni.leggi_soglia(sessione)
            riepilogo = consultazione.riepilogo_inventario(sessione, self._soglia)
            colori = consultazione.lista_colori_con_conteggio(sessione)
            profili = [(p.id, p.codice, p.descrizione) for p in consultazione.lista_profilo(sessione)]
            ubicazioni = list(consultazione.lista_ubicazioni(sessione))
        finally:
            sessione.close()

        self._aggiorna_kpi(riepilogo)
        self._aggiorna_tab_colori(colori)
        self._aggiorna_filtri(self.combo_profilo.currentData(), profili, ubicazioni)
        self._rinfresca_tabella()
        self._sezioni_laterali()
        self.cambiato.emit()

    def _aggiorna_filtri(self, profilo_id: int | None, profili: list, ubicazioni: list) -> None:
        self.combo_profilo.blockSignals(True)
        self.combo_profilo.clear()
        self.combo_profilo.addItem("Tutti i profili", None)
        for pid, codice, descrizione in profili:
            testo = codice if not descrizione else f"{codice} — {descrizione}"
            self.combo_profilo.addItem(testo, pid)
        if profilo_id is not None:
            i = self.combo_profilo.findData(profilo_id)
            if i >= 0:
                self.combo_profilo.setCurrentIndex(i)
            else:
                self.combo_profilo.setCurrentIndex(0)
        self.combo_profilo.blockSignals(False)

        testo_ub = self.combo_ubicazione.currentText().strip()
        self.combo_ubicazione.blockSignals(True)
        self.combo_ubicazione.clear()
        self.combo_ubicazione.addItem(_TUTTE_UBICAZIONI, "")
        for u in ubicazioni:
            self.combo_ubicazione.addItem(u, u)
        self.combo_ubicazione.blockSignals(False)
        if testo_ub:
            i = self.combo_ubicazione.findText(testo_ub)
            if i >= 0:
                self.combo_ubicazione.setCurrentIndex(i)
            else:
                self.combo_ubicazione.setEditText(testo_ub)
        else:
            self.combo_ubicazione.setCurrentIndex(0)

    # ------------------------------------------------------------------
    # tabella
    # ------------------------------------------------------------------
    def _ubicazione_filtro(self) -> str | None:
        testo = (self.combo_ubicazione.currentText() or "").strip()
        if not testo or testo == _TUTTE_UBICAZIONI:
            return None
        return testo

    def _rinfresca_tabella(self) -> None:
        stato = self.combo_stato.currentData()
        ubicazione = self._ubicazione_filtro()
        sessione = self._factory()
        try:
            if self._colore_selezionato is None:
                filtri_colori = None
                conteggio_riferimento = None
            else:
                filtri_colori = self._colore_selezionato
                conteggio_riferimento = [
                    r for c, r, _p in consultazione.lista_colori_con_conteggio(sessione)
                    if c.id == self._colore_selezionato
                ]
                conteggio_riferimento = conteggio_riferimento[0] if conteggio_riferimento else 0
            pezzi = consultazione.cerca_pezzi(
                sessione,
                testo=self.cerca.text(),
                colore_id=filtri_colori,
                stato=stato,
                profilo_id=self.combo_profilo.currentData(),
                ubicazione=ubicazione,
                soglia_globale=self._soglia,
            )
        finally:
            sessione.close()

        t = tema_attivo()
        tab = self._tabella
        tab.blockSignals(True)
        tab.setRowCount(0)

        def _item(testo: str, allineamento: int = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter) -> QTableWidgetItem:
            i = QTableWidgetItem(str(testo))
            i.setTextAlignment(allineamento)
            i.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            return i

        for z in pezzi:
            riga = tab.rowCount()
            tab.insertRow(riga)

            bc = _item(z.barcode or "")
            bc.setForeground(QColor(t.testo_dim))
            tab.setItem(riga, _BARCODE, bc)

            codice = z.profilo.codice or ""
            descrizione = z.profilo.descrizione or ""
            prof_item = _item(codice + ((" — " + descrizione) if descrizione else ""))
            prof_item.setData(Qt.ItemDataRole.UserRole + 1, descrizione)
            tab.setItem(riga, 1, prof_item)

            colore_txt = z.colore.nome_visualizzato or z.colore.codice_normalizzato
            col_item = _item(colore_txt)
            col_item.setData(Qt.ItemDataRole.UserRole + 1, z.colore.codice_normalizzato)
            tab.setItem(riga, _COLORE, col_item)

            peso_tot = consultazione.peso_totale_kg(z)
            tab.setItem(riga, 3, _item(self._numero_it(z.lunghezza_mm) + " mm" if z.lunghezza_mm else "—", Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
            stato_riga = consultazione.stato_scorta(z, self._soglia)
            pz_item = _item(f"{z.quantita:,}".replace(",", "X").replace(".", ",").replace("X", ".") if z.quantita is not None else "—", Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if stato_riga in ("sotto", "esaurito"):
                pz_item.setForeground(QColor(t.pericolo))
                f = pz_item.font()
                f.setBold(True)
                pz_item.setFont(f)
            tab.setItem(riga, 4, pz_item)
            tab.setItem(riga, 5, _item(_testo_peso(peso_tot), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
            tab.setItem(riga, 6, _item(z.ubicazione or "—"))

            testo_stato, chiave = _STATO_INFO.get(stato_riga, ("OK", "ok"))
            stato_item = _item("")
            stato_item.setData(Qt.ItemDataRole.UserRole, testo_stato)
            tab.setItem(riga, 7, stato_item)
            tab.setCellWidget(riga, 7, _cella_pillola(testo_stato, chiave))

        tab.blockSignals(False)

        self._applica_colonna_colore()
        totale = (
            conteggio_riferimento
            if self._colore_selezionato is not None and conteggio_riferimento is not None
            else len(pezzi)
        )
        self._footer.setText(f"{len(pezzi):,} di {int(totale or 0):,} referenze")

        filtri_attivi = bool(
            (self.cerca.text() or "").strip()
            or self.combo_profilo.currentIndex() != 0
            or self._ubicazione_filtro() is not None
            or self.combo_stato.currentIndex() != 0
        )
        if not pezzi and filtri_attivi and int(totale or 0) > 0:
            self._vuoto.show()
            self._centra_vuoto()
        else:
            self._vuoto.hide()

    @staticmethod
    def _numero_it(valore) -> str:
        return f"{int(valore):,}".replace(",", "X").replace(".", ",").replace("X", ".")

    def _applica_colonna_colore(self) -> None:
        """La colonna 'Colore' è ridondante quando è attiva una chip colore."""
        self._tabella.setColumnHidden(_COLORE, self._colore_selezionato is not None)
        self._tabella.setColumnHidden(_BARCODE, True)  # contratto: resta colonna 0

    # ------------------------------------------------------------------
    # interazione
    # ------------------------------------------------------------------
    def _su_cambio_tab(self, indice: int) -> None:
        self._colore_selezionato = self._id_tab[indice] if 0 <= indice < len(self._id_tab) else None
        self._applica_colonna_colore()
        self._rinfresca_tabella()
        self._sezioni_laterali()

    def _su_selezione(self) -> None:
        selezione = self._tabella.selectedItems()
        if selezione:
            riga = selezione[0].row()
            item_bc = self._tabella.item(riga, _BARCODE)
            self._barcode_selezionato = item_bc.text() if item_bc else None
        else:
            self._barcode_selezionato = None
        self._sezioni_laterali()
        animazioni.dissolvenza(self._pannello, animazioni.DURATA_BREVE)

    def _azzera_filtri(self) -> None:
        self.cerca.clear()
        self.combo_profilo.setCurrentIndex(0)
        self.combo_ubicazione.setCurrentIndex(0)
        self.combo_stato.setCurrentIndex(0)
        self._rinfresca_tabella()

    def vai_a_colore(self, colore_id: int) -> None:
        """Seleziona la scheda del colore, azzera ricerca e combo (da Avvisi)."""
        indice = self._id_tab.index(colore_id) if colore_id in self._id_tab else 0
        self._azzera_filtri()
        self._tabbar.setCurrentIndex(indice)

    # scorciatoie tastiera
    def tab_colori_giù(self) -> None:
        self._muovi_tab(1)

    def tab_colori_sopra(self) -> None:
        self._muovi_tab(-1)

    def _muovi_tab(self, delta: int) -> None:
        bar = self._tabbar
        bar.setCurrentIndex(max(0, min(bar.count() - 1, bar.currentIndex() + delta)))
        bar.setFocus()
