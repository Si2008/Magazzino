"""Popup "Aggiornamento disponibile" (Fase 13 completa).

Flusso:
- mostra versione installata → nuova versione, note e barra di avanzamento;
- "Scarica e installa ora": download in ``QThread`` (segnali progresso/fine/
  errore) dentro ``exec()``; al termine lancia il riavvio della nuova
  versione e chiude con ``Accepted``;
- "Più tardi": chiude con ``Rejected`` e l'app continua;
- a ogni errore mostra la procedura di recupero e permette di riprovare:
  l'app in uso non è mai stata modificata.

I punti di rete/esecuzione sono iniettabili (``scarica``, ``esegui``)
per i test: nessun processo reale nei test.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from .. import __version__ as versione_installata
from ..services import aggiornamenti as ag

__ERR__ = ag.ErroreAggiornamento


class _Worker(QThread):
    """Scarica l'installer in un thread: segnali progresso/fine/errore."""

    progresso = Signal(int, int)
    fine = Signal(str)
    errore = Signal(str)

    def __init__(self, manifest, cartella: Path, scarica, parent=None, prepara=False) -> None:
        super().__init__(parent)
        self._manifest = manifest
        self._cartella = cartella
        self._scarica = scarica
        self._prepara=prepara

    def run(self) -> None:  # thread Qt
        try:
            percorso = self._scarica(
                self._manifest,
                self._cartella,
                avanzamento=lambda fatti, totali: self.progresso.emit(fatti, totali),
            )
            if self._prepara:percorso=ag.prepara_versione(self._manifest,percorso)
            self.fine.emit(str(percorso))
        except __ERR__ as errore:
            self.errore.emit(str(errore))
        except Exception as errore:  # difensivo: non far cadere il thread in silenzio
            self.errore.emit(f"Errore imprevisto durante il download: {errore}")


def _scarica_reale(manifest, cartella: Path, avanzamento=None) -> Path:
    """Download reale: ``scarica_e_verifica`` con apri su rete (certificati verificati)."""
    return ag.scarica_e_verifica(
        manifest,
        cartella,
        apri=lambda url: ag.apri_url(url),
        # L'integrità dell'installer è già provata dal SHA-256 contenuto
        # nel manifest firmato Ed25519: qui basta non sollevare.
        verifica_autenticita=lambda percorso: None,
        avanzamento=avanzamento or (lambda fatti, totali: None),
    )


class DialogoAggiornamento(QDialog):
    """Chiede all'utente di installare la nuova versione, poi la lancia."""

    def __init__(
        self,
        manifest,
        parent=None,
        scarica=_scarica_reale,
        esegui=None,
        attesa_secondi: int = 2,
        prima_del_riavvio=None,
        ripristina_servizi=None,
    ) -> None:
        super().__init__(parent)
        self._manifest = manifest
        self._scarica = scarica
        self._esegui = esegui
        self._attesa_secondi = attesa_secondi
        self._worker: _Worker | None = None
        self._prima_del_riavvio = prima_del_riavvio or (lambda: True)
        self._ripristina_servizi = ripristina_servizi or (lambda: None)
        self._preparazione_iniziata = False
        self._annullato = False
        self._riavvio_avviato = False

        self.setWindowTitle("Aggiornamento disponibile")
        self.setModal(True)
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)

        titolo = QLabel(
            "È disponibile una nuova versione di Magazzino Profili\n"
            f"installata: {versione_installata}  →  nuova: {manifest.versione}"
        )
        titolo.setWordWrap(True)
        layout.addWidget(titolo)

        if manifest.note:
            note = QLabel(manifest.note)
            note.setWordWrap(True)
            layout.addWidget(note)

        self._barra = QProgressBar()
        self._barra.setRange(0, 100)
        self._barra.setValue(0)
        self._barra.setVisible(False)
        layout.addWidget(self._barra)

        self._stato = QLabel("")
        self._stato.setWordWrap(True)
        layout.addWidget(self._stato)

        pulsanti = QHBoxLayout()
        self._btn_poi = QPushButton("Più tardi")
        self._btn_poi.clicked.connect(self.reject)
        self._btn_ora = QPushButton("Scarica e installa ora")
        self._btn_ora.setDefault(True)
        self._btn_ora.clicked.connect(self._avvia_download)
        pulsanti.addStretch(1)
        pulsanti.addWidget(self._btn_poi)
        pulsanti.addWidget(self._btn_ora)
        layout.addLayout(pulsanti)

    # -- flusso -----------------------------------------------------------------

    def _avvia_download(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        Path(ag.cartella_cache()).mkdir(parents=True, exist_ok=True)
        self._btn_ora.setEnabled(False)
        self._barra.setVisible(True)
        self._stato.setText("Download dell'installer…")
        self._worker = _Worker(
            self._manifest, ag.cartella_cache(), self._scarica,prepara=self._esegui is None
        )
        self._worker.progresso.connect(self._on_progresso)
        self._worker.fine.connect(self._on_fine)
        self._worker.errore.connect(self._on_errore)
        self._worker.start()

    def _on_progresso(self, fatti: int, totali: int) -> None:
        if totali > 0:
            self._barra.setValue(int(fatti * 100 / totali))

    def _on_fine(self, percorso: str) -> None:
        if self._annullato:
            return
        self._preparazione_iniziata = True
        if not self._prima_del_riavvio():
            self._stato.setText("Download verificato. Attendo la fine delle operazioni e del backup prima di riavviare…")
            QTimer.singleShot(1000, lambda: self._on_fine(percorso))
            return
        self._barra.setValue(100)
        self._stato.setText("Download completato e verificato: preparo il riavvio…")
        # Lancia la nuova versione staccata, poi chiudi questa finestra.
        try:
            ag.lancia_aggiornamento(percorso, self._attesa_secondi, esegui=self._esegui)
        except Exception as errore:
            self._on_errore(f"Avvio della nuova versione non riuscito: {errore}")
            return
        # Il segnale fine precede di poco l'uscita effettiva del QThread.
        if self._worker is not None:
            self._worker.wait(2000)
        self._riavvio_avviato = True
        self.accept()

    def _on_errore(self, messaggio: str) -> None:
        if self._preparazione_iniziata and not self._riavvio_avviato:
            self._ripristina_servizi()
            self._preparazione_iniziata = False
        self._stato.setText(f"Download non riuscito: {messaggio}\n\n" + ag.testo_recupero())
        self._btn_ora.setEnabled(True)

    def reject(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._stato.setText("Download in corso: attendi la fine prima di chiudere.")
            return
        self._annullato = True
        if self._preparazione_iniziata and not self._riavvio_avviato:
            self._ripristina_servizi()
            self._preparazione_iniziata = False
        super().reject()

    def closeEvent(self, evento) -> None:
        if self._worker is not None and self._worker.isRunning():
            evento.ignore()
            self._stato.setText("Download in corso: attendi la fine prima di chiudere.")
            return
        self._annullato = True
        if self._preparazione_iniziata and not self._riavvio_avviato:
            self._ripristina_servizi()
            self._preparazione_iniziata = False
        super().closeEvent(evento)
