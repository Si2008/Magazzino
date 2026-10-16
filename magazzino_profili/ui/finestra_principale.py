"""Finestra principale: barra del titolo, schede e barra di stato.

Layout (come nel mockup):

- barra del titolo: logo + "Magazzino Profili / Giacenza profili · Tre-D Lab",
  pulsante "Report" (menu Excel/PDF) e pulsante tema (sole/luna);
- schede: Inventario, Carico, Scarico, Profili, Avvisi (badge di conteggio);
- barra di stato: messaggio, utente, stato database, referenze/pezzi;
- toast in basso a destra per i movimenti registrati.

L'accesso utente (username/ruolo) è gestito da ``main.py`` prima di
aprire la finestra; ``DialogoAccesso`` resta disponibile per
riattivarlo.
"""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import Qt, SignalInstance
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QTabBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..sicurezza import Ruolo, autentica, schede_consenti as _schede_ruolo
from . import animazioni, tema
from .tema import M, tema_attivo
from .icone import ic_px, icona_svg, pixmap_icona
from .avvisi import SchedaAvvisi
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
}


def schede_consenti(ruolo: Ruolo | str) -> tuple[str, ...]:
    """Schede visibili per il ruolo (nomi in maiuscolo, ordine di visualizzazione).

    Delega a :func:`magazzino_profili.sicurezza.schede_consenti` (modulo
    congelato) e capitalizza solo le etichette.
    """
    try:
        return tuple(s.capitalize() for s in _schede_ruolo(ruolo))
    except ValueError:
        return ()


class DialogoAccesso(QWidget):
    """Richiede username + password e valida contro l'utente memorizzato.

    Serve una ``factory`` di sessioni: l'autenticazione usa il servizio
    congelato :func:`magazzino_profili.sicurezza.autentica`.
    """

    def __init__(
        self,
        factory=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._factory = factory
        self._utente = None
        self.setWindowTitle("Accesso")
        icona = _icona_applicazione()
        if icona is not None:
            self.setWindowIcon(icona)
        self.setFixedWidth(M.PROF_DX)
        t = tema.tema_attivo()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(M.CARD_PAD, M.CARD_PAD, M.CARD_PAD, M.CARD_PAD)
        layout.setSpacing(M.GAP_SM)

        titolo = QLabel("Magazzino Profili", self)
        titolo.setObjectName("TitoloCard")
        layout.addWidget(titolo)

        self.nome = QLineEdit(self)
        self.nome.setPlaceholderText("username")
        layout.addWidget(self.nome)

        self.password = QLineEdit(self)
        self.password.setPlaceholderText("password")
        self.password.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.password)

        self.messaggio = QLabel("", self)
        self.messaggio.setObjectName("Debole")
        layout.addWidget(self.messaggio)

        ok = bottone("Entra", classe="primario", parent=self)
        ok.clicked.connect(self._prova)
        layout.addWidget(ok)
        self.nome.setFocus()

    def _prova(self) -> None:
        if self._factory is None:
            self.messaggio.setText("Accesso non disponibile (nessun database)")
            return
        sessione = self._factory()
        try:
            self._utente = autentica(sessione, self.nome.text(), self.password.text())
        finally:
            sessione.close()
        if self._utente is None:
            self.messaggio.setText("Credenziali non valide")
            self.password.clear()
            return
        self.close()

    def utente(self):
        """L'utente autenticato (``None`` finché non è valida)."""
        return self._utente


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

    def __init__(
        self,
        factory,
        ruolo: Ruolo | str,
        nome_utente: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._factory = factory
        self._ruolo = Ruolo(ruolo)
        self._nome_utente = nome_utente
        self._toast: list[Toast] = []
        self._badge_avvisi: QLabel | None = None
        self._icone_nomi: list[str] = []

        self.setObjectName("Finestra")
        self.setWindowTitle("Magazzino Profili")
        icona = _icona_applicazione()
        if icona is not None:
            self.setWindowIcon(icona)
        self.resize(1280, 760)
        self.setMinimumSize(1280, 760)
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
        self._tab.currentChanged.connect(
            lambda i: animazioni.dissolvenza(self._tab.widget(i), animazioni.DURATA_BREVE)
        )
        self._radice.addWidget(self._tab, 1)

        self._costruisci_barra_stato()
        self._crea_schede()

        # Scorciatoie globali: Ctrl+Alt+Freccia sinistra/destra cambia la
        # scheda colore nella scheda Inventario.
        sx = QShortcut(QKeySequence("Ctrl+Alt+Left"), self)
        sx.setContext(Qt.ShortcutContext.WindowShortcut)
        sx.activated.connect(lambda: self._muovi_tab_colori(-1))
        dx = QShortcut(QKeySequence("Ctrl+Alt+Right"), self)
        dx.setContext(Qt.ShortcutContext.WindowShortcut)
        dx.activated.connect(lambda: self._muovi_tab_colori(1))

        self._messaggio("Apertura: accesso come " + self._nome_utente)
        self._aggiorna_stato_riepilogo()

    # ------------------------------------------------------------------
    # barra del titolo
    # ------------------------------------------------------------------
    def _costruisci_barra_titolo(self) -> None:
        t = tema_attivo()
        barra = QWidget(self)
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

        self.puls_report = bottone("Report", icona="file", parent=barra)
        self.puls_report.setProperty("menu", "true")
        menu = QMenu(self.puls_report)
        self._azione_excel = QAction("Esporta inventario in Excel", menu)
        self._azione_excel.setIcon(icona_svg("download", t.testo, ic_px(14)))
        self._azione_excel.triggered.connect(self._esporta_excel)
        self._azione_pdf = QAction("Esporta inventario in PDF", menu)
        self._azione_pdf.setIcon(icona_svg("file", t.testo, ic_px(14)))
        self._azione_pdf.triggered.connect(self._esporta_pdf)
        menu.addAction(self._azione_excel)
        menu.addAction(self._azione_pdf)
        menu.addSeparator()
        self._azione_animazioni = QAction("Animazioni di transizione", menu)
        self._azione_animazioni.setCheckable(True)
        self._azione_animazioni.setChecked(animazioni.attive())
        self._azione_animazioni.toggled.connect(lambda v: animazioni.imposta_attive(v))
        menu.addAction(self._azione_animazioni)
        self.puls_report.setMenu(menu)
        h.addWidget(self.puls_report)

        icona_tema = "moon" if t is tema.CHIARO else "sun"
        self.puls_tema = bottone("", dim="icona", icona=icona_tema, parent=barra)
        self.puls_tema.setFixedSize(M.BTN_ICONA, M.BTN_ICONA)
        self.puls_tema.setToolTip("Cambia tema scuro/chiaro")
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

        utente = QLabel(f"utente: {self._nome_utente} · {self._ruolo.value}", barra)
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
    def _crea_schede(self) -> None:
        self._tab.clear()
        self._icone_nomi.clear()
        self._badge_avvisi = None

        consentite = schede_consenti(self._ruolo)
        self.scheda_inventario: TabellaPezzi | None = None
        self.scheda_avvisi: SchedaAvvisi | None = None
        nomi = []

        if "Inventario" in consentite:
            self.scheda_inventario = TabellaPezzi(self._factory)
            nomi.append((self.scheda_inventario, "Inventario"))
        else:
            self.scheda_inventario = None

        def _collega_cambiato(scheda) -> None:
            # ``messaggio`` è un segnale solo dove esiste come SignalInstance
            # (nelle nuove schede è un widget MessaggioErrore, non un segnale).
            def _segnale_messaggio() -> bool:
                attr = getattr(scheda, "messaggio", None)
                return isinstance(attr, SignalInstance)

            if not hasattr(scheda, "cambiato") or scheda is self.scheda_avvisi:
                if _segnale_messaggio():
                    scheda.messaggio.connect(self.mostra_toast)
                return
            if self.scheda_inventario is not None:
                scheda.cambiato.connect(self.scheda_inventario.aggiorna)
            if self.scheda_avvisi is not None:
                scheda.cambiato.connect(self.scheda_avvisi.aggiorna)
            if _segnale_messaggio():
                scheda.messaggio.connect(self.mostra_toast)

        if "Carico" in consentite:
            self.scheda_carico = SchedaCarico(self._factory, self._nome_utente)
            nomi.append((self.scheda_carico, "Carico"))
        if "Scarico" in consentite:
            self.scheda_scarico = SchedaScarico(self._factory, self._nome_utente)
            nomi.append((self.scheda_scarico, "Scarico"))
        if "Profili" in consentite:
            self.scheda_profilo = SchedaProfilo(self._factory)
            nomi.append((self.scheda_profilo, "Profili"))
        if "Avvisi" in consentite:
            self.scheda_avvisi = SchedaAvvisi(self._factory)
            nomi.append((self.scheda_avvisi, "Avvisi"))

        for scheda, nome in nomi:
            self._tab.addTab(scheda, nome)
            self._icone_nomi.append(_NOME_ICONA_SCHEDE.get(nome, "list"))
            _collega_cambiato(scheda)
            if nome == "Avvisi":
                # Avvisi -> "Dettagli": passa all'Inventario sulla scheda colore
                self.scheda_avvisi.vai_a_colore.connect(self._vai_a_colore_davvisi)
                # Avvisi -> "Carica": passa al Carico con il barcode compilato
                self.scheda_avvisi.vai_a_scheda.connect(self._vai_a_scheda)

        # Inventario -> Carico/Scarico: "Carica"/"Scarica" compilano il barcode
        if self.scheda_inventario is not None:
            self.scheda_inventario.vai_a_scheda.connect(self._vai_a_scheda)

        self._aggiorna_icone_schede()
        self._aggiorna_badge_avvisi()

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
        self._crea_schede()
        self._costruisci_barra_stato()
        nome = "chiaro" if tema.tema_attivo() is tema.CHIARO else "scuro"
        self._messaggio(f"Tema cambiato: {nome}")
        self._aggiorna_stato_riepilogo()

    def _messaggio(self, testo: str) -> None:
        self._barra_stato.setText(testo)

    def _aggiorna_stato_riepilogo(self) -> None:
        from ..services import consultazione

        t = tema_attivo()
        r = None
        try:
            sessione = self._factory()
            try:
                r = consultazione.riepilogo_inventario(sessione)
            finally:
                sessione.close()
            ok = True
        except Exception:
            ok = False
        self._stato_db.setText("PostgreSQL" if ok else "Database non raggiungibile")
        self._pallino_db.setPixmap(_pallino(t.ok if ok else t.pericolo, M.PILL_PUNTO))
        if r is not None:
            self._conta_riepilogo.setText(f"{r['referenze']} referenze · {r['pezzi_totali']} pezzi")

    def _aggiorna_badge_avvisi(self) -> None:
        from ..services import consultazione

        try:
            sessione = self._factory()
            try:
                n = len(consultazione.pezzi_da_riordinare(sessione))
            finally:
                sessione.close()
        except Exception:
            n = 0
        for i in range(self._tab.count()):
            if self._tab.tabText(i) != "Avvisi":
                continue
            if self._badge_avvisi is None:
                self._badge_avvisi = QLabel("0", self)
                self._badge_avvisi.setObjectName("Conta")
                self._badge_avvisi.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._badge_avvisi.setText(str(n))
            self._badge_avvisi.setVisible(n > 0)
            self._tab.tabBar().setTabButton(i, QTabBar.ButtonPosition.RightSide, self._badge_avvisi)
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
    def _esporta_pdf(self) -> None:
        try:
            from ..reports import genera_pdf_inventario
        except Exception as errore:  # report non disponibile
            QMessageBox.warning(self, "Report", f"PDF non disponibile: {errore}")
            return
        default = os.path.join(os.getcwd(), "inventario.pdf")
        percorso, _ = QFileDialog.getSaveFileName(self, "Salva PDF", default, "PDF (*.pdf)")
        if not percorso:
            return
        try:
            sessione = self._factory()
            try:
                n = genera_pdf_inventario(sessione, percorso)
            finally:
                sessione.close()
            self._messaggio(f"Report PDF generato: {n} righe")
        except Exception as errore:
            self._messaggio(f"Errore PDF: {errore}")
            QMessageBox.critical(self, "Report", str(errore))

    def _esporta_excel(self) -> None:
        default = os.path.join(os.getcwd(), "inventario.xlsx")
        percorso, _ = QFileDialog.getSaveFileName(self, "Salva Excel", default, "Excel (*.xlsx)")
        if not percorso:
            return
        try:
            import openpyxl
            from ..services import consultazione
        except ImportError:
            QMessageBox.warning(self, "Report", "openpyxl non installato")
            return
        sessione = self._factory()
        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Inventario"
            ws.append(["Barcode", "Profilo", "Colore", "Lunghezza (mm)", "Quantità", "Ubicazione"])
            for z in consultazione.lista_pezzi(sessione):
                ws.append([
                    z.barcode,
                    z.profilo.codice,
                    z.colore.nome_visualizzato,
                    z.lunghezza_mm,
                    z.quantita,
                    z.ubicazione or "",
                ])
            wb.save(percorso)
        finally:
            sessione.close()
        self._messaggio(f"Report Excel generato: {percorso}")


def _icona_schede() -> "object":
    """Dimensione icona delle schede principali (24 px logici)."""
    from PySide6.QtCore import QSize

    return QSize(ic_px(16), ic_px(16))
