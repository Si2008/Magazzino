"""Scheda Profili: elenco, ricerca, creazione, modifica e immagine della sezione.

L'immagine della sezione è un PNG opzionale: può essere importata
(copiata nella cartella del programma) e rimossa (il file non viene
cancellato da disco, toglie solo il riferimento).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIntValidator, QPixmap, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QScrollArea,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..domain import Profilo  # modello per sessione.get
from ..services import anagrafica
from ..services import consultazione
from ..services.catalogo_immagini import CatalogoImmagini
from ..services.proposta_immagine import GestoreProposta, StatoImmagine
from .componenti import (
    MessaggioErrore,
    bottone,
    campo_con_etichetta,
)
from .icone import ic_px, pixmap_icona
from .tema import M, tema_attivo
from .validatori import ValidatoreMaiuscolo

_COLONNE = ("CODICE", "DESCRIZIONE", "LUNG. STD", "PEZZI")
_LUNG = 2
_PEZZI = 3


class SchedaProfilo(QWidget):
    """Gestione anagrafica e immagini, accessibile dall'Inventario."""

    cambiato = Signal()

    def __init__(
        self,
        factory,
        parent: QWidget | None = None,
        *,
        catalogo: CatalogoImmagini | None = None,
    ) -> None:
        super().__init__(parent)
        self._factory = factory
        self._profilo_id: int | None = None
        self._immagine_locale: str | None = None  # PNG importato, non ancora salvato
        self._rimossa_in_locales = False
        self._righe: list[tuple[int, str]] = []  # (id, codice) per la selezione
        self._catalogo = catalogo if catalogo is not None else CatalogoImmagini()
        self._proposta = GestoreProposta(self._catalogo)

        radice = QHBoxLayout(self)
        radice.setContentsMargins(M.PAG_H, M.PAG_T, M.PAG_H, M.PAG_B)
        radice.setSpacing(M.GAP)

        # ---------------- colonna sinistra: elenco ----------------
        card = QFrame(self)
        card.setObjectName("Card")
        v = QVBoxLayout(card)
        v.setContentsMargins(M.CARD_PAD, M.CARD_PAD, M.CARD_PAD, M.CARD_PAD)
        v.setSpacing(M.GAP_SM)

        barra = QFrame(card)
        barra.setObjectName("BarraStrumenti")
        hb = QHBoxLayout(barra)
        hb.setSpacing(M.GAP_SM)
        self.ricerca = QLineEdit(barra)
        self.ricerca.setPlaceholderText("Cerca profilo…")
        self.ricerca.setClearButtonEnabled(True)
        self.ricerca.textChanged.connect(self._rinfresca_tabella)
        hb.addWidget(self.ricerca, 1)
        self.nuovo_btn = bottone("Nuovo profilo", "primario", icona="plus", parent=barra)
        self.nuovo_btn.clicked.connect(self._nuovo)
        hb.addWidget(self.nuovo_btn)
        v.addWidget(barra)

        self._tabella = QTableWidget(0, len(_COLONNE), card)
        self._tabella.setHorizontalHeaderLabels(_COLONNE)
        self._tabella.setColumnHidden(1, True)
        self._tabella.verticalHeader().setVisible(False)
        self._tabella.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tabella.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tabella.setSelectionMode(QAbstractItemView.SingleSelection)
        self._tabella.setShowGrid(False)
        self._tabella.setIconSize(QSize(48, 48))
        self._tabella.verticalHeader().setDefaultSectionSize(64)
        self._tabella.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self._tabella.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._tabella.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for c in (_LUNG, _PEZZI):
            self._tabella.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self._tabella.itemSelectionChanged.connect(self._su_selezione)
        v.addWidget(self._tabella, 1)

        radice.addWidget(card, 1)

        # ---------------- colonna destra: form + immagine ----------------
        dx = QFrame(self)
        dx.setObjectName("Card")
        dx.setFixedWidth(M.PROF_DX)
        # Form + immagine sono alti più dello schermo: il contenuto scorre
        # (come `.main{overflow:auto}` del mockup) invece di essere compresso.
        vdx = QVBoxLayout(dx)
        vdx.setContentsMargins(0, 0, 0, 0)
        scroller = QScrollArea(dx)
        scroller.setObjectName("ScorrimentoCard")
        scroller.setWidgetResizable(True)
        scroller.setFrameShape(QFrame.Shape.NoFrame)
        contenuto = QWidget()
        vd = QVBoxLayout(contenuto)
        vd.setContentsMargins(M.CARD_PAD, M.CARD_PAD, M.CARD_PAD, M.CARD_PAD)
        vd.setSpacing(M.GAP)

        self._titolo_form = QLabel("Nuovo profilo", dx)
        self._titolo_form.setObjectName("TitoloCard")
        vd.addWidget(self._titolo_form)

        self.codice = QLineEdit(dx)
        self.codice.setPlaceholderText("Es. AB12")
        self.codice.setMaxLength(64)                      # String(64) del modello
        self.codice.setValidator(ValidatoreMaiuscolo(self.codice))
        self.descrizione = QLineEdit(dx)
        self.descrizione.setPlaceholderText("Es. Angolo 40x40")
        self.lunghezza = QLineEdit(dx)
        self.lunghezza.setPlaceholderText("Es. 6000")
        self.lunghezza.setValidator(QIntValidator(1, 99_999_999, dx))
        vd.addWidget(campo_con_etichetta("Codice", self.codice, dx))
        vd.addWidget(campo_con_etichetta("Descrizione", self.descrizione, dx))

        riga_pl = QHBoxLayout()
        riga_pl.setSpacing(M.GAP_SM)
        riga_pl.addWidget(campo_con_etichetta("Lunghezza std mm", self.lunghezza, dx), 1)
        vd.addLayout(riga_pl)

        self.messaggio = MessaggioErrore(dx)
        vd.addWidget(self.messaggio)

        self.salva = bottone("Salva profilo", "primario", "lg", "check", dx)
        self.salva.clicked.connect(self.salva_profilo)
        vd.addWidget(self.salva)

        # card immagine
        vd.addSpacing(M.GAP_SM)
        titolo_img = QLabel("Sezione del profilo", dx)
        titolo_img.setObjectName("Dim")
        vd.addWidget(titolo_img)

        self._anteprima = QLabel(dx)
        self._anteprima.setObjectName("BoxImmagine")
        self._anteprima.setFixedHeight(200)
        self._anteprima.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._anteprima.setWordWrap(True)
        self._mostra_immagine(None)
        vd.addWidget(self._anteprima, 1)
        self.apri_immagine_btn = bottone("Apri immagine e ingrandisci", icona="image", parent=dx)
        self.apri_immagine_btn.setEnabled(False)
        self.apri_immagine_btn.clicked.connect(self._apri_immagine)
        vd.addWidget(self.apri_immagine_btn)
        # Anteprima immediatamente visibile, prima dei campi anagrafici.
        vd.removeWidget(titolo_img)
        vd.removeWidget(self._anteprima)
        vd.removeWidget(self.apri_immagine_btn)
        vd.insertWidget(1, titolo_img)
        vd.insertWidget(2, self._anteprima)
        vd.insertWidget(3, self.apri_immagine_btn)

        self._nota_catalogo = QLabel("", dx)
        self._nota_catalogo.setObjectName("Dim")
        self._nota_catalogo.setWordWrap(True)
        self._nota_catalogo.setVisible(False)
        vd.addWidget(self._nota_catalogo)

        riga_btn = QHBoxLayout()
        riga_btn.setSpacing(M.GAP_SM)
        btn_imp = bottone("Importa immagine (PNG)", icona="upload", parent=dx)
        btn_imp.clicked.connect(self._importa_immagine)
        riga_btn.addWidget(btn_imp, 1)
        self.rimuovi_btn = bottone("Rimuovi", icona="x", parent=dx)
        self.rimuovi_btn.clicked.connect(self._rimuovi_immagine)
        riga_btn.addWidget(self.rimuovi_btn)
        vd.addLayout(riga_btn)
        scroller.setWidget(contenuto)
        vdx.addWidget(scroller)

        radice.addWidget(dx)

        # Alla fine di __init__: tutti i widget esistono.
        self.codice.textChanged.connect(self._su_codice_cambiato)
        self._rinfresca_tabella()
        self._aggiorna_pulsante_immagine()

    # ------------------------------------------------------------------ elenco
    def _rinfresca_tabella(self, _testo: str = "") -> None:
        sessione = self._factory()
        try:
            righe = consultazione.lista_profili_con_giacenza(sessione)
        finally:
            sessione.close()

        filtro = (self.ricerca.text() if self.ricerca else "").strip().lower()

        tab = self._tabella
        tab.blockSignals(True)
        tab.setRowCount(0)
        self._righe = []
        for profilo, totale in righe:
            if filtro and filtro not in (profilo.codice or "").lower() and filtro not in (profilo.descrizione or "").lower():
                continue
            r = tab.rowCount()
            tab.insertRow(r)

            def _item(testo: str, dx: int = 0) -> QTableWidgetItem:
                i = QTableWidgetItem(testo)
                if dx:
                    i.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                else:
                    i.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                i.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                i.setData(Qt.UserRole, profilo.id)
                return i

            tab.setItem(r, 0, _item(profilo.codice or ""))
            from ..services.immagini import immagine_del_profilo
            from .visualizzatore_immagine import miniatura_sezione
            immagine = immagine_del_profilo(profilo)
            if immagine:
                try:
                    stato = immagine.stat()
                    miniatura = miniatura_sezione(str(immagine), stato.st_mtime_ns, stato.st_size)
                    tab.item(r, 0).setIcon(QIcon(miniatura))
                    tab.item(r, 0).setToolTip("Sezione associata automaticamente. Seleziona il profilo per ingrandirla.")
                except OSError:
                    tab.item(r, 0).setToolTip("Immagine non leggibile: verificare il file PNG")
            else:
                tab.item(r, 0).setToolTip("Sezione non disponibile: nessun PNG corrisponde al codice profilo")
            tab.setItem(r, 1, _item(profilo.descrizione or ""))
            tab.setItem(r, _LUNG, _item(f"{profilo.lunghezza_standard_mm:,}".replace(",", ".") + " mm", 1))
            tab.setItem(r, _PEZZI, _item(str(totale), 1))
            self._righe.append((profilo.id, profilo.codice or ""))
        tab.blockSignals(False)

    def _su_selezione(self) -> None:
        selezione = self._tabella.selectionModel().selectedRows()
        if not selezione:
            self._vuota_form()
            return
        r = selezione[0].row()
        pid = self._righe[r][0]
        sessione = self._factory()
        try:
            p = sessione.get(Profilo, pid)
            # forza il caricamento delle relazioni
            codice, descrizione = p.codice, p.descrizione
            lunghezza = p.lunghezza_standard_mm
            from ..services.immagini import immagine_del_profilo
            immagine = immagine_del_profilo(p)
            immagine = str(immagine) if immagine else None
        finally:
            sessione.close()
        self._profilo_id = pid
        self._proposta.azzera()
        self._nota_catalogo.setVisible(False)
        self._immagine_locale = None
        self._rimossa_in_locales = False
        self._titolo_form.setText(f"Anagrafica — {codice}")
        self.codice.setText(codice or "")
        self.descrizione.setText(descrizione or "")
        self.lunghezza.setText(str(lunghezza)) if lunghezza else self.lunghezza.clear()
        self._mostra_immagine(immagine)
        self._aggiorna_pulsante_immagine()

    # ------------------------------------------------------------------ immagine
    def _mostra_immagine(self, percorso: str | None) -> None:
        from .visualizzatore_immagine import leggi_anteprima
        box = leggi_anteprima(percorso, M.PROF_DX - 2 * M.CARD_PAD, self._anteprima.height()) if percorso else QPixmap()
        self._percorso_immagine = percorso if not box.isNull() else None
        if hasattr(self, "apri_immagine_btn"):
            self.apri_immagine_btn.setEnabled(self._percorso_immagine is not None)
        if not box.isNull():
            self._anteprima.setPixmap(box)
            self._anteprima.setText("")
        else:
            t = tema_attivo()
            self._anteprima.setPixmap(pixmap_icona("image", t.testo_debole, ic_px(34)))
            codice = self.codice.text().strip()
            self._anteprima.setText(f"Nessuna sezione PNG nel catalogo per {codice}" if codice else "Seleziona un profilo per vedere la sezione")

    def _apri_immagine(self):
        if self._percorso_immagine:
            from .visualizzatore_immagine import apri_immagine
            try:
                apri_immagine(self._percorso_immagine, self)
            except ValueError as errore:
                self.messaggio.mostra(str(errore))

    def _aggiorna_pulsante_immagine(self) -> None:
        """Il pulsante "Rimuovi" ha senso solo se c'è un'immagine (salvata o locale)."""
        salvata = False
        if self._profilo_id is not None:
            sessione = self._factory()
            try:
                salvata = bool(sessione.get(Profilo, self._profilo_id).immagine_sezione)
            finally:
                sessione.close()
        self.rimuovi_btn.setVisible(salvata or self._immagine_locale is not None)

    # ------------------------------------------------------------------ form
    def _vuota_form(self) -> None:
        self._profilo_id = None
        self._immagine_locale = None
        self._rimossa_in_locales = False
        self._titolo_form.setText("Nuovo profilo")
        for c in (self.codice, self.descrizione, self.lunghezza):
            c.clear()
        # Azzeramento dello stato DOPO i clear(): la proposta non ripropone nulla.
        self._proposta.azzera()
        self._nota_catalogo.setVisible(False)
        self._mostra_immagine(None)
        self._aggiorna_pulsante_immagine()

    def _nuovo(self) -> None:
        self._vuota_form()
        self.codice.setFocus()

    def _importa_immagine(self) -> None:
        percorso, _ = QFileDialog.getOpenFileName(self, "Importa immagine sezione", "", "PNG (*.png)")
        if not percorso:
            return
        self._immagine_locale = percorso
        self._rimossa_in_locales = False
        self._mostra_immagine(percorso)
        self._aggiorna_pulsante_immagine()
        if self._profilo_id is None:
            # Nuova immagine a mano: la proposta non deve più sovrascriverla.
            self._proposta.su_importazione_manuale(percorso)
            self._nota_catalogo.setVisible(False)

    def _rimuovi_immagine(self) -> None:
        """Segna la rimozione dell'immagine (il file resta su disco)."""
        nuovo = self._profilo_id is None
        proposta_attiva = (
            nuovo and self._proposta.stato is StatoImmagine.PROPOSTA
        )
        if not proposta_attiva:
            from .messaggi import chiedi_conferma

            if not chiedi_conferma(
                self,
                "Rimuovi immagine",
                "Rimuovere l'immagine della sezione da questo profilo?\n"
                "Il file PNG non viene cancellato dal disco; la rimozione diventa definitiva "
                "solo quando salvi il profilo.",
                "Rimuovi",
                pericolosa=True,
            ):
                return
        self._rimossa_in_locales = True
        self._immagine_locale = None
        self._mostra_immagine(None)
        self._aggiorna_pulsante_immagine()
        if nuovo:
            # Non riproporre finché il codice normalizzato non cambia.
            self._proposta.su_rimozione(self.codice.text())
            self._nota_catalogo.setVisible(False)

    # ------------------------------------------------------------------ proposta
    def _su_codice_cambiato(self, testo: str) -> None:
        if self._profilo_id is not None:      # profilo esistente: mai proposte
            return
        self._proposta.su_codice_cambiato(testo)
        self._applica_stato_immagine()

    def _applica_stato_immagine(self) -> None:
        stato = self._proposta.stato
        if stato is StatoImmagine.MANUALE:
            self._nota_catalogo.setVisible(False)
            return
        if stato is StatoImmagine.PROPOSTA and self._proposta.percorso is not None:
            percorso = str(self._proposta.percorso)
            if QPixmap(percorso).isNull():            # PNG illeggibile per Qt: nessuna proposta
                self._proposta.azzera()
                stato = StatoImmagine.NESSUNA
            else:
                self._immagine_locale = percorso
                self._rimossa_in_locales = False
                self._mostra_immagine(percorso)
                self._nota_catalogo.setText(f"Immagine trovata nel catalogo: {Path(percorso).name}")
                self._nota_catalogo.setVisible(True)
                self._aggiorna_pulsante_immagine()
                return
        if stato is StatoImmagine.NESSUNA:
            self._immagine_locale = None
            self._rimossa_in_locales = False
            self._mostra_immagine(None)
        self._nota_catalogo.setVisible(False)
        self._aggiorna_pulsante_immagine()

    # ------------------------------------------------------------------ salvataggio
    def salva_profilo(self) -> None:
        codice = self.codice.text().strip()
        descrizione = self.descrizione.text().strip()
        try:
            lunghezza = int(self.lunghezza.text().strip()) if self.lunghezza.text().strip() else None
        except ValueError:
            self.messaggio.mostra("Lunghezza non valida.")
            return

        nuovo = self._profilo_id is None
        if nuovo and (not codice or not descrizione or lunghezza is None):
            self.messaggio.mostra(
                "Per un nuovo profilo codice, descrizione e lunghezza sono obbligatori."
            )
            return

        # Il file proposto/importato potrebbe essere sparito dal disco: nessun profilo,
        # l'utente può ripremere Salva (senza immagine) o sceglierne un'altra.
        if self._immagine_locale and not Path(self._immagine_locale).is_file():
            self._immagine_locale = None
            self._proposta.azzera()
            self._nota_catalogo.setVisible(False)
            self._mostra_immagine(None)
            self._aggiorna_pulsante_immagine()
            self.messaggio.mostra(
                "L'immagine selezionata non è più disponibile. "
                "Premi di nuovo Salva per salvare senza immagine, oppure scegline un'altra."
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
                        lunghezza_standard_mm=lunghezza,
                        file_immagine=self._immagine_locale,
                        auto_immagine=not self._rimossa_in_locales,
                    )
                else:
                    p = anagrafica.aggiorna_profilo(
                        sessione,
                        self._profilo_id,
                        descrizione=descrizione or None,
                        lunghezza_standard_mm=lunghezza,
                        file_immagine=self._immagine_locale,
                        rimuovi_immagine=self._rimossa_in_locales,
                    )
            finally:
                sessione.close()
        except Exception as errore:  # noqa: BLE001 - spiegato all'utente, dettaglio nel log
            from .messaggi import mostra_errore

            mostra_errore(self, "Profili", errore, "Il salvataggio del profilo")
            return

        self.messaggio.mostra("")
        self._rinfresca_tabella()
        self.cambiato.emit()
