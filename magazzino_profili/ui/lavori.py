"""Lavori lunghi fuori dal thread grafico, con risultato e errore espliciti."""
import logging
from PySide6.QtCore import QThread, Signal


class Lavoro(QThread):
    riuscito = Signal(object)
    fallito = Signal(str)

    def __init__(self, azione, parent=None):
        super().__init__(parent)
        self._azione = azione

    def run(self):
        try:
            self.riuscito.emit(self._azione())
        except Exception as errore:
            logging.getLogger(__name__).exception("Operazione non riuscita")
            self.fallito.emit(str(errore))
