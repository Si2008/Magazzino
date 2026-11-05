"""Configurazione LAN e finestra secondaria senza connessione al magazzino."""
from PySide6.QtWidgets import (QWidget,QDialog,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,
    QLineEdit,QFileDialog,QMessageBox,QDialogButtonBox,QApplication,QFrame)
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


from .finestra_principale import FinestraPrincipale


class FinestraSecondaria(FinestraPrincipale):
    def __init__(self):
        # Stesso navigatore e stessa grafica del principale; il secondario non
        # carica config.toml e indica in ogni scheda il ruolo di questa postazione.
        from ..sicurezza import Ruolo
        super().__init__(None, Ruolo.AMMINISTRATORE, "operatore", secondario=True)


class SchedaSoloPrincipale(QWidget):
    """Contenuto coerente con il tema mentre il magazzino resta sul PC principale."""
    def __init__(self, nome, parent=None):
        super().__init__(parent)
        from .tema import M
        root=QVBoxLayout(self);root.setContentsMargins(M.PAG_H,M.PAG_T,M.PAG_H,M.PAG_B)
        card=QFrame(self);card.setObjectName("Card")
        contenuto=QVBoxLayout(card);contenuto.setContentsMargins(M.CARD_PAD,M.CARD_PAD,M.CARD_PAD,M.CARD_PAD)
        contenuto.setSpacing(M.GAP)
        titolo=QLabel(nome,card);titolo.setObjectName("TitoloCard");contenuto.addWidget(titolo)
        spiegazione=QLabel(
            f"La scheda {nome} è disponibile con il magazzino sul PC principale. "
            "Questa postazione non apre il database: usa la scheda Commesse per "
            "caricare e inviare i documenti al principale.",card)
        spiegazione.setObjectName("Suggerimento");spiegazione.setWordWrap(True)
        contenuto.addWidget(spiegazione);contenuto.addStretch(1);root.addWidget(card,1)
    def aggiorna(self):
        return None
    def _mostra_movimenti(self):
        return None
