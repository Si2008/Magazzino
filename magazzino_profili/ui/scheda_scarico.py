"""Scheda Scarico: riduzione di giacenza da barcode, con causale."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..services import consultazione, scarica
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QHeaderView

from .messaggi import chiedi_conferma, mostra_errore
from .tema import px, tema_attivo


def _etichetta(testo: str, parent: QWidget) -> QLabel:
    t = tema_attivo()
    lab = QLabel(testo, parent)
    lab.setStyleSheet(f"color: {t.testo_dim}; font-size: {px(13)}px; font-weight: 600;")
    return lab


def _con_etichetta(testo: str, widget: QWidget) -> QWidget:
    contenitore = QWidget()
    v = QVBoxLayout(contenitore)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(px(4))
    v.addWidget(_etichetta(testo, contenitore))
    v.addWidget(widget)
    return contenitore


class SchedaScarico(QWidget):
    """Form di scarico pezzi da barcode."""

    cambiato = Signal()

    def __init__(
        self,
        factory,
        utente: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._factory = factory
        self._utente = utente
        t = tema_attivo()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(px(14), px(14), px(14), px(14))
        layout.setSpacing(px(14))

        form = QWidget(self)
        vf = QVBoxLayout(form)
        vf.setContentsMargins(0, 0, 0, 0)
        vf.setSpacing(px(10))

        titolo = QLabel("Scarico", form)
        titolo.setStyleSheet(f"font-size: {px(20)}px; font-weight: 800;")
        vf.addWidget(titolo)

        vf.addWidget(_etichetta("Barcode", form))
        self.barcode = QLineEdit(form)
        self.barcode.setPlaceholderText("Scansiona o digita il barcode del pezzo da scaricare…")
        self.barcode.setStyleSheet(f"font-size: {px(17)}px; font-weight: 700; padding: {px(11)} {px(13)};")
        self.barcode.returnPressed.connect(self._su_invio)
        self.barcode.textChanged.connect(self._aggiorna_anteprima)
        vf.addWidget(self.barcode)

        riga = QHBoxLayout()
        self.quantita = QLineEdit(form)
        self.quantita.setPlaceholderText("quantità (pz)")
        self.quantita.setValidator(QIntValidator(1, 99_999_999, self))
        self.quantita.setText("1")
        riga.addWidget(_con_etichetta("Quantità (pz)", self.quantita), 1)
        self.causale = QLineEdit(form)
        self.causale.setPlaceholderText("Causale (obbligatoria)")
        riga.addWidget(_con_etichetta("Causale (obbligatoria)", self.causale), 1)
        vf.addLayout(riga)

        self.anteprima = QLabel("", form)
        self.anteprima.setStyleSheet(f"color: {t.testo_dim}; font-size: {px(13.5)}px;")
        self.anteprima.setWordWrap(True)
        vf.addWidget(self.anteprima)

        vf.addStretch(1)

        self.salva = QPushButton("Salva scarico", form)
        self.salva.setProperty("classe", "pericolo")
        self.salva.setStyleSheet(f"font-size: {px(15)}px; padding: {px(11)} {px(18)};")
        self.salva.clicked.connect(self.salva_scarico)
        vf.addWidget(self.salva, alignment=Qt.AlignLeft)

        # lista pezzi a destra
        lato = QWidget(self)
        vl = QVBoxLayout(lato)
        vl.setContentsMargins(px(14), px(0), px(0), px(0))
        vl.setSpacing(px(8))
        titolo_m = QLabel("Pezzi in giacenza", lato)
        titolo_m.setStyleSheet(f"font-size: {px(15)}px; font-weight: 700;")
        vl.addWidget(titolo_m)
        self._tabella = QTableWidget(0, 5, lato)
        self._tabella.setHorizontalHeaderLabels(["Barcode", "Profilo", "Colore", "Lunghezza", "Giacenza"])
        self._tabella.verticalHeader().setVisible(False)
        self._tabella.setAlternatingRowColors(True)
        self._tabella.setEditTriggers(QTableWidget.NoEditTriggers)
        self._tabella.setSelectionBehavior(QTableWidget.SelectRows)
        self._tabella.setShowGrid(False)
        self._tabella.horizontalHeader().setStretchLastSection(True)
        # Righe alternate con il colore del tema (il bianco di default rendeva il testo illeggibile).
        pal = self._tabella.palette()
        pal.setColor(QPalette.AlternateBase, QColor(t.carta))
        self._tabella.setPalette(pal)
        for colonna in range(4):
            self._tabella.horizontalHeader().setSectionResizeMode(colonna, QHeaderView.ResizeMode.ResizeToContents)
        vl.addWidget(self._tabella, 1)

        layout.addWidget(form, 2)
        layout.addWidget(lato, 3)

        self._rinfresca_tabella()
        self.barcode.setFocus()

    # ------------------------------------------------------------------
    def _rinfresca_tabella(self) -> None:
        sessione = self._factory()
        try:
            pezzi = consultazione.lista_pezzi(sessione)
        finally:
            sessione.close()

        tab = self._tabella
        tab.setRowCount(0)
        for z in pezzi:
            riga = tab.rowCount()
            tab.insertRow(riga)
            for colonna, testo in enumerate(
                [
                    z.barcode or "",
                    z.profilo.codice or "",
                    z.colore.nome_visualizzato or z.colore.codice_normalizzato,
                    f"{z.lunghezza_mm:,}" if z.lunghezza_mm else "—",
                    f"{z.quantita:,}" if z.quantita is not None else "0",
                ]
            ):
                i = QTableWidgetItem(testo)
                i.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter if colonna < 3 else Qt.AlignRight | Qt.AlignVCenter)
                i.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                tab.setItem(riga, colonna, i)

    def _aggiorna_anteprima(self, testo: str) -> None:
        """Mostra il pezzo riconosciuto e la giacenza disponibile prima dello scarico."""
        t = tema_attivo()
        valore = (testo or "").strip().upper()
        if not valore:
            self.anteprima.clear()
            return
        sessione = self._factory()
        try:
            pezzo = consultazione.pezzo_per_barcode(sessione, valore)
            if pezzo is None:
                self.anteprima.setText("Nessun pezzo con questo barcode.")
                self.anteprima.setStyleSheet(f"color: {t.avviso}; font-size: {px(13.5)}px;")
                return
            riga = (
                f"{pezzo.profilo.codice} · {pezzo.colore.nome_visualizzato} · "
                f"{pezzo.lunghezza_mm:,} mm — giacenza: {pezzo.quantita} pz"
            )
            if pezzo.ubicazione:
                riga += f" · {pezzo.ubicazione}"
            self.anteprima.setText(riga)
            self.anteprima.setStyleSheet(
                f"color: {t.testo}; font-size: {px(13.5)}px; font-weight: 600;"
            )
        finally:
            sessione.close()

    def _su_invio(self) -> None:
        if not self.causale.text().strip():
            QMessageBox.warning(self, "Scarico", "La causale è obbligatoria.")
            return
        self.salva_scarico()

    def salva_scarico(self) -> None:
        if not self.causale.text().strip():
            QMessageBox.warning(self, "Scarico", "La causale è obbligatoria.")
            return
        testo = self.barcode.text().strip()
        if not testo:
            QMessageBox.warning(self, "Scarico", "Compila il barcode.")
            return
        try:
            quantita = int(self.quantita.text() or 0)
        except ValueError:
            QMessageBox.warning(self, "Scarico", "Quantità non valida.")
            return
        if quantita <= 0:
            QMessageBox.warning(self, "Scarico", "La quantità deve essere maggiore di zero.")
            return
        # Uscita totale: la giacenza diventa zero. Serve conferma esplicita.
        sessione = self._factory()
        try:
            pezzo = consultazione.pezzo_per_barcode(sessione, testo.upper())
            giacenza = pezzo.quantita if pezzo is not None else None
            descrizione = f"{pezzo.profilo.codice} · {pezzo.colore.nome_visualizzato} · {pezzo.lunghezza_mm:,} mm" if pezzo is not None else ""
        finally:
            sessione.close()
        if giacenza is not None and quantita == giacenza:
            confermato = chiedi_conferma(
                self,
                "Scarico totale",
                f"Stai scaricando tutta la giacenza di {descrizione}: {giacenza} pz.\n"
                "Dopo lo scarico il pezzo risulterà esaurito. Continuare?",
                "Scarica tutto",
                pericolosa=True,
            )
            if not confermato:
                return

        try:
            sessione = self._factory()
            try:
                scarica(sessione, barcode=testo, quantita=quantita, utente=self._utente or "operatore",
                        causale=self.causale.text().strip())
            finally:
                sessione.close()
        except Exception as errore:  # noqa: BLE001 - spiegato all'utente, dettaglio nel log
            mostra_errore(self, "Scarico", errore, "Lo scarico")
            return

        self.barcode.clear()
        self.quantita.setText("1")
        self.causale.clear()
        self.anteprima.clear()
        self._rinfresca_tabella()
        self.cambiato.emit()
