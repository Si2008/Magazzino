"""Impostazioni della singola postazione; nessuna credenziale o login."""
import os
import sys
from pathlib import Path
from PySide6.QtCore import QSettings


def impostazioni():
    s=QSettings('MagazzinoProfili','Postazione')
    return ('secondario' if '--secondario' in sys.argv else str(s.value('ruolo','principale'))),str(s.value('cartella_rete',''))


def salva(ruolo,rete):
    if ruolo not in ('principale','secondario'):raise ValueError('Postazione non valida')
    s=QSettings('MagazzinoProfili','Postazione');s.setValue('ruolo',ruolo);s.setValue('cartella_rete',rete.strip());s.sync()
    if s.status()!=QSettings.Status.NoError:raise OSError('Impossibile salvare le impostazioni della postazione')


def archivio_locale():
    return Path(os.environ.get('LOCALAPPDATA',Path.home()))/'magazzino_profili/commesse_secondario'


def configurazione_database():
    return str(QSettings('MagazzinoProfili','Postazione').value('config_database',''))
