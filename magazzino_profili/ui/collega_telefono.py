"""Collegamento del telefono come lettore barcode: controllo, dialogo e pulsante."""

from __future__ import annotations

import qrcode
from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.exc import SQLAlchemyError

from ..services import telefono as servizio
from ..db.config import ErroreConfigurazione as _ErroreConfigurazione
from .componenti import bottone
from .icone import ic_px, icona_svg, pixmap_icona
from .tema import M, rem, tema_attivo


# ---------------------------------------------------------------- controllo (polling)
class ControlloTelefono(QObject):
    """Interroga il database solo mentre il collegamento è attivo."""

    #: un barcode arrivato dal telefono
    scansione = Signal(str)
    #: True = ping recente (telefono collegato), False = nessun ping recente
    stato_cambiato = Signal(bool)
    #: True = ascolto avviato, False = fermato
    attivo_cambiato = Signal(bool)
    #: messaggio di errore (emesso una sola volta finché il problema dura)
    errore = Signal(str)

    INTERVALLO_MS = 1500

    def __init__(self, factory, parent: QObject | None = None, *, destinatario=None, consegna=None) -> None:
        super().__init__(parent)
        self._factory = factory
        self.destinatario = destinatario
        self._consegna = consegna
        self._poll_worker = None
        self._ack_worker = None
        self._ack_pending = []
        self._in_consegna = False
        self._attivo = False
        self._collegato = False
        self._errore_notificato = False
        self._timer = QTimer(self)
        self._timer.setInterval(self.INTERVALLO_MS)
        self._timer.timeout.connect(self.controlla)

    @property
    def attivo(self) -> bool:
        return self._attivo

    @property
    def collegato(self) -> bool:
        return self._attivo and self._collegato

    def avvia(self) -> None:
        """Inizia ad ascoltare. Le scansioni già in coda vengono scartate (mai consegnare roba vecchia)."""
        if self._attivo:
            return
        if self.destinatario:
            self._attivo = True
            self._timer.start()
            self.attivo_cambiato.emit(True)
            self.controlla()
            return
        try:
            sessione = self._factory()
            try:
                servizio.scarta_arretrate(sessione)
            finally:
                sessione.close()
        except SQLAlchemyError as e:
            self.errore.emit(f"Telefono: database non raggiungibile ({e.__class__.__name__}).")
            return
        self._attivo = True
        self._timer.start()
        self.attivo_cambiato.emit(True)
        self.controlla()

    def ferma(self) -> bool:
        self._timer.stop()
        self._attivo = False
        self._imposta_collegato(False)
        self.attivo_cambiato.emit(False)
        for worker in (self._poll_worker, self._ack_worker):
            if worker is not None and worker.isRunning():
                if not worker.wait(10000):
                    return False
        return True

    def controlla(self) -> None:
        """Un giro di controllo: nuove scansioni + stato del collegamento (una sessione per chiamata)."""
        if not self._attivo:
            return
        if self.destinatario:
            self._controlla_async()
            return
        try:
            sessione = self._factory()
            try:
                codici = servizio.preleva_scansioni(sessione)
            finally:
                sessione.close()
            sessione = self._factory()
            try:
                collegato = servizio.telefono_collegato(sessione)
            finally:
                sessione.close()
        except SQLAlchemyError as e:
            if not self._errore_notificato:
                self._errore_notificato = True
                self.errore.emit(f"Telefono: database non raggiungibile ({e.__class__.__name__}).")
            return
        self._errore_notificato = False
        self._imposta_collegato(collegato)
        for codice in codici:
            self.scansione.emit(codice)

    def _controlla_async(self):
        from .lavori import Lavoro
        if self._in_consegna or any(w is not None and w.isRunning() for w in (self._poll_worker, self._ack_worker)):
            return
        if self._ack_pending:
            da_confermare = list(self._ack_pending)
            def conferma():
                for id_, esito, dettaglio in da_confermare:
                    with self._factory() as sessione:
                        servizio.conferma_scansione(sessione, id_, self.destinatario, esito, dettaglio)
                return da_confermare
            lavoro = Lavoro(conferma, self)
            self._ack_worker = lavoro
            lavoro.riuscito.connect(lambda righe: [self._ack_pending.remove(r) for r in righe if r in self._ack_pending])
            lavoro.fallito.connect(self.errore.emit)
            lavoro.finished.connect(lambda: setattr(self, "_ack_worker", None))
            lavoro.finished.connect(lavoro.deleteLater)
            lavoro.start()
            return
        def leggi():
            with self._factory() as sessione:
                righe = servizio.prendi_scansioni(sessione, self.destinatario)
            with self._factory() as sessione:
                collegato = servizio.telefono_collegato(sessione, destinatario=self.destinatario)
            return righe, collegato
        lavoro = Lavoro(leggi, self)
        self._poll_worker = lavoro
        lavoro.riuscito.connect(self._consegna_risultati)
        lavoro.fallito.connect(self._errore_poll)
        lavoro.finished.connect(lambda: setattr(self, "_poll_worker", None))
        lavoro.finished.connect(lavoro.deleteLater)
        lavoro.start()

    def _errore_poll(self, messaggio):
        self._imposta_collegato(False)
        if not self._errore_notificato:
            self.errore.emit("Collegamento telefono non disponibile: " + messaggio)
        self._errore_notificato = True

    def _consegna_risultati(self, risultato):
        if not self._attivo:
            return  # un risultato già in coda non deve scrivere dopo Scollega/Esci
        righe, collegato = risultato
        self._errore_notificato = False
        self._imposta_collegato(collegato)
        self._in_consegna = True
        try:
            for id_, barcode in righe:
                try:
                    esito, dettaglio = self._consegna(barcode) if self._consegna else ("rifiutata", "Nessuna scheda pronta")
                except Exception:
                    import logging
                    logging.getLogger(__name__).exception("Consegna scansione %s", id_)
                    esito, dettaglio = "incerto", "Controllare la giacenza prima di ripetere"
                self._ack_pending.append((id_, esito, dettaglio))
        finally:
            self._in_consegna = False

    def _imposta_collegato(self, valore: bool) -> None:
        if valore != self._collegato:
            self._collegato = valore
            self.stato_cambiato.emit(valore)


# ---------------------------------------------------------------- QR
def pixmap_qr(testo: str, lato: int) -> QPixmap:
    """QR del testo come QPixmap quadrato di ``lato`` pixel (bianco e nero, indipendente dal tema)."""
    qr = qrcode.QRCode(border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(testo)
    qr.make(fit=True)
    matrice = qr.get_matrix()  # list[list[bool]], bordo incluso
    n = len(matrice)
    img = QImage(n, n, QImage.Format.Format_RGB32)
    img.fill(0xFFFFFFFF)
    for y, riga in enumerate(matrice):
        for x, nero in enumerate(riga):
            if nero:
                img.setPixel(x, y, 0xFF000000)
    img = img.scaled(
        lato, lato, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation
    )
    return QPixmap.fromImage(img)


# ---------------------------------------------------------------- pulsante nelle schede
def crea_pulsante_telefono(parent: QWidget) -> QPushButton:
    """Pulsante "Collega telefono" in alto a destra nella card (stile ghost, piccolo, icona ``phone``)."""
    b = bottone("Collega telefono", dim="sm", icona="phone", parent=parent)
    b.setProperty("telefono", "off")
    return b


def aggiorna_pulsante_telefono(b: QPushButton, collegato: bool) -> None:
    """"Telefono collegato" (verde) quando il telefono ha un ping recente, altrimenti "Collega telefono"."""
    t = tema_attivo()
    b.setText("Telefono collegato" if collegato else "Collega telefono")
    b.setProperty("telefono", "on" if collegato else "off")
    b.setIcon(icona_svg("phone", t.ok if collegato else t.testo, ic_px(13)))
    b.style().unpolish(b)
    b.style().polish(b)


# ---------------------------------------------------------------- dialogo
class DialogoTelefono(QDialog):
    """"Collega il telefono come lettore": QR + istruzioni, oppure stato "Telefono collegato"."""

    def __init__(self, controllo: ControlloTelefono, url: str | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controllo = controllo
        self._url = url
        self.setWindowTitle("Collega il telefono come lettore")
        self.setModal(True)
        self.setMinimumWidth(rem(38))
        self._radice = QVBoxLayout(self)
        self._radice.setContentsMargins(M.CARD_PAD, M.CARD_PAD, M.CARD_PAD, M.CARD_PAD)
        self._radice.setSpacing(M.GAP)
        self._corpo = QWidget(self)
        self._radice.addWidget(self._corpo)
        self._controllo.stato_cambiato.connect(self._ricostruisci)
        self._controllo.attivo_cambiato.connect(self._ricostruisci)
        self._ricostruisci()

    def _ricostruisci(self, *_args) -> None:
        # sostituisce il corpo: tre stati (senza indirizzo / in attesa / collegato)
        nuovo = QWidget(self)
        v = QVBoxLayout(nuovo)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(M.GAP)
        titolo = QLabel("Collega il telefono come lettore", nuovo)
        titolo.setObjectName("TitoloCard")
        v.addWidget(titolo)

        piede = QHBoxLayout()
        piede.addStretch(1)

        if not self._url or not self._url.lower().startswith("https://"):
            testo = QLabel(
                "Inserisci l'indirizzo HTTPS del servizio Magazzino.\n\n"
                "Per collegarti anche dalla rete mobile serve un dominio raggiungibile tramite "
                "tunnel HTTPS o VPN, con certificato riconosciuto dal telefono. "
                "Salvare un indirizzo non attiva il servizio né configura la rete. "
                "Il PC e il server devono rimanere accesi.",
                nuovo,
            )
            testo.setWordWrap(True)
            testo.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            v.addWidget(testo)
            indirizzo = QLineEdit(nuovo)
            indirizzo.setPlaceholderText("https://magazzino.tuo-dominio.it/")
            v.addWidget(indirizzo)
            salva = bottone("Salva indirizzo HTTPS", "primario", parent=nuovo)
            def salva_url():
                from ..db.config import scrivi_url_pubblico
                try:
                    base = scrivi_url_pubblico(indirizzo.text())
                    from urllib.parse import urlencode
                    self._url = base + ("?" + urlencode({"pc": self._controllo.destinatario}) if self._controllo.destinatario else "")
                    self._controllo.avvia()
                    self._ricostruisci()
                except (ValueError, OSError, _ErroreConfigurazione) as errore:
                    testo.setText(str(errore))
            salva.clicked.connect(salva_url)
            v.addWidget(salva)
        elif self._controllo.collegato:
            ico = QLabel(nuovo)
            ico.setPixmap(pixmap_icona("check", tema_attivo().ok, ic_px(34)))
            ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tit = QLabel("Telefono collegato", nuovo)
            tit.setObjectName("AvvTitolo")
            tit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sotto = QLabel(
                "Le scansioni arrivano nel campo barcode della scheda attiva: in Scarico il pezzo "
                "viene scaricato subito (serve la causale), in Carico compila i dati del pezzo.",
                nuovo,
            )
            sotto.setObjectName("Dim")
            sotto.setWordWrap(True)
            sotto.setAlignment(Qt.AlignmentFlag.AlignCenter)
            v.addWidget(ico)
            v.addWidget(tit)
            v.addWidget(sotto)
            scollega = bottone("Scollega", parent=nuovo)
            scollega.clicked.connect(self._scollega)
            piede.addWidget(scollega)
        else:
            riga = QHBoxLayout()
            riga.setSpacing(M.GAP)
            qr = QLabel(nuovo)
            qr.setPixmap(pixmap_qr(self._url, rem(11)))
            riga.addWidget(qr, 0, Qt.AlignmentFlag.AlignTop)
            col = QVBoxLayout()
            passi = QLabel(
                "1. Apri l'indirizzo qui sotto sul telefono (o inquadra il QR).\n"
                "2. La pagina si apre direttamente, senza credenziali.\n"
                "3. Tocca «Lettore» e inquadra il barcode del pezzo.",
                nuovo,
            )
            passi.setWordWrap(True)
            indirizzo = QLabel(self._url, nuovo)
            indirizzo.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            attesa = QLabel("In attesa del telefono…  (il server web deve essere avviato sul PC)", nuovo)
            attesa.setObjectName("Dim")
            attesa.setWordWrap(True)
            col.addWidget(passi)
            col.addWidget(indirizzo)
            col.addWidget(attesa)
            col.addStretch(1)
            riga.addLayout(col, 1)
            v.addLayout(riga)

        if self._url:
            cambia = bottone("Cambia indirizzo di collegamento", parent=nuovo)
            def modifica_url():
                self._url = None
                self._ricostruisci()
            cambia.clicked.connect(modifica_url)
            v.addWidget(cambia)

        chiudi = bottone("Chiudi", "primario", parent=nuovo)
        chiudi.clicked.connect(self.accept)
        piede.addWidget(chiudi)
        v.addLayout(piede)

        self._radice.replaceWidget(self._corpo, nuovo)
        self._corpo.deleteLater()
        self._corpo = nuovo

    def _scollega(self) -> None:
        self._controllo.ferma()
        self.accept()
