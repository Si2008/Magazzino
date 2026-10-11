"""Scheda Profili: elenco, creazione, modifica e immagine della sezione.

L'immagine della sezione è un PNG opzionale: può essere importata
(copiata nella cartella del programma) e rimossa (il file non viene
cancellato da disco, toglie solo il riferimento).
"""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..domain import Profilo  # modello per sessione.get
from ..services import anagrafica
from ..services import consultazione
from .tema import px, tema_attivo


class SchedaProfilo(QWidget):
    """Gestione profili (sezione + peso per metro)."""

    cambiato = Signal()

    def __init__(self, factory, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._factory = factory
        self._profilo_id: int | None = None
        self._immagine_locale: str | None = None  # PNG importato, non ancora salvato
        self._rimossa_in_locales = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(px(14), px(14), px(14), px(14))
        layout.setSpacing(px(14))

        # ---------------- colonna sinistra: elenco ----------------
        vf = QVBoxLayout()
        vf.setContentsMargins(0, 0, 0, 0)
        vf.setSpacing(px(8))
        titolo = QLabel("Profili")
        titolo.setStyleSheet(f"font-size: {px(20)}px; font-weight: 800;")
        vf.addWidget(titolo)
        self._elenco = QListWidget(self)
        vf.addWidget(self._elenco, 1)
        self._elenco.currentItemChanged.connect(self._su_selezione)
        layout.addLayout(vf, 2)

        # ---------------- colonna destra: form ----------------
        form = QWidget(self)
        vl = QVBoxLayout(form)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(px(10))

        self.codice = QLineEdit(form)
        self.codice.setPlaceholderText("codice (es. AB12) — obbligatorio, immutabile")
        self.descrizione = QLineEdit(form)
        self.descrizione.setPlaceholderText("descrizione (es. Angolo 40x40) — obbligatoria")
        self.peso = QLineEdit(form)
        self.peso.setPlaceholderText("peso kg/metro (es. 1,28) — obbligatorio")
        self.lunghezza = QLineEdit(form)
        self.lunghezza.setPlaceholderText("lunghezza standard (mm) — obbligatoria")
        for c in (self.codice, self.descrizione, self.peso, self.lunghezza):
            c.setStyleSheet(f"font-size: {px(14)}px; padding: {px(9)} {px(11)};")
            vl.addWidget(c)

        riga_img = QHBoxLayout()
        self._anteprima = QLabel("—", form)
        self._anteprima.setFixedSize(px(96), px(96))
        self._anteprima.setAlignment(Qt.AlignCenter)
        self._anteprima.setStyleSheet(
            f"background: {tema_attivo().carta2}; border: 1px dashed {tema_attivo().bordo_forte}; border-radius: {px(9)}px;"
        )
        riga_img.addWidget(self._anteprima)
        btn_imp = QPushButton("Importa PNG…", form)
        btn_imp.clicked.connect(self._importa_immagine)
        riga_img.addWidget(btn_imp)
        btn_rimuovi = QPushButton("Rimuovi", form)
        btn_rimuovi.setProperty("classe", "pericolo")
        btn_rimuovi.clicked.connect(self._rimuovi_immagine)
        riga_img.addWidget(btn_rimuovi)
        riga_img.addStretch(1)
        vl.addLayout(riga_img)

        riga_btn = QHBoxLayout()
        self.salva = QPushButton("Salva profilo", form)
        self.salva.setProperty("classe", "primario")
        self.salva.setStyleSheet(f"font-size: {px(15)}px; padding: {px(11)} {px(18)};")
        self.salva.clicked.connect(self.salva_profilo)
        riga_btn.addWidget(self.salva)
        btn_nuovo = QPushButton("Nuovo", form)
        btn_nuovo.clicked.connect(self._nuovo)
        riga_btn.addWidget(btn_nuovo)
        riga_btn.addStretch(1)
        vl.addLayout(riga_btn)
        vl.addStretch(1)

        layout.addWidget(form, 3)

        self._rinfresca_elenco()

    # ------------------------------------------------------------------
    def _rinfresca_elenco(self) -> None:
        sessione = self._factory()
        try:
            profili = consultazione.lista_profilo(sessione)
        finally:
            sessione.close()
        self._elenco.blockSignals(True)
        self._elenco.clear()
        for p in profili:
            testo = p.codice
            if p.descrizione:
                testo += f"  —  {p.descrizione}"
            voce = QListWidgetItem(testo)
            voce.setData(Qt.UserRole, p.id)
            self._elenco.addItem(voce)
        self._elenco.blockSignals(False)

    def _su_selezione(self, corrente: QListWidgetItem | None, _precedente: QListWidgetItem | None) -> None:
        if corrente is None:
            self._vuota_form()
            return
        pid = corrente.data(Qt.UserRole)
        sessione = self._factory()
        try:
            p = sessione.get(Profilo, pid)
            # forza il caricamento delle relazioni
            codice, descrizione = p.codice, p.descrizione
            peso = p.peso_kg_per_metro
            lunghezza = p.lunghezza_standard_mm
            immagine = p.immagine_sezione
        finally:
            sessione.close()
        self._profilo_id = pid
        self._immagine_locale = None
        self._rimossa_in_locales = False
        self.codice.setText(codice or "")
        self.descrizione.setText(descrizione or "")
        self.peso.setText(f"{Decimal(str(peso))}".replace(".", ",")) if peso is not None else self.peso.setText("")
        self.lunghezza.setText(str(lunghezza)) if lunghezza else self.lunghezza.setText("")
        self._mostra_immagine(immagine)

    def _mostra_immagine(self, percorso: str | None) -> None:
        if percorso and QPixmap(percorso).isNull() is False:
            self._anteprima.setPixmap(
                QPixmap(percorso).scaled(px(96), px(96), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        else:
            self._anteprima.setText("—")

    def _vuota_form(self) -> None:
        self._profilo_id = None
        self._immagine_locale = None
        self._rimossa_in_locales = False
        for c in (self.codice, self.descrizione, self.peso, self.lunghezza):
            c.clear()
        self._anteprima.setText("—")

    def _nuovo(self) -> None:
        self._vuota_form()
        self.codice.setFocus()

    # ------------------------------------------------------------------
    def _importa_immagine(self) -> None:
        percorso, _ = QFileDialog.getOpenFileName(self, "Importa immagine sezione", "", "PNG (*.png)")
        if not percorso:
            return
        self._immagine_locale = percorso
        self._rimossa_in_locales = False
        self._mostra_immagine(percorso)

    def _rimuovi_immagine(self) -> None:
        """Segna la rimozione dell'immagine (il file resta su disco)."""
        self._rimossa_in_locales = True
        self._immagine_locale = None
        self._anteprima.setText("—")

    # ------------------------------------------------------------------
    def salva_profilo(self) -> None:
        codice = self.codice.text().strip()
        descrizione = self.descrizione.text().strip()
        try:
            peso = float(self.peso.text().strip().replace(",", ".")) if self.peso.text().strip() else None
            lunghezza = int(self.lunghezza.text().strip()) if self.lunghezza.text().strip() else None
        except ValueError:
            QMessageBox.warning(self, "Profili", "Peso o lunghezza non validi.")
            return

        nuovo = self._profilo_id is None
        if nuovo and (not codice or not descrizione or peso is None or lunghezza is None):
            QMessageBox.warning(
                self, "Profili", "Per un nuovo profilo codice, descrizione, peso e lunghezza sono obbligatori."
            )
            return

        try:
            sessione = self._factory()
            try:
                if nuovo:
                    p = anagrafica.crea_profilo(
                        sessione,
                        codice=codice,
                        descrizione=descrizione,
                        peso_kg_per_metro=peso,
                        lunghezza_standard_mm=lunghezza,
                    )
                else:
                    p = anagrafica.aggiorna_profilo(
                        sessione,
                        self._profilo_id,
                        descrizione=descrizione or None,
                        peso_kg_per_metro=peso,
                        lunghezza_standard_mm=lunghezza,
                    )
                if self._rimossa_in_locales:
                    anagrafica.rimuovi_immagine_sezione(sessione, p.id)
                elif self._immagine_locale:
                    anagrafica.associa_immagine_sezione(sessione, p.id, self._immagine_locale)
            finally:
                sessione.close()
        except Exception as errore:  # noqa: BLE001
            QMessageBox.critical(self, "Profili", f"Errore: {errore}")
            return

        self._rinfresca_elenco()
        self.cambiato.emit()
