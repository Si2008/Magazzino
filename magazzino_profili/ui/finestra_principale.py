"""Finestra principale: barra superiore, schede e barra di stato.

Layout (come nel mockup):

- barra superiore: brand "Magazzino Profili" + pulsante "Report"
  (menu PDF/Excel) + pulsante tema (scuro/chiaro);
- tab: Inventario, Carico, Scarico, Profili, Avvisi (con badge di
  conteggio);
- barra di stato: ultimo messaggio + conteggio referenze/pezzi.

L'accesso utente (username/ruolo) è gestito da ``main.py`` prima di
aprire la finestra; ``DialogoAccesso`` resta disponibile per
riattivarlo.
"""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..sicurezza import Ruolo, autentica, schede_consenti as _schede_ruolo
from . import tema
from .tema import px
from .avvisi import SchedaAvvisi
from .scheda_carico import SchedaCarico
from .scheda_profilo import SchedaProfilo
from .scheda_scarico import SchedaScarico
from .tabella_pezzi import TabellaPezzi


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
        self.setFixedWidth(px(380))
        t = tema.tema_attivo()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(18), px(18), px(18), px(18))
        layout.setSpacing(px(10))

        titolo = QLabel("Magazzino Profili", self)
        titolo.setStyleSheet(f"font-size: {px(18)}px; font-weight: 800;")
        layout.addWidget(titolo)

        self.nome = QLineEdit(self)
        self.nome.setPlaceholderText("username")
        layout.addWidget(self.nome)

        self.password = QLineEdit(self)
        self.password.setPlaceholderText("password")
        self.password.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.password)

        self.messaggio = QLabel("", self)
        self.messaggio.setStyleSheet(f"color: {t.pericolo}; font-size: {px(13)}px;")
        layout.addWidget(self.messaggio)

        ok = QPushButton("Entra", self)
        ok.setProperty("classe", "primario")
        ok.clicked.connect(self._prova)
        layout.addWidget(ok)
        self.nome.setFocus()

    def _prova(self) -> None:
        t = tema.tema_attivo()
        if self._factory is None:
            self.messaggio.setStyleSheet(f"color: {t.pericolo}; font-size: {px(13)}px;")
            self.messaggio.setText("Accesso non disponibile (nessun database)")
            return
        sessione = self._factory()
        try:
            self._utente = autentica(sessione, self.nome.text(), self.password.text())
        finally:
            sessione.close()
        if self._utente is None:
            self.messaggio.setStyleSheet(f"color: {t.pericolo}; font-size: {px(13)}px;")
            self.messaggio.setText("Credenziali non valide")
            self.password.clear()
            return
        self.close()

    def utente(self):
        """L'utente autenticato (``None`` finché non è valida)."""
        return self._utente


def _icona_applicazione() -> QIcon | None:
    """Icona dell'app: cercata in _MEIPASS (eseguibile) o nella radice del progetto."""
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

        self.setWindowTitle("Magazzino Profili")
        icona = _icona_applicazione()
        if icona is not None:
            self.setWindowIcon(icona)
        self.resize(px(1150), px(720))
        self._applica_tema()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(14), px(12), px(14), px(8))
        layout.setSpacing(px(10))

        layout.addWidget(self._costruisci_barra_superiore())

        self._tab = QTabWidget(self)
        self._tab.setDocumentMode(True)
        layout.addWidget(self._tab, 1)

        self._barra_stato = QLabel(self)
        self._crea_schede()
        self._barra_stato.setObjectName("TestoDim")
        self._barra_stato.setStyleSheet(
            f"border-top: 1px solid {tema.tema_attivo().bordo}; padding-top: {px(7)}px; font-size: {px(12.5)}px;"
        )
        layout.addWidget(self._barra_stato)

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
    # barra superiore
    # ------------------------------------------------------------------
    def _costruisci_barra_superiore(self) -> QWidget:
        t = tema.tema_attivo()
        w = QWidget(self)
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(px(10))

        brand = QLabel("Magazzino Profili", w)
        brand.setStyleSheet(f"font-size: {px(19)}px; font-weight: 800;")
        h.addWidget(brand)
        h.addSpacing(px(6))
        chi = QLabel(f"utente: {self._nome_utente} · {self._ruolo.value}", w)
        chi.setStyleSheet(f"font-size: {px(12.5)}px; color: {t.testo_debole};")
        h.addWidget(chi)
        h.addStretch(1)

        self.puls_report = QPushButton("Report  ▾", w)
        menu = QMenu(self.puls_report)
        self._azione_pdf = QAction("Esporta PDF inventario", menu)
        self._azione_pdf.triggered.connect(self._esporta_pdf)
        self._azione_excel = QAction("Esporta Excel inventario", menu)
        self._azione_excel.triggered.connect(self._esporta_excel)
        menu.addAction(self._azione_pdf)
        menu.addAction(self._azione_excel)
        self.puls_report.setMenu(menu)
        h.addWidget(self.puls_report)

        self.puls_tema = QPushButton("Tema", w)
        self.puls_tema.setToolTip("Cambia tema scuro/chiaro")
        self.puls_tema.clicked.connect(self._cambia_tema)
        h.addWidget(self.puls_tema)
        return w

    # ------------------------------------------------------------------
    # schede
    # ------------------------------------------------------------------
    def _crea_schede(self) -> None:
        self._tab.clear()

        consentite = schede_consenti(self._ruolo)
        self.scheda_inventario: TabellaPezzi | None = None

        if "Inventario" in consentite:
            self.scheda_inventario = TabellaPezzi(self._factory)
            self._tab.addTab(self.scheda_inventario, "Inventario")
        def _collega_cambiato(scheda) -> None:
            if self.scheda_inventario is not None:
                scheda.cambiato.connect(self.scheda_inventario.aggiorna)

        if "Carico" in consentite:
            self.scheda_carico = SchedaCarico(self._factory, self._nome_utente)
            self._tab.addTab(self.scheda_carico, "Carico")
            _collega_cambiato(self.scheda_carico)
        if "Scarico" in consentite:
            self.scheda_scarico = SchedaScarico(self._factory, self._nome_utente)
            self._tab.addTab(self.scheda_scarico, "Scarico")
            _collega_cambiato(self.scheda_scarico)
        if "Profili" in consentite:
            self.scheda_profilo = SchedaProfilo(self._factory)
            self._tab.addTab(self.scheda_profilo, "Profili")
            _collega_cambiato(self.scheda_profilo)
        if "Avvisi" in consentite:
            self.scheda_avvisi = SchedaAvvisi(self._factory)
            self._tab.addTab(self.scheda_avvisi, "Avvisi")
            # Avvisi -> "Dettagli": passa all'Inventario sulla scheda colore
            self.scheda_avvisi.vai_a_colore.connect(self._vai_a_colore_davvisi)

        # gli avvisi vanno aggiornati dopo ogni movimento
        for nome in ("scheda_carico", "scheda_scarico", "scheda_profilo"):
            scheda = getattr(self, nome, None)
            if scheda is not None and getattr(self, "scheda_avvisi", None) is not None:
                scheda.cambiato.connect(self.scheda_avvisi.aggiorna)

        self._aggiorna_badge_avvisi()

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
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(tema.qss_globale(tema.tema_attivo()))

    def _cambia_tema(self) -> None:
        tema.alterna_tema()
        self._applica_tema()
        # ricostruisce le schede perché i colori sono applicati alla creazione
        self._crea_schede()
        nome = "chiaro" if tema.tema_attivo() is tema.CHIARO else "scuro"
        self._messaggio(f"Tema cambiato: {nome}")
        self._aggiorna_stato_riepilogo()

    def _messaggio(self, testo: str) -> None:
        self._barra_stato.setText(testo)

    def _aggiorna_stato_riepilogo(self) -> None:
        from ..services import consultazione

        sessione = self._factory()
        try:
            r = consultazione.riepilogo_inventario(sessione)
        finally:
            sessione.close()
        base = self._barra_stato.text()
        base = base.split("  ·  ")[0] if "  ·  " in base else base
        self._barra_stato.setText(
            f"{base}   ·   {r['referenze']} referenze · {r['pezzi_totali']} pezzi in giacenza"
        )

    def _aggiorna_badge_avvisi(self) -> None:
        from ..services import consultazione

        sessione = self._factory()
        try:
            n = len(consultazione.pezzi_da_riordinare(sessione))
        finally:
            sessione.close()
        for i in range(self._tab.count()):
            if self._tab.tabText(i) == "Avvisi":
                etichetta = "Avvisi" if n == 0 else f"Avvisi ({n})"
                self._tab.setTabText(i, etichetta)
                break

    # ------------------------------------------------------------------
    # report
    # ------------------------------------------------------------------
    def _esporta_pdf(self) -> None:
        t = tema.tema_attivo()
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
