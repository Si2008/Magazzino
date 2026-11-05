"""Sezione ingrandibile con panoramica, zoom e adattamento alla finestra."""
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QImageReader, QPixmap
from PySide6.QtGui import QPainter
from functools import lru_cache
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QGraphicsView, QGraphicsScene
from .componenti import bottone


def leggi_anteprima(percorso, larghezza, altezza):
    reader = QImageReader(str(percorso))
    reader.setAutoTransform(True)
    size = reader.size()
    if size.isValid():
        reader.setScaledSize(size.scaled(QSize(larghezza, altezza), Qt.AspectRatioMode.KeepAspectRatio))
    return QPixmap.fromImage(reader.read())


@lru_cache(maxsize=256)
def miniatura_sezione(nome, modifica, dimensione):
    """Miniature 48×48, cache limitata; sfondo bianco anche nel tema scuro."""
    originale = leggi_anteprima(nome, 44, 44)
    if originale.isNull():
        return originale
    miniatura = QPixmap(48, 48)
    miniatura.fill(Qt.GlobalColor.white)
    pittore = QPainter(miniatura)
    pittore.drawPixmap((48-originale.width())//2, (48-originale.height())//2, originale)
    pittore.end()
    return miniatura


class VisualizzatoreImmagine(QDialog):
    def __init__(self, percorso, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sezione del profilo")
        self.resize(1000, 750)
        immagine = leggi_anteprima(percorso, 4096, 4096)
        if immagine.isNull():
            raise ValueError("Immagine PNG assente o illeggibile")
        layout = QVBoxLayout(self)
        barra = QHBoxLayout()
        self.vista = QGraphicsView(self)
        scena = QGraphicsScene(self.vista)
        self.elemento = scena.addPixmap(immagine)
        self.vista.setScene(scena)
        self.vista.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        for testo, azione in (("−", lambda: self.vista.scale(.8, .8)),
                              ("+", lambda: self.vista.scale(1.25, 1.25)),
                              ("Adatta", self.adatta), ("1:1", self.vista.resetTransform)):
            b = bottone(testo, parent=self)
            b.clicked.connect(azione)
            barra.addWidget(b)
        barra.addStretch(1)
        chiudi = bottone("Chiudi", parent=self)
        chiudi.clicked.connect(self.accept)
        barra.addWidget(chiudi)
        layout.addLayout(barra)
        layout.addWidget(self.vista, 1)

    def showEvent(self, evento):
        super().showEvent(evento)
        self.adatta()

    def adatta(self):
        self.vista.fitInView(self.elemento, Qt.AspectRatioMode.KeepAspectRatio)


def apri_immagine(percorso, parent=None):
    dialogo = VisualizzatoreImmagine(percorso, parent)
    dialogo.exec()
    dialogo.deleteLater()
