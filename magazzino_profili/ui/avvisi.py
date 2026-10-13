"""Scheda Avvisi: pezzi esauriti o sotto scorta minima, con "Dettagli".

Il pulsante "Dettagli" di ogni riga emette :attr:`vai_a_colore` con
l'id del colore del pezzo: la finestra principale passa alla scheda
Inventario e seleziona la scheda colore corrispondente (azzera ricerca
e combo), come richiesto dal collegamento Avvisi → Inventario.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..services import consultazione
from .componenti import pillola
from .tema import px, tema_attivo


class SchedaAvvisi(QWidget):
    """Tabella dei pezzi da riordinare (esauriti o sotto scorta)."""

    #: emesso da "Dettagli" di una riga: id del colore del pezzo
    vai_a_colore = Signal(int)

    def __init__(self, factory, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._factory = factory
        t = tema_attivo()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(14), px(14), px(14), px(14))
        layout.setSpacing(px(12))

        riga_titolo = QWidget(self)
        h = QHBoxLayout(riga_titolo)
        h.setContentsMargins(0, 0, 0, 0)
        titolo = QLabel("Avvisi", riga_titolo)
        titolo.setStyleSheet(f"font-size: {px(20)}px; font-weight: 800;")
        self.contatore = QLabel(riga_titolo)
        self.contatore.setStyleSheet(f"font-size: {px(13.5)}px; color: {t.testo_dim};")
        h.addWidget(titolo)
        h.addSpacing(px(12))
        h.addWidget(self.contatore)
        h.addStretch(1)
        self.aggiorna_btn = QPushButton("Aggiorna", riga_titolo)
        self.aggiorna_btn.clicked.connect(self.aggiorna)
        h.addWidget(self.aggiorna_btn)
        layout.addWidget(riga_titolo)

        # 7 colonne: l'ultima ospita il pulsante "Dettagli"
        self._tabella = QTableWidget(0, 7, self)
        self._tabella.setHorizontalHeaderLabels(
            ["Codice", "Colore", "Lunghezza (mm)", "Giacenza", "Scorta minima", "Stato", ""]
        )
        self._tabella.verticalHeader().setVisible(False)
        self._tabella.verticalHeader().setDefaultSectionSize(px(44))
        from PySide6.QtWidgets import QHeaderView as _QHV
        self._tabella.horizontalHeader().setSectionResizeMode(5, _QHV.ResizeMode.ResizeToContents)
        self._tabella.setAlternatingRowColors(True)
        pal = self._tabella.palette()
        pal.setColor(QPalette.AlternateBase, QColor(tema_attivo().carta))
        self._tabella.setPalette(pal)
        self._tabella.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tabella.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tabella.setSelectionMode(QAbstractItemView.SingleSelection)
        self._tabella.setShowGrid(False)
        from PySide6.QtWidgets import QHeaderView

        self._tabella.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self._tabella.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._tabella, 1)

        self.aggiorna()

    # ------------------------------------------------------------------
    def aggiorna(self) -> None:
        sessione = self._factory()
        try:
            lista = consultazione.pezzi_da_riordinare(sessione)
        finally:
            sessione.close()

        t = tema_attivo()
        tab = self._tabella
        tab.setRowCount(0)
        for z in lista:
            riga = tab.rowCount()
            tab.insertRow(riga)

            def _item(testo: str, allineamento: int = Qt.AlignLeft | Qt.AlignVCenter) -> QTableWidgetItem:
                i = QTableWidgetItem(str(testo))
                i.setTextAlignment(allineamento)
                i.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                return i

            tab.setItem(riga, 0, _item(z.profilo.codice or ""))
            tab.setItem(riga, 1, _item(z.colore.nome_visualizzato or z.colore.codice_normalizzato))
            tab.setItem(riga, 2, _item(f"{z.lunghezza_mm:,}" if z.lunghezza_mm else "—", Qt.AlignRight | Qt.AlignVCenter))
            giacenza = _item(f"{z.quantita:,}" if z.quantita is not None else "0", Qt.AlignRight | Qt.AlignVCenter)
            tab.setItem(riga, 3, giacenza)
            scorta = _item(f"{z.scorta_minima:,}" if z.scorta_minima is not None else "—", Qt.AlignRight | Qt.AlignVCenter)
            tab.setItem(riga, 4, scorta)

            stato = consultazione.stato_scorta(z)
            if stato == "esaurito":
                testo, hx = "Esaurito", t.pericolo
            else:
                testo, hx = "Sotto scorta", t.avviso
            variante = "pericolo" if stato == "esaurito" else "avviso"
            stato_item = _item("")  # la cella mostra il badge; il testo resta in UserRole
            stato_item.setData(Qt.UserRole, testo)
            tab.setItem(riga, 5, stato_item)
            badge = QWidget()
            badge.setAttribute(Qt.WA_TransparentForMouseEvents)
            riga_badge = QHBoxLayout(badge)
            riga_badge.setContentsMargins(px(8), px(4), px(8), px(4))
            riga_badge.addWidget(pillola(testo, variante), 0, Qt.AlignLeft | Qt.AlignVCenter)
            tab.setCellWidget(riga, 5, badge)

            puls = QPushButton("Dettagli")
            puls.setCursor(Qt.PointingHandCursor)
            puls.setFixedSize(px(96), px(30))
            puls.setStyleSheet(
                f"background: {t.carta2}; border: 1px solid {t.accento}; color: {t.testo};\n"
                f"border-radius: {px(7)}px; padding: 0 {px(8)}px; font-weight: 700;"
            )
            puls.clicked.connect(lambda _c=False, cid=z.colore.id: self.vai_a_colore.emit(cid))
            contenitore_puls = QWidget()
            riga_puls = QHBoxLayout(contenitore_puls)
            riga_puls.setContentsMargins(px(8), px(3), px(8), px(3))
            riga_puls.addWidget(puls, 0, Qt.AlignLeft | Qt.AlignVCenter)
            tab.setCellWidget(riga, 6, contenitore_puls)

        n = tab.rowCount()
        if n == 0:
            self.contatore.setText("Nessun avviso: tutte le giacenze sono sopra la scorta minima.")
        else:
            self.contatore.setText(
                f"{n} {'pezzo' if n == 1 else 'pezzi'} da riordinare (esauriti o sotto scorta)."
            )
