"""Fase 8: dialogo «Gestione colori» e azioni del menu contestuale dei chip colore.

Azioni condivise tra il dialogo e il menu contestuale dei chip in Inventario:

- :func:`scegli_colore`: ``QColorDialog`` che parte dal colore attuale;
  annullare = nessun cambiamento (nessuna scrittura);
- :func:`conferma_suggerito`: salva il colore suggerito (solo se è un
  suggerimento a tinta unita);
- :func:`ripristina_automatico`: rimuove ``colore_hex`` (con conferma).

Dopo ogni modifica: ``registro_colori.ricarica_da_database`` in una sessione
dedicata + segnale ``colori_cambiati`` (Inventario — e Scarico con selezione
visibile — aggiornano l'interfaccia).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QColorDialog,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..services import colori as colori_servizio
from . import registro_colori
from .componenti import Pillola, bottone
from .messaggi import chiedi_conferma, mostra_errore
from .tema import rem, tema_attivo

_VARIANTE_PILLOLA = {
    registro_colori.CONFERMATO: "ok",
    registro_colori.SUGGERITO: "avviso",
    registro_colori.NON_DEFINITO: "neutro",
}
_TITOLO_PILLOLA = {
    registro_colori.CONFERMATO: "Confermato",
    registro_colori.SUGGERITO: "Suggerito",
    registro_colori.NON_DEFINITO: "Non definito",
}


# ------------------------------------------------------------------ azioni condivise
def _cerca_colore(factory, codice: str) -> int | None:
    """Id del colore con quel codice (normalizzato), oppure ``None``."""
    chiave = (codice or "").upper().strip()
    sessione = factory()
    try:
        for c in colori_servizio.elenco_colori(sessione):
            if (c.codice_normalizzato or "").upper().strip() == chiave:
                return c.id
    finally:
        sessione.close()
    return None


def _salva(factory, parent: QWidget | None, codice: str, valore: str | None) -> bool:
    """Imposta (``#rrggbb``) o rimuove (``None``) il colore di ``codice``.

    Restituisce ``True`` su successo; su errore mostra il messaggio e ``False``.
    Dopo il salvataggio ricarica il registro (nuova sessione) e segnala il cambio.
    """
    colore_id = _cerca_colore(factory, codice)
    if colore_id is None:
        mostra_errore(parent, "Gestione colori", LookupError(f"colore {codice} inesistente"), "il salvataggio")
        return False
    # sessione NUOVA: imposta_colore_hex apre ``session.begin()``
    sessione = factory()
    try:
        try:
            colori_servizio.imposta_colore_hex(sessione, colore_id, valore)
        except Exception as e:  # noqa: BLE001
            mostra_errore(parent, "Gestione colori", e, "l'impostazione del colore")
            return False
    finally:
        sessione.close()

    sessione = factory()
    try:
        registro_colori.ricarica_da_database(sessione)
    finally:
        sessione.close()
    registro_colori.SEGNALATORE.colori_cambiati.emit()
    return True


def scegli_colore(parent: QWidget | None, factory, codice: str) -> None:
    """«Scegli colore…»: ``QColorDialog`` che parte dal colore attuale; annullare = nessun cambiamento."""
    swatch = registro_colori.registro().swatch(codice)
    inizio = QColor(swatch.colori[0]) if swatch.definito else QColor()
    scelta = QColorDialog.getColor(
        inizio if inizio.isValid() else QColor("#808080"),
        parent,
        f"Scegli il colore per {codice}",
    )
    if not scelta.isValid():
        return  # annullato: nessuna scrittura
    _salva(factory, parent, codice, scelta.name())


def conferma_suggerito(parent: QWidget | None, factory, codice: str) -> None:
    """«Conferma suggerito»: salva il suggerimento a tinta unita (altrimenti inazione)."""
    swatch = registro_colori.registro().swatch(codice)
    if swatch.origine != registro_colori.SUGGERITO or len(swatch.colori) != 1:
        return
    _salva(factory, parent, codice, swatch.colori[0])


def ripristina_automatico(parent: QWidget | None, factory, codice: str) -> None:
    """«Ripristina automatico»: rimuove ``colore_hex`` (con conferma)."""
    if not chiedi_conferma(
        parent,
        "Gestione colori",
        f"Ripristinare il colore automatico per {codice}?",
        "Ripristina",
    ):
        return
    _salva(factory, parent, codice, None)


# ------------------------------------------------------------------ dialogo
class GestioneColori(QDialog):
    """«Gestione colori»: una riga per codice — pallino · codice · nome · stato · esadecimale.

    Ricerca per codice o nome, filtro per stato, contatori; doppio clic = «Scegli colore…».
    """

    def __init__(self, factory, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._factory = factory
        self.setWindowTitle("Gestione colori")
        self.setModal(True)
        self.resize(960, 650)
        self.setMinimumSize(860, 560)
        self._costruisci()
        self._ricarica()

    # ------------------------------------------------------------------ interfaccia
    def _costruisci(self) -> None:
        layout = QVBoxLayout(self)

        titolo = QLabel("Gestione colori")
        titolo.setObjectName("TitoloCard")
        layout.addWidget(titolo)

        aiuto = QLabel(
            "Imposta il colore mostrato per ogni codice. I colori «Suggeriti» sono dedotti dal "
            "codice e non sono ancora confermati; «Non definiti» non hanno un colore riconosciuto."
        )
        aiuto.setWordWrap(True)
        layout.addWidget(aiuto)

        barra = QHBoxLayout()
        self.cerca = QLineEdit()
        self.cerca.setPlaceholderText("Cerca per codice o nome…")
        self.cerca.textChanged.connect(lambda _testo: self._ricarica())
        self.filtro = QComboBox()
        self.filtro.addItem("Tutti", None)
        self.filtro.addItem("Non definiti", registro_colori.NON_DEFINITO)
        self.filtro.addItem("Suggeriti", registro_colori.SUGGERITO)
        self.filtro.addItem("Confermati", registro_colori.CONFERMATO)
        self.filtro.currentIndexChanged.connect(lambda _indice: self._ricarica())
        self.contatori = QLabel("")
        self.contatori.setObjectName("Dim")
        barra.addWidget(self.cerca, 1)
        barra.addWidget(self.filtro)
        barra.addWidget(self.contatori)
        layout.addLayout(barra)

        self.tabella = QTableWidget(0, 5)
        self.tabella.setHorizontalHeaderLabels(["Colore", "Codice", "Nome", "Stato", "Esadecimale"])
        self.tabella.verticalHeader().setVisible(False)
        self.tabella.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabella.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tabella.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabella.itemSelectionChanged.connect(self._aggiorna_pulsanti)
        self.tabella.itemDoubleClicked.connect(lambda _cella: self._azione_scegli())
        self.tabella.setColumnWidth(0, int(rem(2.5)))
        self.tabella.setColumnWidth(3, int(rem(8)))
        layout.addWidget(self.tabella, 1)

        pulsanti = QHBoxLayout()
        self._btn_scegli = bottone("Scegli colore…", classe="primario")
        self._btn_scegli.clicked.connect(self._azione_scegli)
        self._btn_conferma = bottone("Conferma suggerito")
        self._btn_conferma.clicked.connect(self._azione_conferma)
        self._btn_ripristina = bottone("Ripristina automatico")
        self._btn_ripristina.clicked.connect(self._azione_ripristina)
        self._btn_chiudi = bottone("Chiudi")
        self._btn_chiudi.clicked.connect(self.accept)
        pulsanti.addWidget(self._btn_scegli)
        pulsanti.addWidget(self._btn_conferma)
        pulsanti.addWidget(self._btn_ripristina)
        pulsanti.addStretch(1)
        pulsanti.addWidget(self._btn_chiudi)
        layout.addLayout(pulsanti)
        self._aggiorna_pulsanti()

    # ------------------------------------------------------------------ logica
    def _codice_selezionato(self) -> str | None:
        """Codice colore della riga selezionata (colonna 1), oppure ``None``."""
        if self.tabella.currentRow() < 0:
            return None
        cella = self.tabella.item(self.tabella.currentRow(), 1)
        return cella.data(Qt.ItemDataRole.UserRole) if cella else None

    def _ricarica(self) -> None:
        """Riempie la tabella (ricerca + filtro) e i contatori; conserva selezione e scorrimento."""
        codice_previo = self._codice_selezionato()
        scorrimento = self.tabella.verticalScrollBar().value()
        testo_cerca = (self.cerca.text() or "").strip().lower()
        filtro = self.filtro.currentData()

        sessione = self._factory()
        try:
            colori = colori_servizio.elenco_colori(sessione)
        finally:
            sessione.close()

        totali = {k: 0 for k in (
            registro_colori.CONFERMATO,
            registro_colori.SUGGERITO,
            registro_colori.NON_DEFINITO,
        )}
        self.tabella.blockSignals(True)
        self.tabella.setRowCount(0)
        for c in colori:
            codice = (c.codice_normalizzato or "").upper().strip()
            nome = c.nome_visualizzato or ""
            swatch = registro_colori.registro().swatch(codice)
            totali[swatch.origine] += 1
            if filtro is not None and swatch.origine != filtro:
                continue
            if testo_cerca and testo_cerca not in codice.lower() and testo_cerca not in nome.lower():
                continue

            riga = self.tabella.rowCount()
            self.tabella.insertRow(riga)
            cella_dot = QTableWidgetItem()
            cella_dot.setIcon(QIcon(
                registro_colori.pixmap_swatch(swatch, int(rem(1.25)), tema_attivo())
            ))
            self.tabella.setItem(riga, 0, cella_dot)

            cella_codice = QTableWidgetItem(codice)
            cella_codice.setData(Qt.ItemDataRole.UserRole, codice)
            self.tabella.setItem(riga, 1, cella_codice)
            self.tabella.setItem(riga, 2, QTableWidgetItem(nome))

            pill = Pillola(_TITOLO_PILLOLA[swatch.origine], _VARIANTE_PILLOLA[swatch.origine])
            self.tabella.setCellWidget(riga, 3, pill)

            esadecimale = " / ".join(swatch.colori) if swatch.definito else "—"
            self.tabella.setItem(riga, 4, QTableWidgetItem(esadecimale))

        # ri-seleziona la riga precedente (se ancora visibile) e il scorrimento
        riga_da_scegliere = -1
        for riga in range(self.tabella.rowCount()):
            cella = self.tabella.item(riga, 1)
            if cella is not None and cella.data(Qt.ItemDataRole.UserRole) == codice_previo:
                riga_da_scegliere = riga
                break
        if riga_da_scegliere >= 0:
            self.tabella.selectRow(riga_da_scegliere)
        self.tabella.verticalScrollBar().setValue(scorrimento)
        self.tabella.blockSignals(False)

        self.contatori.setText(
            f"{totali[registro_colori.NON_DEFINITO]} non definiti · "
            f"{totali[registro_colori.SUGGERITO]} suggeriti · "
            f"{totali[registro_colori.CONFERMATO]} confermati"
        )
        self._aggiorna_pulsanti()

    def _aggiorna_pulsanti(self) -> None:
        """Abilita i pulsanti in base alla selezione: «Conferma suggerito» solo per
        suggerimenti a tinta unita; gli altri servono con qualsiasi riga selezionata."""
        codice = self._codice_selezionato()
        ha_riga = codice is not None
        self._btn_scegli.setEnabled(ha_riga)
        self._btn_ripristina.setEnabled(ha_riga)
        self._btn_conferma.setEnabled(False)
        if ha_riga:
            swatch = registro_colori.registro().swatch(codice)
            self._btn_conferma.setEnabled(
                swatch.origine == registro_colori.SUGGERITO and len(swatch.colori) == 1
            )

    # ------------------------------------------------------------------ azioni
    def _azione_scegli(self) -> None:
        codice = self._codice_selezionato()
        if codice is None:
            return
        scegli_colore(self, self._factory, codice)
        self._ricarica()

    def _azione_conferma(self) -> None:
        codice = self._codice_selezionato()
        if codice is None:
            return
        conferma_suggerito(self, self._factory, codice)
        self._ricarica()

    def _azione_ripristina(self) -> None:
        codice = self._codice_selezionato()
        if codice is None:
            return
        ripristina_automatico(self, self._factory, codice)
        self._ricarica()
