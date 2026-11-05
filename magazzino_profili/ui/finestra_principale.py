"""Interfaccia desktop ad accesso libero, con tutte le schede e i privilegi abilitati."""

from __future__ import annotations

import logging
import os
import sys

from sqlalchemy.exc import SQLAlchemyError

from PySide6.QtCore import Qt, QTimer, Signal, SignalInstance
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QScrollArea,
    QTabBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..sicurezza import Ruolo, schede_consenti as _schede_ruolo
from . import animazioni, tema
from .tema import M, tema_attivo
from .icone import ic_px, icona_svg, pixmap_icona
from ..services import telefono as servizio_telefono
from .avvisi import SchedaAvvisi
from .collega_telefono import ControlloTelefono, DialogoTelefono, aggiorna_pulsante_telefono
from .componenti import Toast, bottone
from .scheda_carico import SchedaCarico
from .scheda_profilo import SchedaProfilo
from .scheda_scarico import SchedaScarico
from .tabella_pezzi import TabellaPezzi

_NOME_ICONA_SCHEDE = {
    "Inventario": "grid",
    "Carico": "up",
    "Scarico": "down",
    "Profili": "profili",
    "Avvisi": "alert",
    "Commesse": "list",
}


def schede_consenti(ruolo: Ruolo | str) -> tuple[str, ...]:
    """Schede visibili per il ruolo (nomi in maiuscolo, ordine di visualizzazione).

    Delega a :func:`magazzino_profili.sicurezza.schede_consenti` (modulo
    congelato) e capitalizza solo le etichette.
    """
    try:
        return tuple(s.capitalize() for s in _schede_ruolo(ruolo)) + ("Commesse",)
    except ValueError:
        return ()


logger = logging.getLogger(__name__)


def _icona_applicazione():
    """Icona dell'app: cercata in _MEIPASS (eseguibile) o nella radice del progetto."""
    from PySide6.QtGui import QIcon

    radici = []
    if getattr(sys, "frozen", False):
        radici.append(os.path.dirname(sys.executable))
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        radici.append(meipass)
    radici.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    for radice in radici:
        percorso = os.path.join(radice, "icona.ico")
        if os.path.exists(percorso):
            return QIcon(percorso)
    return None


def _pallino(hx: str, d: int) -> "object":
    """Piccolo cerchio colorato (stato database)."""
    from PySide6.QtGui import QColor, QPainter, QPixmap

    img = QPixmap(d, d)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(hx))
    p.drawEllipse(0, 0, d, d)
    p.end()
    return img


class FinestraPrincipale(QWidget):
    """Finestra principale con le schede di magazzino."""

    scadenze_eliminate = Signal(int)  # emesso dal thread del controllo: Qt lo consegna al thread UI

    def __init__(
        self,
        factory,
        ruolo: Ruolo | str,
        nome_utente: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._factory = factory
        self._ruolo = Ruolo.AMMINISTRATORE
        self._nome_utente = "operatore"
        self._toast: list[Toast] = []
        self._badge_avvisi: QLabel | None = None
        self._icone_nomi: list[str] = []

        self._scansione_in_corso = False
        self._scansioni_in_coda: list[str] = []
        from .server_telefono import ServerTelefono
        self._server_telefono = ServerTelefono(self)
        self._server_telefono.messaggio.connect(lambda m: self.mostra_toast(m, "info"))
        from uuid import uuid4
        self._controllo_telefono = ControlloTelefono(self._factory, self,
            destinatario=uuid4().hex, consegna=self._consegna_telefono)
        self._controllo_telefono.scansione.connect(self._su_scansione_telefono)
        self._controllo_telefono.stato_cambiato.connect(lambda _c: self._aggiorna_pulsanti_telefono())
        self._controllo_telefono.attivo_cambiato.connect(lambda _a: self._aggiorna_pulsanti_telefono())
        self._controllo_telefono.errore.connect(lambda m: self.mostra_toast(m, "danger"))

        self.setObjectName("Finestra")
        from .. import __version__
        self.setWindowTitle(f"Magazzino Profili {__version__}")
        icona = _icona_applicazione()
        if icona is not None:
            self.setWindowIcon(icona)
        self.resize(1280, 760)
        self.setMinimumSize(960, 620)
        self._applica_tema()

        self._radice = QVBoxLayout(self)
        self._radice.setContentsMargins(0, 0, 0, 0)
        self._radice.setSpacing(0)

        self._barra_titolo: QWidget | None = None
        self._barra_stato: QLabel
        self._stato_db: QLabel
        self._conta_riepilogo: QLabel
        self._barra_stato_frame: QWidget | None = None
        self._costruisci_barra_titolo()

        self._tab = QTabWidget(self)
        self._tab.setDocumentMode(True)
        self._tab.tabBar().setObjectName("TabPrincipali")
        self._tab.tabBar().setDrawBase(False)
        self._tab.setIconSize(_icona_schede())
        self._tab.currentChanged.connect(self._aggiorna_icone_schede)
        self._tab.currentChanged.connect(self._pagina_corrente_cambiata)
        self._tab.setMinimumWidth(960)
        area_programma = QScrollArea(self)
        area_programma.setWidgetResizable(True)
        area_programma.setFrameShape(QFrame.Shape.NoFrame)
        area_programma.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        area_programma.setWidget(self._tab)
        self._radice.addWidget(area_programma, 1)

        self._costruisci_barra_stato()
        self._crea_schede()

        # Fase 8: dopo ogni cambio colore, Inventario (e Scarico con selezione) si aggiorna
        self._collega_colori_cambiati()

        # Scorciatoie globali: Ctrl+Alt+Freccia sinistra/destra cambia la
        # scheda colore nella scheda Inventario.
        sx = QShortcut(QKeySequence("Ctrl+Alt+Left"), self)
        sx.setContext(Qt.ShortcutContext.WindowShortcut)
        sx.activated.connect(lambda: self._muovi_tab_colori(-1))
        dx = QShortcut(QKeySequence("Ctrl+Alt+Right"), self)
        dx.setContext(Qt.ShortcutContext.WindowShortcut)
        dx.activated.connect(lambda: self._muovi_tab_colori(1))

        self.scadenze_eliminate.connect(self._su_scadenze_eliminate)

        self._messaggio("Apertura: accesso come " + self._nome_utente)
        self._aggiorna_stato_riepilogo()

    # ------------------------------------------------------------------
    # Fase 8: colori
    # ------------------------------------------------------------------
    def _apri_gestione_colori(self) -> None:
        """Apre il dialogo «Gestione colori» (una riga per codice colore)."""
        if self._ruolo != Ruolo.AMMINISTRATORE:
            return
        from .gestione_colori import GestioneColori

        dialogo = GestioneColori(self._factory, self)
        dialogo.exec()
        dialogo.deleteLater()

    def _collega_colori_cambiati(self) -> None:
        """Dopo ogni cambio colore: Inventario aggiorna l'interfaccia; Scarico solo se ha
        un barcode visibile. Collegamento unico (il segnalatore è un singleton e le schede
        vengono ricreate al cambio tema: gli attributi restano validi). Al distruggimento
        della finestra il handler si scollega: un vecchio handler non deve mai toccare
        widget già eliminati (es. teardown dei test)."""
        if getattr(self, "_collegato_colori", False):
            return

        def _su_cambiato() -> None:
            try:
                if self.scheda_inventario is not None:
                    self.scheda_inventario.aggiorna()
                scarico = self._pagina_pronta("scheda_scarico")
                if scarico is not None and (scarico.barcode.text() or "").strip():
                    scarico._aggiorna_anteprima("")
            except RuntimeError:
                # oggetti C++ già eliminati (teardown): ignora
                return

        from . import registro_colori

        registro_colori.SEGNALATORE.colori_cambiati.connect(_su_cambiato)
        self._handler_colori = _su_cambiato
        self._collegato_colori = True

        def _scollega() -> None:
            try:
                registro_colori.SEGNALATORE.colori_cambiati.disconnect(self._handler_colori)
            except (RuntimeError, TypeError):
                # già scollegato, o segnalatore eliminato (es. fine sessione)
                return

        self.destroyed.connect(_scollega)

    # ------------------------------------------------------------------
    # barra del titolo
    # ------------------------------------------------------------------
    def _costruisci_barra_titolo(self) -> None:
        t = tema_attivo()
        barra = QFrame(self)
        barra.setObjectName("Titlebar")
        h = QHBoxLayout(barra)
        h.setContentsMargins(M.TITOLO_PH, M.TITOLO_PV, M.TITOLO_PH, M.TITOLO_PV)
        h.setSpacing(M.GAP_SM)

        logo = QLabel(barra)
        logo.setObjectName("Logo")
        logo.setFixedSize(M.LOGO, M.LOGO)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setPixmap(pixmap_icona("box", t.accento_inchiostro, ic_px(18)))
        h.addWidget(logo)

        brand = QVBoxLayout()
        brand.setContentsMargins(0, 0, 0, 0)
        brand.setSpacing(0)
        nome = QLabel("Magazzino Profili", barra)
        nome.setObjectName("BrandNome")
        sotto = QLabel("Giacenza profili · Tre-D Lab", barra)
        sotto.setObjectName("BrandSotto")
        brand.addWidget(nome)
        brand.addWidget(sotto)
        h.addLayout(brand)
        h.addStretch(1)

        self.puls_report = bottone("Strumenti e backup", icona="file", parent=barra)
        self.puls_report.setProperty("menu", "true")
        menu = QMenu(self.puls_report)
        from .postazione import configura
        menu.addAction('Configura postazione e cartella di rete…',lambda:configura(self))
        self._azione_excel = QAction("Esporta inventario in Excel", menu)
        self._azione_excel.setIcon(icona_svg("download", t.testo, ic_px(14)))
        self._azione_excel.triggered.connect(self._esporta_excel)
        self._azione_pdf = QAction("Esporta inventario in PDF", menu)
        self._azione_pdf.setIcon(icona_svg("file", t.testo, ic_px(14)))
        self._azione_pdf.triggered.connect(self._esporta_pdf)
        menu.addAction(self._azione_excel)
        menu.addAction(self._azione_pdf)
        for testo, tipo in (("Esporta CSV V2…", "csv"), ("Esporta ODS V2…", "ods"),
                            ("Backup Excel multi-foglio…", "backup"),
                            ("Archivio dati e immagini ZIP…", "zip")):
            azione = menu.addAction(testo)
            azione.triggered.connect(lambda _=False, tipo=tipo: self._esporta_formato(tipo))
        if self._ruolo == Ruolo.AMMINISTRATORE:
            menu.addSeparator()
            menu.addAction("Importa CSV o ODS…", self._importa_inventario)
            menu.addAction("Ripristina backup Excel o archivio ZIP…", self._ripristina_excel)
            menu.addAction("Converti giacenze storiche in pezzi singoli…", self._converti_barcode_storici)
        menu.addSeparator()
        menu.addAction("Stato backup automatico", lambda: self.mostra_toast(
            getattr(getattr(self, "_pianificatore_backup", None), "ultimo_esito", "Servizio backup non disponibile"), "info"))

        menu.addSeparator()
        self._azione_animazioni = QAction("Animazioni di transizione", menu)
        self._azione_animazioni.setCheckable(True)
        self._azione_animazioni.setChecked(animazioni.attive())
        self._azione_animazioni.toggled.connect(lambda v: animazioni.imposta_attive(v))
        menu.addAction(self._azione_animazioni)

        # Fase 8: «Gestione colori…» (solo per i ruoli che vedono la scheda «Profili»)
        if "Profili" in schede_consenti(self._ruolo):
            menu.addSeparator()
            self._azione_colori = QAction("Gestione colori…", menu)
            self._azione_colori.triggered.connect(self._apri_gestione_colori)
            menu.addAction(self._azione_colori)

        menu.addSeparator()
        menu.addAction("Avvia servizio telefono", self._avvia_server_telefono)
        from .background import configura_tray
        configura_tray(self, menu)
        self.puls_report.setMenu(menu)
        h.addWidget(self.puls_report)

        icona_tema = "moon" if t is tema.CHIARO else "sun"
        self.puls_tema = bottone("", dim="icona", icona=icona_tema, parent=barra)
        self.puls_tema.setFixedSize(M.BTN_ICONA, M.BTN_ICONA)
        self.puls_tema.setToolTip("Cambia tema scuro/chiaro")
        self.puls_tema.setAccessibleName("Cambia tema scuro o chiaro")
        self.puls_tema.clicked.connect(self._cambia_tema)
        h.addWidget(self.puls_tema)

        self._barra_titolo = barra
        self._radice.insertWidget(0, barra)

    # ------------------------------------------------------------------
    # barra di stato
    # ------------------------------------------------------------------
    def _costruisci_barra_stato(self) -> None:
        t = tema_attivo()
        barra = QFrame(self)
        barra.setObjectName("Statusbar")
        h = QHBoxLayout(barra)
        h.setContentsMargins(M.STATO_PH, M.STATO_PV, M.STATO_PH, M.STATO_PV)
        h.setSpacing(M.GAP_SM)

        ico = QLabel(barra)
        ico.setPixmap(pixmap_icona("check", t.ok, ic_px(14)))
        h.addWidget(ico)

        self._barra_stato = QLabel(barra)
        h.addWidget(self._barra_stato, 1)

        utente = QLabel("Accesso libero · tutti i privilegi", barra)
        utente.setObjectName("Debole")
        h.addWidget(utente)

        self._pallino_db = QLabel(barra)
        self._pallino_db.setPixmap(_pallino(t.testo_debole, M.PILL_PUNTO))
        h.addWidget(self._pallino_db)
        self._stato_db = QLabel("…", barra)
        h.addWidget(self._stato_db)

        self._conta_riepilogo = QLabel(barra)
        h.addWidget(self._conta_riepilogo)

        self._barra_stato_frame = barra
        self._radice.addWidget(barra)

    # ------------------------------------------------------------------
    # schede
    # ------------------------------------------------------------------
    def _crea_schede(self):
        # Su PC lenti si costruisce solo la pagina effettivamente aperta.
        self._pagine = {}
        self._segnaposto = {}
        self._nomi_pagine = ["scheda_inventario", "scheda_carico", "scheda_scarico", "scheda_profilo", "scheda_avvisi", "scheda_commesse"]
        self._fabbriche_pagine = {
            "scheda_inventario": ("Inventario", lambda: TabellaPezzi(self._factory)),
            "scheda_carico": ("Carico", lambda: SchedaCarico(self._factory, self._nome_utente)),
            "scheda_scarico": ("Scarico", lambda: SchedaScarico(self._factory, self._nome_utente)),
            "scheda_profilo": ("Profili", lambda: SchedaProfilo(self._factory)),
            "scheda_avvisi": ("Avvisi", lambda: SchedaAvvisi(self._factory)),
            "scheda_commesse": ("Commesse", self._crea_commesse),
        }
        self._tab.blockSignals(True)
        self._tab.clear()
        self._icone_nomi.clear()
        for nome in self._nomi_pagine:
            titolo, _ = self._fabbriche_pagine[nome]
            segnaposto = QWidget(self._tab)
            self._segnaposto[nome] = segnaposto
            self._tab.addTab(segnaposto, titolo)
            self._icone_nomi.append(_NOME_ICONA_SCHEDE[titolo])
        self._tab.blockSignals(False)
        self._materializza_pagina("scheda_inventario")
        self._aggiorna_icone_schede()
        self._aggiorna_badge_avvisi()

    def _crea_commesse(self):
        from .scheda_commesse import SchedaCommesse
        return SchedaCommesse(self._factory, self._avvia_lavoro)

    def _pagina_pronta(self, nome):
        return getattr(self, "_pagine", {}).get(nome)

    def _materializza_pagina(self, nome):
        pronta = self._pagina_pronta(nome)
        if pronta is not None:
            return pronta
        titolo, fabbrica = self._fabbriche_pagine[nome]
        pagina = fabbrica()
        self._pagine[nome] = pagina
        segnaposto = self._segnaposto.pop(nome)
        indice, corrente = self._tab.indexOf(segnaposto), self._tab.currentIndex()
        bloccati = self._tab.blockSignals(True)
        self._tab.removeTab(indice)
        self._tab.insertTab(indice, pagina, titolo)
        self._tab.setCurrentIndex(corrente)
        self._tab.blockSignals(bloccati)
        segnaposto.deleteLater()
        if nome == "scheda_avvisi":
            self._badge_avvisi = None
            self._aggiorna_badge_avvisi()
        if hasattr(pagina, "telefono_richiesto"):
            pagina.telefono_richiesto.connect(self._apri_dialogo_telefono)
            aggiorna_pulsante_telefono(pagina.btn_telefono, self._controllo_telefono.collegato)
        if hasattr(pagina, "vai_a_scheda"):
            pagina.vai_a_scheda.connect(self._vai_a_scheda)
        if nome == "scheda_avvisi":
            pagina.vai_a_colore.connect(self._vai_a_colore_davvisi)
            pagina.soglia_cambiata.connect(self._su_soglia_cambiata)
        if hasattr(pagina, "cambiato"):
            pagina.cambiato.connect(lambda: self._dati_pagina_cambiati(nome))
        messaggio = getattr(pagina, "messaggio", None)
        if isinstance(messaggio, SignalInstance):
            messaggio.connect(self.mostra_toast)
        self._aggiorna_icone_schede()
        return pagina

    def _pagina_corrente_cambiata(self, indice):
        if indice < 0 or not hasattr(self, "_nomi_pagine"):
            return
        nome = self._nomi_pagine[indice]
        gia_pronta = self._pagina_pronta(nome) is not None
        pagina = self._materializza_pagina(nome)
        if gia_pronta and nome in ("scheda_inventario", "scheda_avvisi"):
            pagina.aggiorna()
        animazioni.dissolvenza(pagina, animazioni.DURATA_BREVE)

    def _dati_pagina_cambiati(self, origine=None):
        if getattr(self, "_aggiornamento_pagine", False):
            return
        self._aggiornamento_pagine = True
        try:
            commesse = self._pagina_pronta("scheda_commesse")
            if commesse is not None:
                commesse.segnala_giacenza_cambiata()
            for nome in ("scheda_inventario", "scheda_avvisi"):
                pagina = self._pagina_pronta(nome)
                if pagina is not None and nome != origine:
                    pagina.aggiorna()
            self._aggiorna_stato_riepilogo()
            self._aggiorna_badge_avvisi()
        finally:
            self._aggiornamento_pagine = False

    @property
    def scheda_inventario(self):
        return self._materializza_pagina("scheda_inventario")

    @property
    def scheda_carico(self):
        return self._materializza_pagina("scheda_carico")

    @property
    def scheda_scarico(self):
        return self._materializza_pagina("scheda_scarico")

    @property
    def scheda_profilo(self):
        return self._materializza_pagina("scheda_profilo")

    @property
    def scheda_avvisi(self):
        return self._materializza_pagina("scheda_avvisi")

    # ------------------------------------------------------------------
    # telefono come lettore barcode
    # ------------------------------------------------------------------
    def _aggiorna_pulsanti_telefono(self) -> None:
        for nome in ("scheda_carico", "scheda_scarico"):
            scheda = self._pagina_pronta(nome)
            if scheda is not None:
                aggiorna_pulsante_telefono(scheda.btn_telefono, self._controllo_telefono.collegato)

    def _apri_dialogo_telefono(self) -> None:
        self._avvia_server_telefono()
        from ..services.collegamento_remoto import PAGINA_TELEFONO
        if (servizio_telefono.leggi_url_pubblico() or PAGINA_TELEFONO).rstrip('/') == PAGINA_TELEFONO:
            if not self._server_telefono.origine_locale:
                self.mostra_toast("Servizio telefono non disponibile", "danger");return
            self._server_telefono.ponte.avvia(self._server_telefono.origine_locale,self._controllo_telefono.destinatario)
            self._mostra_qr_remoto()
            return
        url = servizio_telefono.leggi_url_pubblico()
        if url:
            try:
                url = servizio_telefono.valida_url_pubblico(url)
                from urllib.parse import urlencode
                url += "?" + urlencode({"pc": self._controllo_telefono.destinatario})
            except ValueError as errore:
                self.mostra_toast(str(errore), "danger")
                url = None
        if url and not self._controllo_telefono.attivo:
            self._controllo_telefono.avvia()  # l'ascolto parte solo se c'è un indirizzo da dare al telefono
        dialogo = DialogoTelefono(self._controllo_telefono, url, self)
        dialogo.exec()
        dialogo.deleteLater()

    def _mostra_qr_remoto(self):
        from ..services.collegamento_remoto import PAGINA_TELEFONO
        from urllib.parse import urlencode
        url=PAGINA_TELEFONO+'/?'+urlencode(dict(pc=self._controllo_telefono.destinatario))
        self._controllo_telefono.avvia()
        dialogo=DialogoTelefono(self._controllo_telefono,url,self)
        dialogo.exec();dialogo.deleteLater()

    def _consegna_telefono(self, barcode):
        corrente = self._tab.currentWidget()
        if corrente is self._pagina_pronta("scheda_scarico"):
            if corrente.ricevi_scansione(barcode):
                return "completata", "Scarico registrato dal PC"
            return "rifiutata", "Scarico non eseguito: controllare causale, quantità e conferma sul PC"
        if corrente is self._pagina_pronta("scheda_carico"):
            if corrente.ricevi_scansione(barcode):
                return "compilata", "Dati inseriti in Carico: completa il salvataggio sul PC"
            return "rifiutata", "Barcode non riconosciuto dal PC: nessun carico eseguito"
        return "rifiutata", "Apri Carico o Scarico sul PC e ripeti la scansione"

    def _su_scansione_telefono(self, barcode: str) -> None:
        """Consegna il barcode alla scheda attiva (Scarico o Carico). Una alla volta."""
        if self._scansione_in_corso:  # un dialogo di conferma è aperto: la scansione aspetta il suo turno
            self._scansioni_in_coda.append(barcode)
            return
        self._scansione_in_corso = True
        try:
            corrente = self._tab.currentWidget()
            if corrente is not None and corrente is self._pagina_pronta("scheda_scarico"):
                self.scheda_scarico.ricevi_scansione(barcode)
            elif corrente is not None and corrente is self._pagina_pronta("scheda_carico"):
                self.scheda_carico.ricevi_scansione(barcode)
            else:
                self.mostra_toast("Apri Carico o Scarico per usare il telefono come lettore", "info")
        finally:
            self._scansione_in_corso = False
        if self._scansioni_in_coda:
            prossimo = self._scansioni_in_coda.pop(0)
            QTimer.singleShot(0, lambda: self._su_scansione_telefono(prossimo))

    def closeEvent(self, evento) -> None:  # noqa: N802
        """Non interrompere una scrittura in corso chiudendo la finestra."""
        if (getattr(self, "_mantieni_background", False) and getattr(self, "_tray", None)
                and not getattr(self, "_esci_davvero", False)):
            self.hide()
            evento.ignore()
            self._tray.showMessage("Magazzino Profili", "Programma attivo nell'area di notifica. Usa Esci per terminarlo.")
            return
        if any(l.isRunning() for l in getattr(self, "_lavori", [])):
            evento.ignore()
            self.mostra_toast("Attendi il completamento dell'operazione in corso", "info")
            return
        if self._controllo_telefono.ferma() is False:
            evento.ignore()
            return
        if self._server_telefono.ferma() is False:
            evento.ignore()
            QTimer.singleShot(500,self.close)
            return
        pianificatore = getattr(self, "_pianificatore_backup", None)
        if pianificatore is not None and not pianificatore.ferma(timeout=0):
            evento.ignore()
            self.mostra_toast("Attendo la fine del backup prima di chiudere", "info")
            QTimer.singleShot(1000, self.close)
            return
        if getattr(self, "_tray", None):
            self._tray.hide()
        super().closeEvent(evento)

    def _avvia_server_telefono(self):
        try:
            self._server_telefono.avvia()
        except (ValueError, OSError) as errore:
            self.mostra_toast(f"Servizio telefono non avviato: {errore}", "danger")

    def _prepara_riavvio(self):
        if any(l.isRunning() for l in getattr(self, "_lavori", [])):
            return False
        backup = getattr(self, "_pianificatore_backup", None)
        if not getattr(self, "_servizi_da_riprendere", None):
            self._servizi_da_riprendere = dict(backup=backup is not None,
                scadenze=getattr(self, "_pianificatore_scadenze", None) is not None,
                telefono=self._controllo_telefono.attivo,
                server=self._server_telefono.processo is not None and self._server_telefono.processo.poll() is None)
        if backup and not backup.ferma(timeout=0):
            return False
        scadenze = getattr(self, "_pianificatore_scadenze", None)
        if scadenze:
            try:
                scadenze.ferma(timeout=0)
            except TimeoutError:
                return False
        return self._controllo_telefono.ferma() and self._server_telefono.ferma()

    def _riprendi_servizi(self):
        stato = getattr(self, "_servizi_da_riprendere", None)
        if not stato:
            return
        backup = getattr(self, "_pianificatore_backup", None)
        scadenze = getattr(self, "_pianificatore_scadenze", None)
        if ((backup and backup.in_corso) or
                (scadenze and scadenze._thread and scadenze._thread.is_alive() and scadenze._fermo.is_set())):
            QTimer.singleShot(500, self._riprendi_servizi)
            return
        self._servizi_da_riprendere = None
        if stato["backup"]:
            backup.avvia(asincrono=True)
        if stato["scadenze"]:
            scadenze.avvia()
        if stato["telefono"]:
            self._controllo_telefono.avvia()
        if stato["server"]:
            self._avvia_server_telefono()

    def _aggiorna_icone_schede(self) -> None:
        """Scheda attiva con icona in ``t.accento``, le altre in ``t.testo_dim``."""
        t = tema_attivo()
        for i, nome in enumerate(self._icone_nomi):
            colore = t.accento if i == self._tab.currentIndex() else t.testo_dim
            self._tab.setTabIcon(i, icona_svg(nome, colore, ic_px(16)))

    def _vai_a_scheda(self, nome: str, barcode: str) -> None:
        """Da Inventario: apre Carico/Scarico con il barcode compilato."""
        scheda = self.scheda_carico if nome == "Carico" else (self.scheda_scarico if nome == "Scarico" else None)
        if scheda is None:
            return
        self._tab.setCurrentWidget(scheda)
        campo = getattr(scheda, "barcode", None)
        if campo is not None and barcode:
            campo.setText(barcode)
        self._messaggio(f"{nome}: barcode compilato")

    def _vai_a_colore_davvisi(self, colore_id: int) -> None:
        """Da Avvisi: vai alla scheda Inventario sul colore indicato."""
        if self.scheda_inventario is None:
            return
        self._tab.setCurrentWidget(self.scheda_inventario)
        self.scheda_inventario.vai_a_colore(colore_id)
        self._messaggio(f"Inventario: scheda colore selezionata da Avvisi (colore {colore_id})")

    def _su_scadenze_eliminate(self, n: int) -> None:
        """Fase 8: il controllo di sottofondo ha eliminato barcode scaduti."""
        if self.scheda_inventario is not None:
            self.scheda_inventario.aggiorna()
        self._messaggio(f"{n} barcode scaduti eliminati automaticamente")

    def _su_soglia_cambiata(self, _valore: int) -> None:
        """La soglia globale è cambiata in Avvisi: rinfresca badge e KPI/Inventario."""
        self._aggiorna_badge_avvisi()
        self._aggiorna_stato_riepilogo()
        if self.scheda_inventario is not None:
            self.scheda_inventario.aggiorna()

    def _muovi_tab_colori(self, delta: int) -> None:
        if self.scheda_inventario is None:
            return
        if self._tab.currentWidget() is not self.scheda_inventario:
            return
        if delta < 0:
            self.scheda_inventario.tab_colori_sopra()
        else:
            self.scheda_inventario.tab_colori_giù()

    # ------------------------------------------------------------------
    # tema / stato
    # ------------------------------------------------------------------
    def _applica_tema(self) -> None:
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is not None:
            app.setPalette(tema.palette_tema(tema_attivo()))
            app.setStyleSheet(tema.qss_globale(tema_attivo()))

    def _cambia_tema(self) -> None:
        animazioni.transizione_tema(self, self._esegui_cambio_tema)

    def _esegui_cambio_tema(self) -> None:
        tema.alterna_tema()
        self._applica_tema()
        # ricostruisce barra del titolo, schede e barra di stato (i colori
        # delle icone e dei pallini sono applicati alla creazione)
        if self._barra_titolo is not None:
            self._radice.removeWidget(self._barra_titolo)
            self._barra_titolo.deleteLater()
            self._barra_titolo = None
        if self._barra_stato_frame is not None:
            self._radice.removeWidget(self._barra_stato_frame)
            self._barra_stato_frame.deleteLater()
            self._barra_stato_frame = None
        self._costruisci_barra_titolo()
        self._costruisci_barra_stato()
        # I form e la selezione restano negli stessi widget, inclusi dati non salvati.
        from PySide6.QtWidgets import QPushButton
        from .componenti import CardKPI
        t = tema.tema_attivo()
        for pulsante in self.findChildren(QPushButton):
            nome_icona = pulsante.property("nome_icona")
            if nome_icona:
                colore = {"ok": t.ok_inchiostro, "pericolo": t.pericolo_inchiostro,
                          "primario": t.accento_inchiostro}.get(pulsante.property("classe"), t.testo)
                pulsante.setIcon(icona_svg(nome_icona, colore, pulsante.iconSize().width()))
        for card in self.findChildren(CardKPI):
            card.set_tono(getattr(card, "_tono", "accento"))
        self._aggiorna_icone_schede()
        if self.scheda_inventario is not None:
            self.scheda_inventario.aggiorna()
        for nome_scheda in ("scheda_carico", "scheda_scarico"):
            scheda = self._pagina_pronta(nome_scheda)
            if scheda is not None:
                scheda._mostra_movimenti()
        if self._pagina_pronta("scheda_avvisi") is not None:
            self.scheda_avvisi.aggiorna()
        self._aggiorna_pulsanti_telefono()
        self._aggiorna_badge_avvisi()
        self.update()
        nome = "chiaro" if tema.tema_attivo() is tema.CHIARO else "scuro"
        self._messaggio(f"Tema cambiato: {nome}")
        self._aggiorna_stato_riepilogo()

    def _messaggio(self, testo: str) -> None:
        self._barra_stato.setText(testo)

    def _aggiorna_stato_riepilogo(self) -> None:
        from ..services import consultazione, impostazioni

        t = tema_attivo()
        r = None
        try:
            sessione = self._factory()
            try:
                soglia = impostazioni.leggi_soglia(sessione)
                r = consultazione.riepilogo_inventario(sessione, soglia)
            finally:
                sessione.close()
            ok = True
        except SQLAlchemyError:
            logger.exception("Aggiornamento stato database non riuscito")
            ok = False
        self._stato_db.setText("PostgreSQL" if ok else "Database non raggiungibile")
        self._pallino_db.setPixmap(_pallino(t.ok if ok else t.pericolo, M.PILL_PUNTO))
        if r is not None:
            self._conta_riepilogo.setText(f"{r['referenze']} referenze · {r['pezzi_totali']} pezzi")

    def _aggiorna_badge_avvisi(self) -> None:
        from ..services import consultazione, impostazioni

        try:
            sessione = self._factory()
            try:
                soglia = impostazioni.leggi_soglia(sessione)
                n = consultazione.pezzi_da_riordinare(sessione, soglia, conteggio=True)
            finally:
                sessione.close()
        except SQLAlchemyError:
            logger.exception("Aggiornamento badge avvisi non riuscito")
            n = 0
        for i in range(self._tab.count()):
            if self._tab.tabText(i) != "Avvisi":
                continue
            if self._badge_avvisi is None:
                self._badge_avvisi = QLabel("0", self)
                self._badge_avvisi.setObjectName("Conta")
                self._badge_avvisi.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._badge_avvisi.setText(str(n))
            self._tab.tabBar().setTabButton(i, QTabBar.ButtonPosition.RightSide, self._badge_avvisi)
            self._badge_avvisi.setVisible(n > 0)
            break

    # ------------------------------------------------------------------
    # toast
    # ------------------------------------------------------------------
    def mostra_toast(self, testo: str, tono: str = "ok") -> None:
        """Notifica in basso a destra (massimo 3 visibili) + messaggio di stato."""
        self._messaggio(testo)
        attive = [x for x in self._toast if x.isVisible()]
        while len(attive) >= Toast.MASSIMO_VISIBILI:
            attive.pop(0).close()
        toast = Toast(testo, tono, parent=self)
        self._toast.append(toast)
        toast.destroyed.connect(lambda _o, t=toast: self._toast.remove(t) if t in self._toast else None)
        toast.mostra(self)
        toast.entra()

    def resizeEvent(self, evento) -> None:  # noqa: N802
        super().resizeEvent(evento)
        for toast in self._toast:
            if toast.isVisible():
                toast.mostra(self)

    # ------------------------------------------------------------------
    # report
    # ------------------------------------------------------------------
    def _avvia_lavoro(self, titolo, azione, completato=None):
        from .lavori import Lavoro
        from PySide6.QtWidgets import QProgressDialog
        if any(l.isRunning() for l in getattr(self, "_lavori", [])):
            self.mostra_toast("Attendi il completamento dell'operazione in corso", "info")
            return
        lavoro = Lavoro(azione, self)
        self._lavori = [lavoro]
        progresso = QProgressDialog(titolo, "", 0, 0, self)
        progresso.setCancelButton(None)
        progresso.setWindowModality(Qt.WindowModality.WindowModal)
        progresso.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        progresso.show()
        def riuscito(risultato):
            self.mostra_toast(titolo + ": operazione completata", "ok")
            if completato:
                completato(risultato)
        lavoro.riuscito.connect(riuscito)
        lavoro.fallito.connect(lambda errore: QMessageBox.critical(self, titolo, errore))
        lavoro.finished.connect(progresso.close)
        lavoro.finished.connect(progresso.deleteLater)
        lavoro.finished.connect(lambda: self._lavori.remove(lavoro))
        lavoro.finished.connect(lavoro.deleteLater)
        lavoro.start()

    def _esporta_pdf(self):
        self._esporta_formato("pdf")

    def _esporta_excel(self):
        self._esporta_formato("xlsx")

    def _esporta_formato(self, tipo):
        from ..sicurezza.utenti import puo
        if not puo(self._ruolo, "report"):
            return
        from ..reports import esporta_inventario_excel, esporta_inventario_pdf
        from ..reports.formato_v2 import esporta_inventario_csv_v2
        from ..reports.ods_v2 import esporta_inventario_ods_v2
        from ..reports.backup_excel import esporta_backup_logico_excel
        from ..reports.archivio import esporta_archivio_dati
        azioni = dict(xlsx=esporta_inventario_excel, pdf=esporta_inventario_pdf,
                      csv=esporta_inventario_csv_v2, ods=esporta_inventario_ods_v2,
                      backup=esporta_backup_logico_excel, zip=esporta_archivio_dati)
        estensione = "xlsx" if tipo == "backup" else tipo
        percorso, _ = QFileDialog.getSaveFileName(self, "Esporta " + tipo.upper(),
                "backup.xlsx" if tipo == "backup" else "inventario." + estensione,
                f"{estensione.upper()} (*.{estensione})")
        if not percorso:
            return
        def esegui():
            with self._factory() as sessione:
                return azioni[tipo](sessione, percorso)
        self._avvia_lavoro("Esportazione " + tipo.upper(), esegui)

    def _backup_preventivo(self):
        from ..backup import leggi_config_backup
        from ..reports.archivio import esporta_archivio_dati
        from pathlib import Path
        from datetime import datetime
        from uuid import uuid4
        destinazione = Path(leggi_config_backup().cartella) / (
                "prima_operazione_" + datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid4().hex[:8] + ".zip")
        with self._factory() as sessione:
            return esporta_archivio_dati(sessione, destinazione)

    def _dopo_importazione(self, risultato):
        self._dati_pagina_cambiati()
        profili = self._pagina_pronta("scheda_profilo")
        if profili is not None:
            profili._rinfresca_tabella()

    def _importa_inventario(self):
        if self._ruolo != Ruolo.AMMINISTRATORE:
            return
        percorso, _ = QFileDialog.getOpenFileName(self, "Importa inventario", "", "CSV o ODS (*.csv *.ods)")
        if not percorso:
            return
        from PySide6.QtWidgets import QInputDialog
        vassoio, ok = QInputDialog.getText(self, "Vassoio per i dati storici",
            "Vassoio per le righe prive di vassoio (ignorato negli snapshot V2):")
        if not ok:
            return
        from .messaggi import chiedi_conferma
        if not chiedi_conferma(self, "Importa inventario",
                "Verrà creato un archivio preventivo. Il formato V2 riconcilia le giacenze; "
                "i file storici aggiungono un nuovo carico e non vanno importati due volte. Continuare?", "Importa"):
            return
        def esegui():
            from pathlib import Path
            from ..reports.formato_v2 import valida_csv_v2, importa_inventario_v2
            from ..reports.ods_v2 import valida_ods_v2
            from ..reports.export_csv import importa_peczi_csv
            from ..reports.importa_ods import importa_ods_file
            self._backup_preventivo()
            with self._factory() as sessione:
                if Path(percorso).suffix.lower() == ".csv":
                    import csv
                    with open(percorso, encoding="utf-8-sig", newline="") as file:
                        header = next(csv.reader(file, delimiter=";"), [])
                    if header and header[0] == "Versione formato":
                        return importa_inventario_v2(sessione, valida_csv_v2(percorso), self._nome_utente)
                    return importa_peczi_csv(sessione, percorso, self._nome_utente,
                                             unitari=True, vassoio_predefinito=vassoio or None)
                risultato = valida_ods_v2(percorso)
                if risultato.valido:
                    return importa_inventario_v2(sessione, risultato, self._nome_utente)
                return importa_ods_file(sessione, percorso, self._nome_utente,
                                       unitari=True, vassoio_predefinito=vassoio or None)
        self._avvia_lavoro("Importazione inventario", esegui, self._dopo_importazione)

    def _ripristina_excel(self):
        if self._ruolo != Ruolo.AMMINISTRATORE:
            return
        percorso, _ = QFileDialog.getOpenFileName(self, "Ripristina backup", "", "Backup (*.xlsx *.zip)")
        if not percorso:
            return
        from PySide6.QtWidgets import QInputDialog
        modalita, ok = QInputDialog.getItem(self, "Destinazione", "Modalità di ripristino",
                                           ["db_vuoto", "merge"], 0, False)
        if not ok:
            return
        from .messaggi import chiedi_conferma
        if not chiedi_conferma(self, "Ripristina backup", "Creare l'archivio preventivo e ripristinare i dati?", "Ripristina"):
            return
        def esegui():
            from ..reports.backup_excel import valida_backup_logico_excel, ripristina_backup_logico_excel
            archivio = percorso.lower().endswith(".zip")
            backup = None if archivio else valida_backup_logico_excel(percorso)
            self._backup_preventivo()
            with self._factory() as sessione:
                if archivio:
                    from ..reports.archivio import ripristina_archivio_dati
                    ripristina_archivio_dati(sessione, percorso, modalita=modalita)
                else:
                    ripristina_backup_logico_excel(sessione, backup, modalita=modalita)
        self._avvia_lavoro("Ripristino backup", esegui, self._dopo_importazione)

    def _converti_barcode_storici(self):
        if self._ruolo != Ruolo.AMMINISTRATORE:
            return
        from ..services.pezzi_unitari import piano_conversione, converti_aggregati
        from .messaggi import chiedi_conferma
        with self._factory() as sessione:
            piano = piano_conversione(sessione)
        if not piano:
            self.mostra_toast("Nessuna giacenza storica positiva da convertire", "info")
            return
        n = sum(r[2] for r in piano)
        if not chiedi_conferma(self, "Conversione barcode storici",
            f"Creare un backup preventivo e assegnare {n} barcode distinti a {n} pezzi fisici? "
            "Il totale di magazzino resta invariato. Le vecchie etichette delle quantità convertite "
            "devono essere sostituite con le nuove etichette singole. Lo storico viene conservato. "
            "Si procede in lotti da massimo 1000 pezzi.", "Converti e genera elenco"):
            return
        percorso, _ = QFileDialog.getSaveFileName(self, "Elenco nuovi barcode", "barcode_convertiti.csv", "CSV (*.csv)")
        if not percorso:
            return
        def esegui():
            import csv
            from ..file_sicuri import destinazione_atomica
            self._backup_preventivo()
            with self._factory() as sessione:
                barcode = converti_aggregati(sessione, piano, self._nome_utente)
            # Il database resta la fonte dei barcode anche se il salvataggio elenco fallisce.
            with destinazione_atomica(percorso) as temporaneo, open(temporaneo, "w", encoding="utf-8-sig", newline="") as file:
                writer = csv.writer(file, delimiter=";")
                writer.writerow(["Barcode univoco del pezzo"])
                writer.writerows((b,) for b in barcode)
            return barcode
        self._avvia_lavoro("Conversione barcode", esegui, self._dopo_importazione)


def _icona_schede() -> "object":
    """Dimensione icona delle schede principali (24 px logici)."""
    from PySide6.QtCore import QSize

    return QSize(ic_px(16), ic_px(16))
