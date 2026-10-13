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

import html
from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIntValidator
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
from .messaggi import mostra_errore
from .tema import px, tema_attivo


def _etichetta(testo: str, parent: QWidget) -> QLabel:
    """Etichetta visibile sopra un campo (il testo segnaposto non basta)."""
    t = tema_attivo()
    lab = QLabel(testo, parent)
    lab.setWordWrap(True)
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


_TIPO_MOVIMENTO = {
    "CARICO": ("▲ CARICATO", "ok", "+"),
    "SCARICO": ("▼ SCARICATO", "pericolo", "−"),
    "RETTIFICA": ("● RETTIFICA", "avviso", "−"),
}


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

        vf.addWidget(_etichetta("Barcode", form))
        self.barcode = QLineEdit(form)
        self.barcode.setPlaceholderText("Scansiona o digita il barcode…")
        self.barcode.setStyleSheet(
            f"font-size: {px(17)}px; font-weight: 700; padding: {px(11)} {px(13)};"
        )
        self.barcode.returnPressed.connect(self._su_invio)
        self.barcode.textChanged.connect(self._su_texto_barcode)
        vf.addWidget(self.barcode)
        vf.addWidget(_etichetta("Oppure inserisci i dati a mano (per un pezzo nuovo servono codice, colore e lunghezza)", form))

        self.codice = QLineEdit(form)
        self.codice.setPlaceholderText("Es. AB12")
        self.colore = QLineEdit(form)
        self.colore.setPlaceholderText("Es. AN007")
        riga_codici = QHBoxLayout()
        riga_codici.addWidget(_con_etichetta("Codice profilo", self.codice), 1)
        riga_codici.addWidget(_con_etichetta("Colore", self.colore), 1)
        vf.addLayout(riga_codici)

        self.lunghezza = QLineEdit(form)
        self.lunghezza.setPlaceholderText("Es. 6000")
        self.lunghezza.setValidator(QIntValidator(1, 99_999_999, self))
        self.quantita = QLineEdit(form)
        self.quantita.setPlaceholderText("Es. 12")
        self.quantita.setValidator(QIntValidator(1, 99_999_999, self))
        self.quantita.setText("1")
        riga_lung_quant = QHBoxLayout()
        riga_lung_quant.addWidget(_con_etichetta("Lunghezza (mm)", self.lunghezza), 1)
        riga_lung_quant.addWidget(_con_etichetta("Quantità (pz)", self.quantita), 1)
        vf.addLayout(riga_lung_quant)

        self.ubicazione = QComboBox(form)
        self.ubicazione.setEditable(True)
        self.ubicazione.setInsertPolicy(QComboBox.NoInsert)
        self.ubicazione.lineEdit().setPlaceholderText("Es. Vassoio 3")
        self.causale = QLineEdit(form)
        self.causale.setPlaceholderText("Es. Arrivo fornitore")
        riga_ubic_caus = QHBoxLayout()
        riga_ubic_caus.addWidget(
            _con_etichetta("Ubicazione (se il pezzo non ne ha una)", self.ubicazione), 1
        )
        riga_ubic_caus.addWidget(_con_etichetta("Causale (facoltativa)", self.causale), 1)
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
        # Nessuna voce "vuota" selezionabile: un valore segnaposto diventerebbe
        # un'ubicazione reale. Il campo parte vuoto e accetta testo libero.
        for u in liste:
            self.ubicazione.addItem(u, u)
        self.ubicazione.setCurrentIndex(-1)
        self.ubicazione.setEditText("")
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
            etichetta_tipo, variante, segno = _TIPO_MOVIMENTO.get(m.tipo.value, (m.tipo.value, "neutro", ""))
            colore = {"ok": t.ok, "pericolo": t.pericolo, "avviso": t.avviso}.get(variante, t.testo_dim)
            data_ora = m.data_ora if isinstance(m.data_ora, datetime) else datetime.fromisoformat(m.data_ora)
            data = data_ora.strftime("%d/%m %H:%M")
            righe.append(
                f'<span style="color:{colore};font-weight:700">{etichetta_tipo}</span> &nbsp; '
                f'<span style="color:{colore};font-weight:700">{segno} {m.quantita}</span> '
                f'{html.escape(m.pezzo.profilo.codice)} · {html.escape(m.pezzo.colore.nome_visualizzato)} · {m.pezzo.lunghezza_mm} mm<br>'
                f'<span style="color:{t.testo_debole};font-size:{px(12.5)}px">'
                f'{html.escape(data)} · {html.escape(m.utente or "")} · {html.escape(m.causale or "")}</span>'
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
        """Compila i campi da un barcode ``CODICE-COLORE-LUNGHEZZA``.

        Prima si cerca il pezzo esistente con quel barcode (fonte certa).
        Altrimenti si accetta la scomposizione solo se è unica: più
        codici di profilo in anagrafica compatibili con lo stesso testo
        lasciano i campi vuoti, invece di indovinare.
        """
        valore = (testo or "").strip().upper()
        if not valore:
            return False
        sessione = self._factory()
        try:
            pezzo = consultazione.pezzo_per_barcode(sessione, valore)
            if pezzo is not None:
                scomposizione = [(pezzo.profilo.codice, pezzo.colore.codice_normalizzato, pezzo.lunghezza_mm)]
            else:
                scomposizione = consultazione.candidati_da_barcode(sessione, valore)
        finally:
            sessione.close()
        if len(scomposizione) != 1:
            return False
        codice, colore, lunghezza = scomposizione[0]
        self.codice.setText(codice)
        self.colore.setText(colore)
        self.lunghezza.setText(str(lunghezza))
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
        if ubicazione == "—":  # segnaposto mai da salvare come ubicazione
            ubicazione = ""
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
        except Exception as errore:  # noqa: BLE001 - spiegato all'utente, dettaglio nel log
            mostra_errore(self, "Carico", errore, "Il carico")
            return

        self.barcode.clear()
        self.codice.clear()
        self.colore.clear()
        self.lunghezza.clear()
        self.quantita.setText("1")
        self.ubicazione.setCurrentIndex(-1)
        self.ubicazione.setEditText("")
        self.causale.clear()
        self._popola_ubicazioni()
        self._mostra_movimenti()
        self.cambiato.emit()
