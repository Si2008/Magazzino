"""Impostazioni della singola postazione; nessuna credenziale o login."""
import os
import sys
from pathlib import Path
from PySide6.QtCore import QSettings
from ..percorsi_installazione import preferenze
from ..db.config import ErroreConfigurazione, leggi_config


def impostazioni():
    s=preferenze('MagazzinoProfili','Postazione')
    return ('secondario' if '--secondario' in sys.argv else str(s.value('ruolo','principale'))),str(s.value('cartella_rete',''))


def salva(ruolo,rete):
    if ruolo not in ('principale','secondario'):raise ValueError('Postazione non valida')
    s=preferenze('MagazzinoProfili','Postazione');s.setValue('ruolo',ruolo);s.setValue('cartella_rete',rete.strip());s.sync()
    if s.status()!=QSettings.Status.NoError:raise OSError('Impossibile salvare le impostazioni della postazione')


def archivio_locale():
    from ..percorsi_installazione import dati_runtime
    return dati_runtime() / 'commesse_secondario'


def configurazione_database():
    from ..percorsi_installazione import installata, config_installata
    if installata():
        return str(config_installata()) if config_installata().is_file() else ''
    return str(preferenze('MagazzinoProfili','Postazione').value('config_database',''))


def valida_configurazione_database(percorso):
    """Rifiuta un ruolo principale finché non è selezionato un TOML valido."""
    p=Path(percorso).expanduser()
    if not p.is_file():
        raise ErroreConfigurazione(
            'config.toml non trovato. Seleziona il file usato dal PC principale; '
            'il programma non crea né sostituisce una configurazione con credenziali inventate.'
        )
    leggi_config(p)
    from ..percorsi_installazione import installata, importa_config
    if installata():
        return importa_config(p)
    return p.resolve()
