"""Scheda Carico: scannerizzazione/inserimento barcode e giacenza.

Comportamento:

- si scansiona (o si digita) il barcode: i campi (codice, colore,
  lunghezza) si compilano da soli;
- "Salva carico" (o Invio con i campi già compilati) chiude l'operazione;
- ``ubicazione`` è opzionale e viene
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
from .collega_telefono import crea_pulsante_telefono
from .componenti import (
    Anteprima,
    ListaMovimenti,
    MessaggioErrore,
    Stepper,
    bottone,
    campo_con_etichetta,
    divisore,
)
from .messaggi import mostra_errore
from .tema import M, rem, tema_attivo


class SchedaCarico(QWidget):
    """Form di carico pezzi da barcode."""

    cambiato = Signal()

    #: l'utente ha premuto "Collega telefono"
    telefono_richiesto = Signal()

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
        card.setMinimumWidth(M.COLONNA_MIN)
        self.pannello_operazione = card
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
        testa = QHBoxLayout()
        testa.setSpacing(M.GAP_SM)
        testa.addWidget(titolo, 1)
        self.btn_telefono = crea_pulsante_telefono(card)
        self.btn_telefono.clicked.connect(self.telefono_richiesto)
        testa.addWidget(self.btn_telefono, 0, Qt.AlignmentFlag.AlignVCenter)
        v.addLayout(testa)

        suggerimento = QLabel(
            "Scansiona il barcode di un pezzo già presente: i dati si compilano da soli. "
            "Per un pezzo nuovo inserisci codice, colore e lunghezza a mano.",
            card,
        )
        suggerimento.setObjectName("Suggerimento")
        suggerimento.setWordWrap(True)
        v.addWidget(suggerimento)
        self.commessa=QComboBox(card)
        self.commessa.addItem('Nessuna commessa',None)
        v.addWidget(campo_con_etichetta('Commessa del nuovo pezzo',self.commessa,card))
        self._ricarica_commesse()

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
        riga_uc = QHBoxLayout()
        riga_uc.setSpacing(M.GAP_SM)
        riga_uc.addWidget(campo_con_etichetta("Ubicazione (se il pezzo non ne ha una)", self.ubicazione, card), 1)
        v.addLayout(riga_uc)
        self.numero_vassoio = QLineEdit(card)
        self.numero_vassoio.setMaxLength(128)
        self.numero_vassoio.setPlaceholderText("Es. 4 oppure Vassoio 4")
        v.addWidget(campo_con_etichetta("Numero di vassoio", self.numero_vassoio, card))


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
        lato.setMinimumWidth(M.COLONNA_MIN)
        self.pannello_profili = lato
        layout_lato = QVBoxLayout(lato)
        layout_lato.setContentsMargins(M.CARD_PAD, M.CARD_PAD, M.CARD_PAD, M.CARD_PAD)
        layout_lato.setSpacing(M.GAP_SM)
        from .ricerca_profili import RicercaProfili
        self._profilo_da_elenco = None
        self.ricerca_profili = RicercaProfili(self._factory, parent=lato)
        self.ricerca_profili.selezionato.connect(self._seleziona_profilo)
        layout_lato.addWidget(self.ricerca_profili, 3)
        scroller_lato = QScrollArea(lato)
        scroller_lato.setWidgetResizable(True)
        scroller_lato.setMinimumHeight(rem(3))
        scroller_lato.setMaximumHeight(rem(9))
        self.dettagli_elenco = bottone("Sezione e ultimi movimenti", dim="sm", parent=lato)
        self.dettagli_elenco.setCheckable(True)
        self.dettagli_elenco.setToolTip("Apri o richiudi i dettagli lasciando spazio all'elenco profili")
        self.dettagli_elenco.toggled.connect(scroller_lato.setVisible)
        layout_lato.addWidget(self.dettagli_elenco)
        scroller_lato.hide()
        contenuto_lato = QWidget()
        scroller_lato.setWidget(contenuto_lato)
        layout_lato.addWidget(scroller_lato, 2)
        vl = QVBoxLayout(contenuto_lato)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(M.GAP_SM)
        self.dettaglio_selezione = QLabel("Seleziona un profilo per preparare il carico.", lato)
        self.dettaglio_selezione.setObjectName("Dim")
        self.dettaglio_selezione.setWordWrap(True)
        vl.addWidget(self.dettaglio_selezione)
        self._percorso_sezione = None
        self.immagine_sezione = QLabel(lato)
        self.immagine_sezione.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.immagine_sezione.setFixedHeight(rem(9))
        self.immagine_sezione.hide()
        vl.addWidget(self.immagine_sezione)
        self.apri_sezione = bottone("Apri sezione del profilo", parent=lato)
        self.apri_sezione.hide()
        self.apri_sezione.clicked.connect(self._apri_sezione)
        vl.addWidget(self.apri_sezione)
        self.codice.textChanged.connect(self._aggiorna_immagine_sezione)
        titolo_m = QLabel("Ultimi movimenti", lato)
        titolo_m.setObjectName("TitoloCard")
        vl.addWidget(titolo_m)
        self.movimenti = ListaMovimenti(lato)
        area = QScrollArea(lato)
        area.setWidgetResizable(True)
        area.setWidget(self.movimenti)
        area.setMinimumHeight(rem(8))
        vl.addWidget(area, 1)

        from .pannelli import dividi_pannelli
        self.divisione = dividi_pannelli(card, lato, (44, 56), self)
        radice.addWidget(self.divisione)

        self._popola_ubicazioni()
        self._mostra_movimenti()
        self.barcode.setFocus()

    # ------------------------------------------------------------------ dati
    def _seleziona_profilo(self, scelta):
        precedente = self._profilo_da_elenco
        self._profilo_da_elenco = scelta
        if scelta is None:
            if precedente is not None:
                self.barcode.clear()
                self.codice.clear()
                self.lunghezza.clear()
            self.dettaglio_selezione.setText("Nessun profilo selezionato.")
            return
        self.barcode.clear()
        self.codice.setText(scelta.codice)
        self.lunghezza.setText(str(scelta.lunghezza_mm))
        self.dettaglio_selezione.setText(f"{scelta.codice} · {scelta.descrizione}\nLunghezza standard: {scelta.lunghezza_mm} mm")
        self._aggiorna_anteprima()

    def aggiorna_tema(self):
        self._aggiorna_anteprima()
        self._aggiorna_immagine_sezione(self.codice.text())

    def _aggiorna_immagine_sezione(self, codice):
        from ..services.immagini import immagine_per_codice
        from PySide6.QtGui import QImageReader, QPixmap
        from PySide6.QtCore import QSize
        try:
            percorso = immagine_per_codice(codice)
        except (ValueError, OSError):
            percorso = None
        self._percorso_sezione = percorso
        self.immagine_sezione.setVisible(bool(percorso))
        self.apri_sezione.setVisible(bool(percorso))
        if percorso:
            lettore = QImageReader(str(percorso))
            dimensione = lettore.size()
            if dimensione.isValid():
                lettore.setScaledSize(dimensione.scaled(QSize(rem(16), rem(8)), Qt.AspectRatioMode.KeepAspectRatio))
            self.immagine_sezione.setPixmap(QPixmap.fromImage(lettore.read()))

    def _apri_sezione(self):
        if self._percorso_sezione:
            from .visualizzatore_immagine import apri_immagine
            apri_immagine(self._percorso_sezione, self)

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

    def ricevi_scansione(self, barcode: str) -> None:
        """Barcode dal telefono: compila il campo (i dati del pezzo si compilano da soli)."""
        self.barcode.setText(barcode.strip().upper())
        self.barcode.setFocus()
        return self._compila_dal_barcode(self.barcode.text())

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
                self.numero_vassoio.setText(pezzo.numero_vassoio or "")
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
        from sqlalchemy.exc import SQLAlchemyError
        from html import escape
        try:
            with self._factory() as sessione:
                esistente = consultazione.pezzo_per_barcode(sessione, self.barcode.text()) if self.barcode.text().strip() else None
                totale = consultazione.totale_per_combinazione(sessione, codice, colore, lunghezza)
        except SQLAlchemyError:
            self.anteprima.setText("Database non disponibile: impossibile leggere la giacenza.")
            return
        flusso = f'<div style="font-size:{M.FONT_FLUSSO}px;font-weight:700">'
        riga_id = escape(f"{codice} · {colore} · {self._numero_it(lunghezza)} mm")
        if esistente is not None:
            finale = esistente.quantita + quantita
            nota = " · un pezzo fisico" if esistente.unitario else " · etichetta storica aggregata"
            self.anteprima.setText(f"<b>{escape(esistente.barcode)}</b>{nota}"
                f"{flusso}{esistente.quantita} → {finale}</div>" +
                ("Un barcode unitario ammette solo giacenza 0 o 1." if esistente.unitario and finale > 1 else ""))
        else:
            self.anteprima.setText(f"<b>{riga_id}</b>"
                f"{flusso}{self._numero_it(totale)} → {self._numero_it(totale + quantita)} pezzi</div>"
                f"Saranno creati {self._numero_it(quantita)} barcode distinti, uno per ogni pezzo.")

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
                from ..services.pezzi_unitari import crea_pezzi_unitari, ricarica_barcode
                barcode = self.barcode.text().strip()
                esistente = consultazione.pezzo_per_barcode(sessione, barcode) if barcode else None
                sessione.rollback()  # chiude la sola lettura prima della transazione di scrittura
                if esistente is not None:
                    ricarica_barcode(sessione, barcode, quantita, self._utente or "operatore",
                                     "Rientro pezzo")
                else:
                    crea_pezzi_unitari(
                    sessione,
                    codice=self.codice.text(),
                    colore=self.colore.text(),
                    lunghezza_mm=lunghezza,
                    quantita=quantita,
                    utente=self._utente or "operatore",
                    causale="Carico",
                    ubicazione=ubicazione or None,
                        numero_vassoio=self.numero_vassoio.text().strip() or None,
                        commessa_id=self.commessa.currentData(),
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

    def _ricarica_commesse(self):
        from ..services.archivio_commesse import elenco
        selezionata=self.commessa.currentData();self.commessa.clear();self.commessa.addItem('Nessuna commessa',None)
        for c in elenco(self._factory):self.commessa.addItem(f'{c.cognome} · {c.nome}',c.id)
        i=self.commessa.findData(selezionata)
        if i>=0:self.commessa.setCurrentIndex(i)

    def showEvent(self,event):
        self._ricarica_commesse()
        self.ricerca_profili.aggiorna()
        super().showEvent(event)

    def _azzera_form(self) -> None:
        self.barcode.clear()
        self.codice.clear()
        self.colore.clear()
        self.lunghezza.clear()
        self.quantita.setText("1")
        self.ubicazione.setCurrentIndex(-1)
        self.ubicazione.setEditText("")
        self.numero_vassoio.clear()
        self.messaggio.mostra("")
        self._aggiorna_anteprima()
