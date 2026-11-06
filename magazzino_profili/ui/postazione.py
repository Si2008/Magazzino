"""Configurazione LAN e finestra secondaria senza connessione al magazzino."""
from PySide6.QtWidgets import (QWidget,QDialog,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,
    QLineEdit,QFileDialog,QMessageBox,QDialogButtonBox,QApplication,QFrame)
from PySide6.QtCore import QTimer
from pathlib import Path
from .componenti import bottone
from ..services import postazione
from ..db.config import ErroreConfigurazione, trova_config


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
    db=bottone('Seleziona config.toml del PC principale…',parent=d);v.addWidget(db)
    percorso_iniziale=postazione.configurazione_database() or (str(trova_config()) if trova_config() else '')
    percorso_label=QLabel(percorso_iniziale or 'Configurazione non selezionata',d)
    percorso_label.setProperty('percorso_config',percorso_iniziale)
    percorso_label.setWordWrap(True);percorso_label.setObjectName('Suggerimento');v.addWidget(percorso_label)
    def scegli_db():
        p,_=QFileDialog.getOpenFileName(d,'Seleziona la configurazione del database','','Configurazione (*.toml)')
        if p:
            try:
                postazione.valida_configurazione_database(p)
            except (OSError,ValueError,ErroreConfigurazione) as errore:
                QMessageBox.warning(d,'Configurazione PostgreSQL',
                    'Il file selezionato non contiene una configurazione database valida.\n\n'+str(errore))
                return
            percorso_label.setText(p)
            percorso_label.setProperty('percorso_config',p)
    db.clicked.connect(scegli_db)
    v.addWidget(QLabel('Il ruolo cambia al prossimo avvio. Nessun database viene trasferito nella cartella di rete.',d))
    pulsanti=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel,d);v.addWidget(pulsanti)
    def accetta():
        if combo.currentData()=='principale':
            percorso=(percorso_label.property('percorso_config') or percorso_iniziale).strip()
            if not percorso or not Path(percorso).is_file():
                QMessageBox.warning(d,'Configurazione PostgreSQL',
                    'Per usare questo PC come principale seleziona il config.toml già usato dal magazzino. '
                    'Il principale richiede PostgreSQL; il secondario invece non richiede questo file.')
                return
            try:
                postazione.valida_configurazione_database(percorso)
            except (OSError,ValueError,ErroreConfigurazione) as errore:
                QMessageBox.warning(d,'Configurazione PostgreSQL','Impossibile leggere config.toml:\n\n'+str(errore))
                return
            from PySide6.QtCore import QSettings
            from ..percorsi_installazione import preferenze
            s=preferenze('MagazzinoProfili','Postazione');s.setValue('config_database',percorso);s.sync()
            if s.status()!=QSettings.Status.NoError:
                QMessageBox.warning(d,'Configurazione PostgreSQL','Impossibile salvare il percorso della configurazione.')
                return
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
