"""Scheda Carico: scannerizzazione/inserimento barcode e giacenza.

Comportamento:

- si scansiona (o si digita) il barcode: i campi (codice, colore,
  lunghezza) si compilano da soli;
- "Salva carico" (o Invio con i campi già compilati) chiude l'operazione;
- ``ubicazione`` e ``causale`` sono opzionali; l'ubicazione viene
  salvata solo se fornita (servizio ``carica``);
- a destra: gli ultimi movimenti del magazzino.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..services import consultazione
from ..services import ProfiloNonTrovatoError, carica
from .tema import px, tema_attivo


class SchedaCarico(QWidget):
    """Form di carico pezzi da barcode."""

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

        # ---------------- colonna sinistra: form ----------------
        form = QWidget(self)
        vf = QVBoxLayout(form)
        vf.setContentsMargins(0, 0, 0, 0)
        vf.setSpacing(px(10))

        titolo = QLabel("Carico", form)
        titolo.setStyleSheet(f"font-size: {px(20)}px; font-weight: 800;")
        vf.addWidget(titolo)

        self.barcode = QLineEdit(form)
        self.barcode.setPlaceholderText("Scansiona o digita il barcode…")
        self.barcode.setStyleSheet(
            f"font-size: {px(17)}px; font-weight: 700; padding: {px(11)} {px(13)};"
        )
        self.barcode.returnPressed.connect(self._su_invio)
        self.barcode.textChanged.connect(self._su_texto_barcode)
        vf.addWidget(self.barcode)

        riga_codici = QHBoxLayout()
        self.codice = QLineEdit(form)
        self.codice.setPlaceholderText("codice profilo")
        riga_codici.addWidget(self.codice, 1)
        self.colore = QLineEdit(form)
        self.colore.setPlaceholderText("colore")
        riga_codici.addWidget(self.colore, 1)
        vf.addLayout(riga_codici)

        riga_lung_quant = QHBoxLayout()
        self.lunghezza = QLineEdit(form)
        self.lunghezza.setPlaceholderText("lunghezza (mm)")
        self.lunghezza.setInputMask("#")
        riga_lung_quant.addWidget(self.lunghezza, 1)
        self.quantita = QLineEdit(form)
        self.quantita.setPlaceholderText("quantità (pz)")
        self.quantita.setInputMask("#")
        self.quantita.setText("1")
        riga_lung_quant.addWidget(self.quantita, 1)
        vf.addLayout(riga_lung_quant)

        riga_ubic_caus = QHBoxLayout()
        self.ubicazione = QComboBox(form)
        self.ubicazione.setEditable(True)
        self.ubicazione.setInsertPolicy(QComboBox.NoInsert)
        self.ubicazione.setPlaceholderText("Ubicazione (opzionale)")
        riga_ubic_caus.addWidget(self.ubicazione, 1)
        self.causale = QLineEdit(form)
        self.causale.setPlaceholderText("Causale (opzionale)")
        riga_ubic_caus.addWidget(self.causale, 1)
        vf.addLayout(riga_ubic_caus)

        vf.addStretch(1)

        self.salva = QPushButton("Salva carico", form)
        self.salva.setProperty("classe", "primario")
        self.salva.setStyleSheet(f"font-size: {px(15)}px; padding: {px(11)} {px(18)};")
        self.salva.clicked.connect(self.salva_carico)
        vf.addWidget(self.salva, alignment=Qt.AlignLeft)

        # ---------------- colonna destra: movimenti recenti ----------------
        lato = QWidget(self)
        vl = QVBoxLayout(lato)
        vl.setContentsMargins(px(14), px(0), px(0), px(0))
        vl.setSpacing(px(8))
        titolo_m = QLabel("Ultimi movimenti", lato)
        titolo_m.setStyleSheet(f"font-size: {px(15)}px; font-weight: 700;")
        vl.addWidget(titolo_m)
        self.movimenti = QTextEdit(lato)
        self.movimenti.setReadOnly(True)
        self.movimenti.setStyleSheet(
            f"background: {t.carta}; border: 1px solid {t.bordo}; border-radius: {px(9)}px;"
        )
        vl.addWidget(self.movimenti, 1)

        layout.addWidget(form, 3)
        layout.addWidget(lato, 2)

        self._popola_ubicazioni()
        self._mostra_movimenti()
        self.barcode.setFocus()

    # ------------------------------------------------------------------
    def _popola_ubicazioni(self) -> None:
        sessione = self._factory()
        try:
            liste = consultazione.lista_ubicazioni(sessione)
        finally:
            sessione.close()
        self.ubicazione.blockSignals(True)
        self.ubicazione.clear()
        self.ubicazione.addItem("—", "")
        for u in liste:
            self.ubicazione.addItem(u, u)
        self.ubicazione.blockSignals(False)

    def _mostra_movimenti(self) -> None:
        sessione = self._factory()
        try:
            movimenti = consultazione.ultimi_movimenti(sessione, limite=12)
        finally:
            sessione.close()
        t = tema_attivo()
        righe = []
        for m in movimenti:
            carico = m.tipo.value == "CARICO"
            segno = "+" if carico else "−"
            colore = t.ok if carico else t.pericolo
            data_ora = m.data_ora if isinstance(m.data_ora, datetime) else datetime.fromisoformat(m.data_ora)
            data = data_ora.strftime("%d/%m %H:%M")
            righe.append(
                f'<span style="color:{colore};font-weight:700">{segno} {m.quantita}</span> '
                f'{m.pezzo.profilo.codice} · {m.pezzo.colore.nome_visualizzato} · {m.pezzo.lunghezza_mm} mm<br>'
                f'<span style="color:{t.testo_debole};font-size:{px(12.5)}px">'
                f'{data} · {m.utente or ""} · {m.causale or ""}</span>'
            )
        if righe:
            self.movimenti.setHtml("<br>".join(righe))
        else:
            self.movimenti.setHtml(f'<span style="color:{t.testo_debole}">Nessun movimento</span>')

    # ------------------------------------------------------------------
    # scansione
    # ------------------------------------------------------------------
    def _su_texto_barcode(self, testo: str) -> None:
        """Lo scanner "digita" il barcode: compila i campi appena leggibile."""
        if self._compila_dal_barcode(testo):
            # non toccare il focus: lo scanner può continuare a scrivere
            pass

    def _su_invio(self) -> None:
        """Invio sul campo barcode: salva se i campi sono già compilati."""
        if self._campi_compilati():
            self.salva_carico()
        else:
            self._compila_dal_barcode(self.barcode.text())

    def _campi_compilati(self) -> bool:
        return bool(
            self.codice.text().strip()
            and self.colore.text().strip()
            and self.lunghezza.text().strip()
        )

    def _compila_dal_barcode(self, testo: str) -> bool:
        """Compila i campi da un barcode ``CODICE-COLORE-LUNGHEZZA``."""
        parti = [p for p in (testo or "").strip().split("-") if p != ""]
        if len(parti) < 3 or not parti[-1].isdigit():
            return False
        self.codice.setText(parti[0])
        self.colore.setText("-".join(parti[1:-1]))
        self.lunghezza.setText(parti[-1])
        if not self.quantita.text().strip():
            self.quantita.setText("1")
        return True

    # ------------------------------------------------------------------
    def salva_carico(self) -> None:
        if not self._campi_compilati():
            QMessageBox.warning(self, "Carico", "Compila codice, colore e lunghezza.")
            return
        try:
            quantita = int(self.quantita.text() or 0)
            lunghezza = int(self.lunghezza.text() or 0)
        except ValueError:
            QMessageBox.warning(self, "Carico", "Lunghezza o quantità non valide.")
            return
        if quantita <= 0 or lunghezza <= 0:
            QMessageBox.warning(self, "Carico", "Lunghezza e quantità devono essere maggiori di zero.")
            return

        ubicazione = self.ubicazione.currentText().strip()
        try:
            sessione = self._factory()
            try:
                carica(
                    sessione,
                    codice=self.codice.text(),
                    colore=self.colore.text(),
                    lunghezza_mm=lunghezza,
                    quantita=quantita,
                    utente=self._utente or "operatore",
                    causale=self.causale.text().strip() or "Carico",
                    ubicazione=ubicazione or None,
                )
            finally:
                sessione.close()
        except ProfiloNonTrovatoError as errore:
            QMessageBox.critical(self, "Carico", str(errore))
            return
        except Exception as errore:  # noqa: BLE001
            QMessageBox.critical(self, "Carico", f"Errore di carico: {errore}")
            return

        self.barcode.clear()
        self.codice.clear()
        self.colore.clear()
        self.lunghezza.clear()
        self.quantita.setText("1")
        self.ubicazione.setCurrentIndex(0)
        self.causale.clear()
        self._popola_ubicazioni()
        self._mostra_movimenti()
        self.cambiato.emit()
