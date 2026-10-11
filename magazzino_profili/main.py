"""Punto di avvio dell'applicazione "Magazzino Profili".

All'avvio:
1. legge la configurazione del database da config.toml;
2. crea l'engine e applica le migrazioni;
3. avvia il backup automatico (immediato + ogni N ore, ultimi K);
4. richiede l'accesso utente (username/password);
5. apre la finestra principale con le schede consentite al ruolo.

Esecuzione::

    python -m magazzino_profili.main
"""

from __future__ import annotations

import sys

from .backup import PianificatoreBackup, leggi_config_backup
from .db import crea_engine, crea_session_factory, crea_tabelle, leggi_config
from .db.server import ensure_running
from .db.migrazioni import applica_migrazioni
from .sicurezza import Ruolo, Utente
from .ui import FinestraPrincipale


def main() -> int:
    # Import ritardato: PySide6 serve solo quando si apre l'interfaccia.
    from PySide6.QtWidgets import QApplication, QMessageBox

    # 1) Configurazione del database.
    try:
        configuration = leggi_config()
    except Exception as errore:  # noqa: BLE001
        app = QApplication(sys.argv)
        QMessageBox.critical(
            None,
            "Database",
            "Impossibile to read the configurazione file: check the path and the syntax di config.toml."
        )
        return 1

    # 2) Engine + tables + migrations. The local server is started if needed.
    ensure_running(configuration.host, configuration.porta)
    try:
        engine = crea_engine(config=configuration)
        crea_tabelle(engine)
        applica_migrazioni(engine)
        factory = crea_session_factory(engine)
    except Exception as errore:  # noqa: BLE001
        app = QApplication(sys.argv)
        QMessageBox.critical(
            None,
            "Database",
            "Impossibile to connect to the database: check che the PostgreSQL server is started and che the parametri tra config.toml are correct."
            + chr(10) + chr(10) + "Execute setup_database.py to start the server." + chr(10) + f"Details: {errore}",
        )
        return 1

    # 3) Backup automatico all'avvio e ogni N ore (ultimi K conservati).
    parametri_backup = leggi_config_backup()
    pianificatore = PianificatoreBackup(
        intervallo_ore=parametri_backup.intervallo_ore,
        azione_backup=lambda: _esegui_backup_singolo(
            configuration,
            parametri_backup.cartella,
            parametri_backup.max_backup,
            parametri_backup.pg_dump,
        ),
    )
    pianificatore.avvia()

    # 4) Accesso utente: autenticazione DISATTIVATA per le prove —
    # si usa un amministratore predefinito senza chiedere credenziali.
    # (Per riattivarla: reintrodurre il DialogoAccesso della UI.)
    app = QApplication(sys.argv)
    utente = Utente(username="simone", ruolo=Ruolo.AMMINISTRATORE.value)

    # 5) Finestra principale con i permessi del ruolo.
    finestra = FinestraPrincipale(factory, utente.ruolo, utente.username)
    finestra.show()

    codice_uscita = app.exec()
    pianificatore.ferma()
    return codice_uscita


def _esegui_backup_singolo(
    configurazione, cartella: str, max_backup: int, pg_dump: str
) -> None:
    """Un singolo backup con i credenziali di config.toml."""
    from .backup import esegui_backup

    esegui_backup(
        host=configurazione.host,
        porta=configurazione.porta,
        utente=configurazione.utente,
        password=configurazione.password,
        dbname=configurazione.dbname,
        cartella=cartella,
        max_backup=max_backup,
        comando_base=(pg_dump,),
    )


if __name__ == "__main__":
    sys.exit(main())
