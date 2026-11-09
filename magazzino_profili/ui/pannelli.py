"""Divisione ridimensionabile: nessuna animazione o scrittura di preferenze."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter
from .tema import M


class DivisionePannelli(QSplitter):
    def __init__(self, proporzioni, parent=None):
        super().__init__(Qt.Horizontal, parent)
        self._proporzioni = proporzioni
        self._posizionata = False

    def showEvent(self, evento):
        super().showEvent(evento)
        if not self._posizionata:
            spazio = max(1, self.width() - self.handleWidth())
            totale = sum(self._proporzioni)
            self.setSizes([round(spazio * peso / totale) for peso in self._proporzioni])
            self._posizionata = True


def dividi_pannelli(sinistra, destra, proporzioni, parent=None):
    divisore = DivisionePannelli(proporzioni, parent)
    divisore.setObjectName("DivisionePannelli")
    divisore.setChildrenCollapsible(False)
    # Sui PC meno veloci il contenuto viene ridisegnato al rilascio del mouse.
    divisore.setOpaqueResize(False)
    divisore.setHandleWidth(M.DIVISORE_W)
    divisore.addWidget(sinistra)
    divisore.addWidget(destra)
    divisore.setStretchFactor(0, 1)
    divisore.setStretchFactor(1, 1)
    divisore.handle(1).setToolTip("Trascina per allargare o restringere le colonne")
    divisore.handle(1).setAccessibleName("Ridimensiona le colonne")
    return divisore
