"""Configurazione LAN e finestra secondaria senza connessione al magazzino."""
from PySide6.QtWidgets import (QWidget,QDialog,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,
    QLineEdit,QFileDialog,QMessageBox,QDialogButtonBox,QApplication)
from PySide6.QtCore import QTimer
from .componenti import bottone
from ..services import postazione


def configura(parent=None):
    d=QDialog(parent);d.setWindowTitle('Postazione e cartella condivisa');d.setMinimumWidth(720)
    v=QVBoxLayout(d);ruolo,rete=postazione.impostazioni()
    v.addWidget(QLabel('Principale: unico magazzino ufficiale. Secondario: lettura e invio commesse, senza database.',d))
    combo=QComboBox(d);combo.addItem('PC principale','principale');combo.addItem('PC secondario','secondario');combo.setCurrentIndex(combo.findData(ruolo));v.addWidget(combo)
    v.addWidget(QLabel('Stessa cartella condivisa su tutti i PC (es. \\\\PC-PRINCIPALE\\Commesse)',d))
    riga=QHBoxLayout();campo=QLineEdit(rete,d);riga.addWidget(campo)
    cerca=bottone('Sfoglia',parent=d);riga.addWidget(cerca);v.addLayout(riga)
    def scegli():
        p=QFileDialog.getExistingDirectory(d,'Cartella condivisa')
        if p:campo.setText(p)
    cerca.clicked.connect(scegli)
    db=bottone('Seleziona configurazione PostgreSQL del principale…',parent=d);v.addWidget(db)
    def scegli_db():
        p,_=QFileDialog.getOpenFileName(d,'Configurazione PostgreSQL','','Configurazione (*.toml)')
        if p:
            from PySide6.QtCore import QSettings
            s=QSettings('MagazzinoProfili','Postazione');s.setValue('config_database',p);s.sync()
    db.clicked.connect(scegli_db)
    v.addWidget(QLabel('Il ruolo cambia al prossimo avvio. Nessun database viene trasferito nella cartella di rete.',d))
    pulsanti=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel,d);v.addWidget(pulsanti)
    def accetta():
        try:postazione.salva(combo.currentData(),campo.text())
        except (ValueError,OSError) as e:QMessageBox.warning(d,'Impostazioni',str(e));return
        d.accept()
    pulsanti.accepted.connect(accetta);pulsanti.rejected.connect(d.reject)
    return d.exec()==QDialog.DialogCode.Accepted


class FinestraSecondaria(QWidget):
    def __init__(self):
        super().__init__();self._lavori=[]
        from .. import __version__
        from . import tema
        app=QApplication.instance();app.setPalette(tema.palette_tema(tema.tema_attivo()));app.setStyleSheet(tema.qss_globale(tema.tema_attivo()))
        self.setWindowTitle('Magazzino Profili '+__version__+' · PC secondario');self.resize(1280,800)
        v=QVBoxLayout(self)
        b=bottone('Configura postazione e cartella di rete',parent=self);b.clicked.connect(lambda:configura(self));v.addWidget(b)
        from .scheda_commesse import SchedaCommesse
        self.commesse=SchedaCommesse(None,self._avvia_lavoro,self);v.addWidget(self.commesse,1)
    def _avvia_lavoro(self,titolo,azione,completato=None):
        from .finestra_principale import FinestraPrincipale
        return FinestraPrincipale._avvia_lavoro(self,titolo,azione,completato)
    def mostra_toast(self,testo,*_):self.commesse.stato.setText(testo)
    def _prepara_riavvio(self):return not any(w.isRunning() for w in self._lavori)
    def _riprendi_servizi(self):pass
    def closeEvent(self,event):
        if not self._prepara_riavvio():event.ignore();return
        super().closeEvent(event)
