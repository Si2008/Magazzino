"""Widget Qt per la lettura di barcode da scanner USB.

Lo scanner si comporta come una tastiera che digita il codice e
termina con Invio: il widget intercetta quell'Invio, emette il segnale
``barcode_scansionato`` con il valore ripulito da spazi e si svuota,
pronto per la scansione successiva.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLineEdit


class CampoScanner(QLineEdit):
    """Campo di testo per barcode: all'Invio emette il codice scansionato.

    Uso::

        campo = CampoScanner()
        campo.barcode_scansionato.connect(lancia_scarche)

    """

    #: Emesso alla pressione di Invio, con il testo del campo ripulito
    #: dagli spazi agli estremi. Non viene emesso se il campo è vuoto.
    barcode_scansionato = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setPlaceholderText("Scansiona il barcode e premi Invio")
        self.returnPressed.connect(self._gestisci_invio)
        # Il campo deve essere pronto a ricevere la scansione subito.
        self.setFocus()

    def _gestisci_invio(self) -> None:
        """Emette il segnale col valore ripulito e svuota il campo.

        Se il campo contiene solo spazi, il segnale non viene emesso:
        un codice vuoto non può corrispondere a nessun pezzo.
        """
        valore = self.text().strip()
        self.clear()
        if valore:
            self.barcode_scansionato.emit(valore)
