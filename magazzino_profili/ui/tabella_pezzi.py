"""Scheda Inventario: card KPI, tab colori, filtri e tabella dei pezzi.

Layout (come nel mockup):

- riga di 4 card KPI (pezzi totali, profili, peso, da riordinare);
- tab colori: "Tutti" + un tab per colore con pallino e conteggio;
- barra filtri: ricerca, Profilo, Ubicazione (uguaglianza esatta),
  Stato scorta, pulsante "Azzera";
- tabella unica (una sola ``QTableWidget`` riusata per tutti i colori),
  con la colonna "Colore" nascosta quando è selezionato un colore;
- piè di pagina: "N di M referenze" (M = referenze del colore, senza
  altri filtri).

Dopo un carico/scarico la scheda selezionata resta invariata:
:func:`TabellaPezzi.aggiorna` ricostruisce le tab conservando la
selezione corrente (e torna a "Tutti" solo se il colore è sparito).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..services import consultazione
from .componenti import CardKPI, icona_colore, icona_linea, icona_tessera, pillola
from .tema import px, qss_globale, tema_attivo

_COLONNE = ["Barcode", "Profilo", "Colore", "Lunghezza (mm)", "Quantità", "Peso (kg)", "Ubicazione", "Stato"]
_COLORE = 2  # indice colonna "Colore"
_TUTTE_UBICAZIONI = "Tutte le ubicazioni"

_STATI_COMBO = [
    ("Tutti", None),
    ("OK", "ok"),
    ("Sotto scorta", "sotto"),
    ("Esauriti", "esaurito"),
    ("Da riordinare", "riordino"),
]

_STATO_INFO = {
    "ok": ("OK", "ok"),
    "sotto": ("Sotto scorta", "avviso"),
    "esaurito": ("Esaurito", "pericolo"),
}


def _cella_pillola(testo: str, variante: str) -> QWidget:
    """Badge di stato centrato nella cella (la cella resta cliccabile)."""
    contenitore = QWidget()
    contenitore.setAttribute(Qt.WA_TransparentForMouseEvents)
    riga = QHBoxLayout(contenitore)
    riga.setContentsMargins(px(8), px(4), px(8), px(4))
    riga.addWidget(pillola(testo, variante), 0, Qt.AlignLeft | Qt.AlignVCenter)
    return contenitore


class TabellaPezzi(QWidget):
    """Scheda Inventario con card KPI, tab colori e tabella pezzi."""

    def __init__(self, factory, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._factory = factory
        self._colore_selezionato: int | None = None  # None = "Tutti"
        self._id_tab: list[int | None] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(px(14), px(14), px(14), px(10))
        root.setSpacing(px(12))

        root.addWidget(self._costruisci_titolo())
        root.addLayout(self._costruisci_kpi())
        self._tabbar = self._costruisci_tabbar()
        root.addWidget(self._tabbar)
        root.addWidget(self._costruisci_toolbar())
        self._tabella = self._costruisci_tabella()
        root.addWidget(self._tabella, 1)
        self._footer = QLabel(self)
        self._footer.setObjectName("TestoDim")
        self._footer.setStyleSheet(f"font-size: {px(13)}px;")
        root.addWidget(self._footer)

        self._tabbar.currentChanged.connect(self._su_cambio_tab)
        self.cerca.textChanged.connect(lambda _t: self._rinfresca_tabella())
        # ubicazione è editabile: editTextChanged copre sia la digitazione
        # sia la selezione dall'elenco (cambia sempre il testo)
        self.combo_ubicazione.editTextChanged.connect(lambda _t: self._rinfresca_tabella())
        for c in (self.combo_profilo, self.combo_stato):
            c.currentIndexChanged.connect(lambda _i: self._rinfresca_tabella())

        self.aggiorna()

    # ------------------------------------------------------------------
    # costruzione
    # ------------------------------------------------------------------
    def _costruisci_titolo(self) -> QWidget:
        t = tema_attivo()
        w = QWidget(self)
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        titolo = QLabel("Inventario", w)
        titolo.setObjectName("TitoloSezione")
        titolo.setStyleSheet(f"font-size: {px(20)}px; font-weight: 800;")
        sotto = QLabel("Giacenze per profilo, colore e ubicazione", w)
        sotto.setObjectName("SottotitoloSezione")
        sotto.setStyleSheet(f"font-size: {px(13.5)}px; color: {t.testo_dim};")
        h.addWidget(titolo)
        h.addSpacing(px(12))
        h.addWidget(sotto)
        h.addStretch(1)
        return w

    def _costruisci_kpi(self) -> QHBoxLayout:
        t = tema_attivo()
        h = QHBoxLayout()
        h.setSpacing(px(10))

        self.kpi_pezzi = CardKPI(icona_linea("layers", t.accento, px(34)), "0", "Pezzi in giacenza", "good")
        self.kpi_profili = CardKPI(icona_linea("tag", t.testo_dim, px(34)), "0", "Referenze", "neutro")
        self.kpi_peso = CardKPI(icona_linea("weight", t.ok, px(34)), "0 kg", "Peso totale", "ok")
        self.kpi_riordino = CardKPI(icona_linea("alert", t.pericolo, px(34)), "0", "Da riordinare", "bad")

        for card in (self.kpi_pezzi, self.kpi_profili, self.kpi_peso, self.kpi_riordino):
            h.addWidget(card, 1)
        return h

    def _costruisci_tabbar(self) -> QTabBar:
        t = tema_attivo()
        bar = QTabBar(self)
        bar.setExpanding(False)
        bar.setDrawBase(False)
        bar.setUsesScrollButtons(True)
        bar.setElideMode(Qt.ElideNone)  # i nomi dei colori non vanno troncati
        bar.setStyleSheet(f"""
            QTabBar {{ background: transparent; }}
            QTabBar::tab {{
                background: {t.carta};
                border: 1px solid {t.bordo};
                border-radius: {px(9)}px;
                color: {t.testo_dim};
                padding: {px(7)} {px(13)};
                margin: 0 {px(4)} 0 0;
                font-size: {px(12.5)}px;
                font-weight: 700;
            }}
            QTabBar::tab:selected {{
                background: {t.accento_sfondo};
                border-color: {t.accento};
                color: {t.testo};
            }}
            QTabBar::tab:hover:!selected {{ border-color: {t.bordo_forte}; color: {t.testo}; }}
            QTabBar::scroller {{
                width: {px(36)}px;
                background: {t.carta};
                border: 1px solid {t.bordo};
                border-radius: {px(8)}px;
            }}
        """)
        return bar

    def _costruisci_toolbar(self) -> QWidget:
        t = tema_attivo()
        w = QWidget(self)
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(px(8))

        self.cerca = QLineEdit(w)
        self.cerca.setPlaceholderText("Cerca: barcode, profilo, colore, ubicazione…")
        self.cerca.setClearButtonEnabled(True)
        self.cerca.addAction(icona_linea("search", t.testo_dim, px(16), 0.1), QLineEdit.LeadingPosition)
        h.addWidget(self.cerca, 2)

        self.combo_profilo = QComboBox(w)
        self.combo_profilo.setMinimumWidth(px(170))
        h.addWidget(self.combo_profilo)

        self.combo_ubicazione = QComboBox(w)
        self.combo_ubicazione.setEditable(True)
        self.combo_ubicazione.setInsertPolicy(QComboBox.NoInsert)
        self.combo_ubicazione.lineEdit().setPlaceholderText("Ubicazione")
        self.combo_ubicazione.setMinimumWidth(px(140))
        h.addWidget(self.combo_ubicazione)

        self.combo_stato = QComboBox(w)
        self.combo_stato.setMinimumWidth(px(140))
        for etichetta, valore in _STATI_COMBO:
            self.combo_stato.addItem(etichetta, valore)
        h.addWidget(self.combo_stato)

        self.azzera = QPushButton("Azzera", w)
        self.azzera.clicked.connect(self._azzera_filtri)
        h.addWidget(self.azzera)
        return w

    def _costruisci_tabella(self) -> QTableWidget:
        tab = QTableWidget(0, len(_COLONNE), self)
        tab.setHorizontalHeaderLabels(_COLONNE)
        tab.verticalHeader().setVisible(False)
        tab.setAlternatingRowColors(True)
        pal = tab.palette()
        pal.setColor(QPalette.AlternateBase, QColor(tema_attivo().carta))
        tab.setPalette(pal)
        tab.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tab.setSelectionBehavior(QAbstractItemView.SelectRows)
        tab.setSelectionMode(QAbstractItemView.SingleSelection)
        tab.setShowGrid(False)
        tab.setSortingEnabled(False)
        tab.setWordWrap(False)
        tab.verticalHeader().setDefaultSectionSize(px(38))
        header = tab.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)  # intestazioni a sinistra (mockup)
        from PySide6.QtWidgets import QHeaderView

        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        return tab

    # ------------------------------------------------------------------
    # aggiornamento dati
    # ------------------------------------------------------------------
    def aggiorna(self) -> None:
        """Rilegge tutto dal database: KPI, tab colori, filtri, tabella.

        La scheda colore selezionata viene conservata (dopo un carico o
        uno scarico non cambia da sola); se il colore non esiste più si
        torna a "Tutti".
        """
        sessione = self._factory()
        try:
            riepilogo = consultazione.riepilogo_inventario(sessione)
            colori = consultazione.lista_colori_con_conteggio(sessione)
            profili = [(p.id, p.codice, p.descrizione) for p in consultazione.lista_profilo(sessione)]
            ubicazioni = list(consultazione.lista_ubicazioni(sessione))
        finally:
            sessione.close()

        self._aggiorna_kpi(riepilogo)
        self._aggiorna_tab_colori(colori)
        self._aggiorna_filtri(self.combo_profilo.currentData(), profili, ubicazioni)
        self._rinfresca_tabella()

    def _aggiorna_kpi(self, r: dict) -> None:
        t = tema_attivo()
        peso = Decimal(str(r["peso_kg"] or 0))
        peso_txt = f"{peso:,.0f}" if peso == peso.to_integral_value() else f"{peso:,.1f}"
        self.kpi_pezzi.set_valore(f"{int(r['pezzi_totali']):,}")
        self.kpi_profili.set_valore(f"{int(r['referenze']):,}")
        self.kpi_peso.set_valore(f"{peso_txt} kg")
        n_riordino = int(r["da_riordinare"])
        self.kpi_riordino.set_valore(f"{n_riordino:,}")
        # il card "da riordinare" diventa rosso solo quando ci sono avvisi
        self.kpi_riordino.set_colore_valore(t.pericolo if n_riordino else t.ok)

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

        # ripristino selezione (stabile dopo carico/scarico)
        indice = 0
        if precedente is not None and precedente in self._id_tab:
            indice = self._id_tab.index(precedente)
        bar.setCurrentIndex(indice)
        self._colore_selezionato = self._id_tab[indice]
        bar.blockSignals(False)
        self._applica_colonna_colore()

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
        """Valore del filtro ubicazione: il testo visibile nel campo.

        Vale sia per la voce selezionata sia per il testo digitato. La voce
        "Tutte le ubicazioni" equivale a nessun filtro.
        """
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
                # "N di M": M = referenze di quel colore, SENZA altri filtri
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
            )
        finally:
            sessione.close()

        t = tema_attivo()
        tab = self._tabella
        tab.setRowCount(0)

        def _item(testo: str, allineamento: int = Qt.AlignLeft | Qt.AlignVCenter) -> QTableWidgetItem:
            i = QTableWidgetItem(str(testo))
            i.setTextAlignment(allineamento)
            i.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            return i

        for z in pezzi:
            riga = tab.rowCount()
            tab.insertRow(riga)

            bc = _item(z.barcode or "")
            bc.setForeground(QColor(t.testo_dim))
            tab.setItem(riga, 0, bc)
            tab.setItem(riga, 1, _item((z.profilo.codice or "") + ((" — " + z.profilo.descrizione) if z.profilo.descrizione else "")))
            tab.setItem(riga, 2, _item(z.colore.nome_visualizzato or z.colore.codice_normalizzato))

            peso_unit = consultazione.peso_unitario_kg(z)
            peso_tot = peso_unit * (z.quantita or 0)
            tab.setItem(riga, 3, _item(f"{z.lunghezza_mm:,}" if z.lunghezza_mm else "—", Qt.AlignRight | Qt.AlignVCenter))
            tab.setItem(riga, 4, _item(f"{z.quantita:,}" if z.quantita is not None else "—", Qt.AlignRight | Qt.AlignVCenter))
            tab.setItem(riga, 5, _item(f"{Decimal(str(peso_tot)):,.2f}", Qt.AlignRight | Qt.AlignVCenter))
            tab.setItem(riga, 6, _item(z.ubicazione or "—"))

            stato_riga = consultazione.stato_scorta(z)
            testo_stato, chiave = _STATO_INFO.get(stato_riga, ("OK", "ok"))
            # testo in UserRole (leggibile da codice); la cella mostra solo il badge
            stato_item = _item("")
            stato_item.setData(Qt.UserRole, testo_stato)
            tab.setItem(riga, 7, stato_item)
            tab.setCellWidget(riga, 7, _cella_pillola(testo_stato, chiave))

        self._applica_colonna_colore()
        totale = (
            conteggio_riferimento
            if self._colore_selezionato is not None and conteggio_riferimento is not None
            else len(pezzi)
        )
        ora = datetime.now().strftime("%H:%M:%S")
        testo_footer = f"{len(pezzi):,} di {int(totale or 0):,} referenze   ·   aggiornamento {ora}"
        if not pezzi and int(totale or 0) > 0:
            testo_footer += "   ·   nessun risultato con i filtri attuali (usa Azzera)"
        self._footer.setText(testo_footer)

    def _applica_colonna_colore(self) -> None:
        """La colonna 'Colore' è ridondante quando è attivo un tab colore."""
        self._tabella.setColumnHidden(_COLORE, self._colore_selezionato is not None)

    # ------------------------------------------------------------------
    # interazione
    # ------------------------------------------------------------------
    def _su_cambio_tab(self, indice: int) -> None:
        self._colore_selezionato = self._id_tab[indice] if 0 <= indice < len(self._id_tab) else None
        self._applica_colonna_colore()
        self._rinfresca_tabella()

    def _azzera_filtri(self) -> None:
        self.cerca.clear()
        self.combo_profilo.setCurrentIndex(0)
        self.combo_ubicazione.setCurrentIndex(0)
        self.combo_stato.setCurrentIndex(0)
        # la chiamata a setCurrentIndex non innesca _rinfresca_tabella
        # (segnali bloccati durante la costruzione); qui lo facciamo noi.
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
