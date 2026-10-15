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

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..services import consultazione, carica
from .componenti import (
    Anteprima,
    ListaMovimenti,
    MessaggioErrore,
    Stepper,
    bottone,
    campo_con_etichetta,
    chip,
    divisore,
)
from .messaggi import mostra_errore
from .tema import M, rem, tema_attivo


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

        radice = QHBoxLayout(self)
        radice.setContentsMargins(M.PAG_H, M.PAG_T, M.PAG_H, M.PAG_B)
        radice.setSpacing(M.GAP)

        card = QFrame(self)
        card.setObjectName("Card")
        card.setFixedWidth(M.SPLIT_SX)
        # Il form è alto più dello schermo: come nel mockup (`.main{overflow:auto}`)
        # il contenuto scorre dentro la card invece di essere compresso.
        vcard = QVBoxLayout(card)
        vcard.setContentsMargins(0, 0, 0, 0)
        scroller = QScrollArea(card)
        scroller.setObjectName("ScorrimentoCard")
        scroller.setWidgetResizable(True)
        scroller.setFrameShape(QFrame.Shape.NoFrame)
        contenuto = QWidget()
        v = QVBoxLayout(contenuto)
        v.setContentsMargins(M.CARD_PAD, M.CARD_PAD, M.CARD_PAD, M.CARD_PAD)
        v.setSpacing(M.GAP_SM)

        titolo = QLabel("Carico merce", card)
        titolo.setObjectName("TitoloCard")
        v.addWidget(titolo)

        suggerimento = QLabel(
            "Scansiona il barcode di un pezzo già presente: i dati si compilano da soli. "
            "Per un pezzo nuovo inserisci codice, colore e lunghezza a mano.",
            card,
        )
        suggerimento.setObjectName("Suggerimento")
        suggerimento.setWordWrap(True)
        v.addWidget(suggerimento)

        self.barcode = QLineEdit(card)
        self.barcode.setProperty("classe", "grande")
        self.barcode.setPlaceholderText("Scansiona o digita il barcode…")
        self.barcode.setMinimumHeight(rem(3.0))
        self.barcode.returnPressed.connect(self._su_invio)
        self.barcode.textChanged.connect(self._su_texto_barcode)
        v.addWidget(campo_con_etichetta("Barcode", self.barcode, card))

        v.addWidget(divisore("oppure inserisci i dati a mano", card))

        self.codice = QLineEdit(card)
        self.codice.setPlaceholderText("Es. AB12")
        self.colore = QLineEdit(card)
        self.colore.setPlaceholderText("Es. AN007")
        riga = QHBoxLayout()
        riga.setSpacing(M.GAP_SM)
        riga.addWidget(campo_con_etichetta("Codice profilo", self.codice, card), 1)
        riga.addWidget(campo_con_etichetta("Colore", self.colore, card), 1)
        v.addLayout(riga)

        self.lunghezza = QLineEdit(card)
        self.lunghezza.setPlaceholderText("Es. 6000")
        self.lunghezza.setValidator(QIntValidator(1, 99_999_999, card))
        stepper = Stepper(valore=1, minimo=1, parent=card)
        self.quantita = stepper.campo  # quantita.text()/setText continuano a funzionare
        riga_lq = QHBoxLayout()
        riga_lq.setSpacing(M.GAP_SM)
        riga_lq.addWidget(campo_con_etichetta("Lunghezza (mm)", self.lunghezza, card), 1)
        riga_lq.addWidget(campo_con_etichetta("Quantità (pz)", stepper, card), 1)
        v.addLayout(riga_lq)

        self.ubicazione = QComboBox(card)
        self.ubicazione.setEditable(True)
        self.ubicazione.setInsertPolicy(QComboBox.NoInsert)
        self.ubicazione.lineEdit().setPlaceholderText("Es. Vassoio 3")
        self.causale = QLineEdit(card)
        self.causale.setPlaceholderText("Es. Arrivo fornitore")
        riga_uc = QHBoxLayout()
        riga_uc.setSpacing(M.GAP_SM)
        riga_uc.addWidget(campo_con_etichetta("Ubicazione (se il pezzo non ne ha una)", self.ubicazione, card), 1)
        riga_uc.addWidget(campo_con_etichetta("Causale (facoltativa)", self.causale, card), 1)
        v.addLayout(riga_uc)

        chips = QHBoxLayout()
        chips.setSpacing(rem(0.375))
        for nome in ("Arrivo fornitore", "Reso", "Rettifica inventario"):
            chips.addWidget(chip(nome, self.causale, card))
        chips.addStretch(1)
        v.addLayout(chips)

        self.messaggio = MessaggioErrore(card)
        v.addWidget(self.messaggio)

        self.anteprima = Anteprima(card)
        self.anteprima.setText("Compila profilo e colore per vedere l'anteprima della giacenza.")
        v.addWidget(self.anteprima)

        v.addStretch(1)

        self.salva = bottone("Salva carico", "ok", "lg", "plus", card)
        self.salva.clicked.connect(self.salva_carico)
        v.addWidget(self.salva)
        scroller.setWidget(contenuto)
        vcard.addWidget(scroller)

        # ---------------- colonna destra: movimenti recenti ----------------
        lato = QFrame(self)
        lato.setObjectName("Card")
        vl = QVBoxLayout(lato)
        vl.setContentsMargins(M.CARD_PAD, M.CARD_PAD, M.CARD_PAD, M.CARD_PAD)
        vl.setSpacing(M.GAP_SM)
        titolo_m = QLabel("Ultimi movimenti", lato)
        titolo_m.setObjectName("TitoloCard")
        vl.addWidget(titolo_m)
        self.movimenti = ListaMovimenti(lato)
        area = QScrollArea(lato)
        area.setWidgetResizable(True)
        area.setWidget(self.movimenti)
        vl.addWidget(area, 1)

        radice.addWidget(card)
        radice.addWidget(lato, 1)

        self._popola_ubicazioni()
        self._mostra_movimenti()
        self.barcode.setFocus()

    # ------------------------------------------------------------------ dati
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
        self.movimenti.imposta(movimenti)

    # ------------------------------------------------------------------ scansione
    def _su_texto_barcode(self, _testo: str) -> None:
        """Lo scanner "digita" il barcode: compila i campi appena leggibile."""
        self._compila_dal_barcode(self.barcode.text())
        self._aggiorna_anteprima()

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

    # ------------------------------------------------------------------ anteprima
    def _aggiorna_anteprima(self) -> None:
        """Anteprima della giacenza dopo il carico (senza scrivere nulla)."""
        codice = self.codice.text().strip().upper()
        colore = self.colore.text().strip().upper()
        if not (codice and colore):
            self.anteprima.setText("Compila profilo e colore per vedere l'anteprima della giacenza.")
            return
        try:
            lunghezza = int(self.lunghezza.text())
        except ValueError:
            lunghezza = 0
        if lunghezza <= 0:
            self.anteprima.setText("Compila profilo e colore per vedere l'anteprima della giacenza.")
            return
        try:
            quantita = int(self.quantita.text())
        except ValueError:
            quantita = 0
        quantita = max(0, quantita)
        sessione = self._factory()
        try:
            pezzo = consultazione.pezzo_per_combinazione(sessione, codice, colore, lunghezza)
        finally:
            sessione.close()
        flusso = f'<div style="font-size:{M.FONT_FLUSSO}px;font-weight:700">'
        riga_id = f"{codice} · {colore} · {self._numero_it(lunghezza)} mm"
        if pezzo is not None:
            self.anteprima.setText(
                f"Giacenza di <b>{riga_id}</b>"
                f"{flusso}{self._numero_it(pezzo.quantita)} → "
                f"{self._numero_it(pezzo.quantita + quantita)} pezzi</div>"
            )
        else:
            self.anteprima.setText(
                f"<b>{riga_id}</b> — combinazione nuova"
                f"{flusso}0 → {self._numero_it(quantita)} pezzi</div>"
            )

    @staticmethod
    def _numero_it(n: int) -> str:
        s = f"{n:,}".replace(",", ".")
        return s

    # ------------------------------------------------------------------ salvataggio
    def salva_carico(self) -> None:
        if not self._campi_compilati():
            self.messaggio.mostra("Compila codice, colore e lunghezza.")
            return
        try:
            quantita = int(self.quantita.text() or 0)
            lunghezza = int(self.lunghezza.text() or 0)
        except ValueError:
            self.messaggio.mostra("Lunghezza o quantità non valide.")
            return
        if quantita <= 0 or lunghezza <= 0:
            self.messaggio.mostra("Lunghezza e quantità devono essere maggiori di zero.")
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

        self._azzera_form()
        self._popola_ubicazioni()
        self._mostra_movimenti()
        self.cambiato.emit()

    def _azzera_form(self) -> None:
        self.barcode.clear()
        self.codice.clear()
        self.colore.clear()
        self.lunghezza.clear()
        self.quantita.setText("1")
        self.ubicazione.setCurrentIndex(-1)
        self.ubicazione.setEditText("")
        self.causale.clear()
        self.messaggio.mostra("")
        self._aggiorna_anteprima()
