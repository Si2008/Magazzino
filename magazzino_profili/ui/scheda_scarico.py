"""Scheda Scarico: riduzione di giacenza da barcode, con causale."""

from __future__ import annotations

from PySide6.QtCore import Signal
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
from .tema import M, alfa, colore_di_codice, rem, tema_attivo


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

        radice = QHBoxLayout(self)
        radice.setContentsMargins(M.PAG_H, M.PAG_T, M.PAG_H, M.PAG_B)
        radice.setSpacing(M.GAP)

        card = QFrame(self)
        card.setObjectName("Card")
        card.setFixedWidth(M.SPLIT_SX)
        v = QVBoxLayout(card)
        v.setContentsMargins(M.CARD_PAD, M.CARD_PAD, M.CARD_PAD, M.CARD_PAD)
        v.setSpacing(M.GAP_SM)

        titolo = QLabel("Scarico merce", card)
        titolo.setObjectName("TitoloCard")
        v.addWidget(titolo)

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
        self.barcode.textChanged.connect(self._aggiorna_anteprima)
        v.addWidget(campo_con_etichetta("Barcode", self.barcode, card))

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
        valore = (self.barcode.text() or "").strip().upper()
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

        try:
            quantita = int(self.quantita.text())
        except ValueError:
            quantita = 0
        giacenza = pezzo.quantita
        dopo = giacenza - quantita
        t = tema_attivo()
        colore = colore_di_codice(pezzo.colore.codice_normalizzato)
        dim = t.testo_dim
        flusso = f'<div style="font-size:{M.FONT_FLUSSO}px;font-weight:700">'
        colore_flusso = t.pericolo if dopo < 0 else t.testo
        righe = [
            f'<div style="font-size:{M.FONT_LAT_TITOLO + 4}px;font-weight:800">{pezzo.profilo.codice}</div>',
        ]
        if pezzo.profilo.descrizione:
            righe.append(
                f'<div style="color:{dim};font-size:{M.FONT_SMALL}px">{pezzo.profilo.descrizione}</div>'
            )
        righe.append(
            f'<div style="margin-top:6px"><span style="background:{colore};color:{alfa(colore, 0.6)};'
            f'border-radius:999px;padding:3px 10px;font-weight:700">{pezzo.colore.nome_visualizzato}</span>'
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

    @staticmethod
    def _numero_it(n: int) -> str:
        return f"{n:,}".replace(",", ".")

    # ------------------------------------------------------------------ salvataggio
    def _su_invio(self) -> None:
        if not self.causale.text().strip():
            self.messaggio.mostra("La causale è obbligatoria.")
            return
        self.salva_scarico()

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
        self._mostra_movimenti()
        self.cambiato.emit()

    def _azzera_form(self) -> None:
        self.barcode.clear()
        self.quantita.setText("1")
        self.causale.clear()
        self.messaggio.mostra("")
        self.anteprima.clear()
