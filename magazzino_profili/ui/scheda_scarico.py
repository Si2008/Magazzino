"""Scheda Scarico: riduzione di giacenza da barcode, con causale."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..services import consultazione, scarica
from ..services.richiamo_vassoi import numero_vassoio
from . import registro_colori
from .collega_telefono import crea_pulsante_telefono
from .componenti import (
    Anteprima,
    ListaMovimenti,
    MessaggioErrore,
    Stepper,
    bottone,
    campo_con_etichetta,
    chip,
)
from .messaggi import chiedi_conferma, mostra_errore
from .richiamo_vassoi import conferma_simulazione
from .tema import M, rem, tema_attivo, inchiostro_contrasto


def _luminanza(hex_val: str) -> float:
    """Luminanza percepita (0–1) di un colore ``#rrggbb`` (per il contrasto del chip)."""
    from PySide6.QtGui import QColor

    c = QColor(hex_val)
    return (0.2126 * c.red() + 0.7152 * c.green() + 0.0722 * c.blue()) / 255.0


class SchedaScarico(QWidget):
    """Form di scarico pezzi da barcode."""

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

        titolo = QLabel("Scarico merce", card)
        titolo.setObjectName("TitoloCard")
        testa = QHBoxLayout()
        testa.setSpacing(M.GAP_SM)
        testa.addWidget(titolo, 1)
        self.btn_telefono = crea_pulsante_telefono(card)
        self.btn_telefono.clicked.connect(self.telefono_richiesto)
        testa.addWidget(self.btn_telefono, 0, Qt.AlignmentFlag.AlignVCenter)
        v.addLayout(testa)

        suggerimento = QLabel(
            "Scansiona il barcode (il lettore invia Invio in automatico) oppure digitalo.",
            card,
        )
        suggerimento.setObjectName("Suggerimento")
        suggerimento.setWordWrap(True)
        v.addWidget(suggerimento)

        self.barcode = QLineEdit(card)
        self.barcode.setProperty("classe", "grande")
        self.barcode.setPlaceholderText("Scansiona o digita il barcode del pezzo da scaricare…")
        self.barcode.setMinimumHeight(rem(3.0))
        self.barcode.returnPressed.connect(self._su_invio)
        v.addWidget(campo_con_etichetta("Barcode", self.barcode, card))
        self.simula_vassoio = bottone("Simula richiamo vassoio", parent=card)
        self.simula_vassoio.setAutoDefault(False)
        self.simula_vassoio.setEnabled(False)
        self.simula_vassoio.clicked.connect(self._simula_vassoio)
        v.addWidget(self.simula_vassoio)
        self.barcode.textChanged.connect(self._aggiorna_anteprima)

        stepper = Stepper(valore=1, minimo=1, parent=card)
        self.quantita = stepper.campo  # quantita.text()/setText continuano a funzionare
        self.causale = QLineEdit(card)
        self.causale.setPlaceholderText("Causale (obbligatoria)")
        riga = QHBoxLayout()
        riga.setSpacing(M.GAP_SM)
        riga.addWidget(campo_con_etichetta("Quantità (pz)", stepper, card), 1)
        riga.addWidget(campo_con_etichetta("Causale (obbligatoria)", self.causale, card), 1)
        v.addLayout(riga)

        chips = QHBoxLayout()
        chips.setSpacing(rem(0.375))
        for nome in ("Lavorazione", "Vendita", "Scarto"):
            chips.addWidget(chip(nome, self.causale, card))
        chips.addStretch(1)
        v.addLayout(chips)

        self.messaggio = MessaggioErrore(card)
        v.addWidget(self.messaggio)

        self.anteprima = Anteprima(card)
        self.anteprima.setText("")
        v.addWidget(self.anteprima)

        v.addStretch(1)

        self.salva = bottone("Scarica", "pericolo", "lg", "down", card)
        self.salva.clicked.connect(self.salva_scarico)
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
        self.ricerca_profili = RicercaProfili(self._factory, scarico=True, parent=lato)
        self.ricerca_profili.selezionato.connect(self._seleziona_profilo)
        layout_lato.addWidget(self.ricerca_profili, 3)
        scroller_lato = QScrollArea(lato)
        scroller_lato.setWidgetResizable(True)
        scroller_lato.setMinimumHeight(rem(3))
        scroller_lato.setMaximumHeight(rem(9))
        self.dettagli_elenco = bottone("Dettagli e ultimi movimenti", dim="sm", parent=lato)
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
        self.dettaglio_selezione = QLabel("Seleziona il pezzo da scaricare: misura e vassoio sono nell’elenco.", lato)
        self.dettaglio_selezione.setObjectName("Dim")
        self.dettaglio_selezione.setWordWrap(True)
        vl.addWidget(self.dettaglio_selezione)
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

        self._mostra_movimenti()
        self.barcode.setFocus()

    # ------------------------------------------------------------------ dati
    def _mostra_movimenti(self) -> None:
        sessione = self._factory()
        try:
            movimenti = consultazione.ultimi_movimenti(sessione, limite=12)
        finally:
            sessione.close()
        self.movimenti.imposta(movimenti)

    # ------------------------------------------------------------------ anteprima
    def _aggiorna_anteprima(self, _testo: str) -> None:
        """Mostra il pezzo riconosciuto e la giacenza disponibile prima dello scarico."""
        self.simula_vassoio.setEnabled(False)
        valore = self.barcode.text().strip().upper()
        if not valore:
            self.anteprima.clear()
            return
        sessione = self._factory()
        try:
            pezzo = consultazione.pezzo_per_barcode(sessione, valore)
        finally:
            sessione.close()
        if pezzo is None:
            self.anteprima.setText("Nessun pezzo con questo barcode.")
            return

        self.simula_vassoio.setEnabled(pezzo.quantita > 0 and numero_vassoio(pezzo.numero_vassoio) is not None)

        try:
            quantita = int(self.quantita.text())
        except ValueError:
            quantita = 0
        giacenza = pezzo.quantita
        dopo = giacenza - quantita
        t = tema_attivo()
        # Fase 8: il chip mostra il colore REALE del codice dal registro unico:
        # confermato → suggerimento dal codice → non definito (contorno neutro).
        swatch = registro_colori.registro().swatch(pezzo.colore.codice_normalizzato)
        dim = t.testo_dim
        flusso = f'<div style="font-size:{M.FONT_FLUSSO}px;font-weight:700">'
        colore_flusso = t.pericolo if dopo < 0 else t.testo
        righe = [
            f'<div style="font-size:{M.FONT_LAT_TITOLO + 4}px;font-weight:800">{pezzo.profilo.codice}</div>',
        ]
        from html import escape
        if getattr(pezzo,'_commessa_cognome',''):
            righe.append('Commessa: '+escape(pezzo._commessa_cognome))
        if pezzo.profilo.descrizione:
            righe.append(
                f'<div style="color:{dim};font-size:{M.FONT_SMALL}px">{pezzo.profilo.descrizione}</div>'
            )
        if not swatch.definito:
            chip = (
                f'<span style="border:1.5px solid {dim};color:{dim};'
                f'border-radius:999px;padding:3px 10px;font-weight:700">{pezzo.colore.nome_visualizzato}</span>'
            )
        else:
            # testo leggibile: luminanza del primo colore > 0.6 → testo scuro, altrimenti chiaro
            sfondo_chip = swatch.colori[0] if len(swatch.colori) == 1 else t.carta2
            testo_chip = inchiostro_contrasto(sfondo_chip)
            chip = (
                f'<span style="background:{sfondo_chip};color:{testo_chip};'
                f'border-radius:999px;padding:3px 10px;font-weight:700">{pezzo.colore.nome_visualizzato}</span>'
            )
        righe.append(
            f'<div style="margin-top:6px">{chip}'
            f"&nbsp; {self._numero_it(pezzo.lunghezza_mm)} mm</div>"
        )
        if pezzo.ubicazione:
            righe.append(
                f'<div style="color:{dim};font-size:{M.FONT_SMALL}px">Ubicazione: {pezzo.ubicazione}</div>'
            )
        righe.append(f"giacenza: {self._numero_it(giacenza)} pz")
        righe.append(
            f"Giacenza dopo lo scarico"
            f'{flusso}<span style="color:{colore_flusso}">{self._numero_it(giacenza)} → '
            f"{self._numero_it(dopo)} pezzi</span></div>"
        )
        self.anteprima.setText("<br>".join(righe))

    def _simula_vassoio(self) -> None:
        barcode = self.barcode.text().strip().upper()
        with self._factory() as sessione:
            pezzo = consultazione.pezzo_per_barcode(sessione, barcode)
        vassoio = numero_vassoio(pezzo.numero_vassoio) if pezzo is not None and pezzo.quantita > 0 else None
        if vassoio is None:
            self.simula_vassoio.setEnabled(False)
            self.messaggio.mostra("Il pezzo non è più disponibile o non ha un vassoio valido.")
            return

        conferma_simulazione(
            self, codice=pezzo.profilo.codice, descrizione=pezzo.profilo.descrizione,
            barcode=barcode, vassoio=vassoio, origine="scarico",
            selezione_attiva=lambda: self.barcode.text().strip().upper() == barcode,
        )

    def _seleziona_profilo(self, scelta):
        precedente = self._profilo_da_elenco
        self._profilo_da_elenco = scelta
        if scelta is None:
            if precedente is not None:
                self.barcode.clear()
            self.dettaglio_selezione.setText("Nessun pezzo selezionato.")
            return
        self.barcode.setText(scelta.barcode)
        self.quantita.setText("1")
        self.dettaglio_selezione.setText(
            f"{scelta.codice} · {scelta.colore} · {scelta.lunghezza_mm} mm\n"
            f"Vassoio: {scelta.vassoio or 'Non assegnato'} · Barcode: {scelta.barcode}")

    def aggiorna_tema(self):
        self._aggiorna_anteprima(self.barcode.text())

    def showEvent(self, evento):
        self.ricerca_profili.aggiorna()
        super().showEvent(evento)

    @staticmethod
    def _numero_it(n: int) -> str:
        return f"{n:,}".replace(",", ".")

    # ------------------------------------------------------------------ salvataggio
    def ricevi_scansione(self, barcode: str) -> None:
        """Barcode dal telefono: compila il campo e salva come farebbe un lettore con Invio."""
        self.barcode.setText(barcode.strip().upper())
        return self._su_invio()

    def _su_invio(self) -> None:
        if not self.causale.text().strip():
            self.messaggio.mostra("La causale è obbligatoria.")
            return
        return self.salva_scarico()

    def salva_scarico(self) -> None:
        if not self.causale.text().strip():
            self.messaggio.mostra("La causale è obbligatoria.")
            return
        testo = self.barcode.text().strip()
        if not testo:
            self.messaggio.mostra("Compila il barcode.")
            return
        try:
            quantita = int(self.quantita.text() or 0)
        except ValueError:
            self.messaggio.mostra("Quantità non valida.")
            return
        if quantita <= 0:
            self.messaggio.mostra("La quantità deve essere maggiore di zero.")
            return
        # Uscita totale: la giacenza diventa zero. Serve conferma esplicita.
        sessione = self._factory()
        try:
            pezzo = consultazione.pezzo_per_barcode(sessione, testo.upper())
            giacenza = pezzo.quantita if pezzo is not None else None
            descrizione = (
                f"{pezzo.profilo.codice} · {pezzo.colore.nome_visualizzato} · {pezzo.lunghezza_mm} mm"
                if pezzo is not None
                else ""
            )
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
                scarica(
                    sessione,
                    barcode=testo,
                    quantita=quantita,
                    utente=self._utente or "operatore",
                    causale=self.causale.text().strip(),
                )
            finally:
                sessione.close()
        except Exception as errore:  # noqa: BLE001 - spiegato all'utente, dettaglio nel log
            mostra_errore(self, "Scarico", errore, "Lo scarico")
            return

        self._azzera_form()
        self.ricerca_profili.aggiorna()
        self._mostra_movimenti()
        self.cambiato.emit()
        return True

    def _azzera_form(self) -> None:
        self.barcode.clear()
        self.quantita.setText("1")
        self.causale.clear()
        self.messaggio.mostra("")
        self.anteprima.clear()
