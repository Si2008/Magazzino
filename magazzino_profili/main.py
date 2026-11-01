"""Punto di avvio dell'applicazione "Magazzino Profili".

All'avvio:
1. legge la configurazione del database da config.toml;
2. crea l'engine e applica le migrazioni;
3. avvia il backup automatico (immediato + ogni N ore, ultimi K);
4. richiede l'accesso utente (username/password); nessun account predefinito;
5. apre la finestra principale con le schede consentite al ruolo.

Il controllo delle scadenze NON gira in questo processo: è un worker del
processo web separato (Fase 12). Chiude la finestra non deve fermarlo.

Esecuzione::

    python -m magazzino_profili.main
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from .backup import PianificatoreBackup, leggi_config_backup
from .db import crea_engine, crea_session_factory, crea_tabelle, leggi_config
from .db.server import ensure_running
from .db.migrazioni import applica_migrazioni
from .ui import FinestraPrincipale


def main() -> int:
    _configura_log()
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
            "Impossibile leggere il file config.toml: verificare percorso e sintassi."
            + chr(10) + f"Dettaglio: {errore}"
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
            "Impossibile connettersi al database: verificare che il server PostgreSQL sia avviato "
            "e che i parametri in config.toml siano corretti."
            + chr(10) + chr(10) + "Eseguire setup_database.py per avviare il server." + chr(10) + f"Dettaglio: {errore}",
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

    # 4) Accesso utente (sempre richiesto; nessun account predefinito).
    # Il controllo delle scadenze NON parte qui: è un worker del processo
    # web (``python -m magazzino_profili.web.app``), così chiude la finestra
    # non lo ferma.
    from PySide6.QtWidgets import QDialog, QStatusBar

    if not _esiste_almeno_un_utente(factory):
        raise RuntimeError(
            "La tabella utenti è vuota: crea il primo utente con "
            "setup_database.py o il tool di gestione utenti."
        )

    try:
        app = QApplication(sys.argv)
    except Exception as errore:  # es. interfaccia già attiva nel processo (test)
        print(f"ERRORE: impossibile avviare l'interfaccia: {errore}")
        return 1

    from .ui.finestra_principale import DialogoAccesso

    dialog = DialogoAccesso(factory=factory, parent=None)
    esito = dialog.exec()  # QDialog.DialogCode
    if esito != QDialog.Accepted:
        print(f"Accesso: {dialog.tooltip_fine}")
        return 1
    utente = dialog.utente()
    print(f"Accesso: {dialog.tooltip_fine}")

    # 4.5) Controllo aggiornamenti (Fase 13 completa), dopo il login:
    # se c'è una nuova versione e l'utente sceglie di installarla, la nuova
    # istanza viene lanciata e questa si chiude (senza aprire la finestra).
    if _controlla_aggiornamento(app, pianificatore):
        print("Aggiornamento: nuova versione avviata, la precedente si chiude.")
        return 0

    # 5) Finestra principale con i permessi del ruolo.
    finestra = FinestraPrincipale(factory, utente.ruolo, utente.username)
    finestra.showMaximized()
    barra_stato = finestra.findChild(QStatusBar, "barraStato")
    if barra_stato is not None:
        barra_stato.showMessage(dialog.tooltip_fine, 5000)

    codice_uscita = app.exec()
    pianificatore.ferma(timeout=10.0)
    return codice_uscita


def _controlla_aggiornamento(app, pianificatore) -> bool:
    """Controlla il feed dopo il login (Fase 13 completa).

    Ritorna True SOLO se è stata lanciata la nuova versione (la vecchia
    deve chiudersi senza aprire la finestra principale). Feed assente,
    errore di rete, sezione [update] disabilitata o versione uguale:
    silenzio (log), l'app funziona normalmente.
    """
    from PySide6.QtWidgets import QDialog

    from . import __version__
    from .services import aggiornamenti as agg

    configurazione = agg.leggi_config_aggiornamento()
    if not (configurazione.abilitato and configurazione.feed_url):
        return False
    try:
        manifest = agg.leggi_feed(configurazione.feed_url, timeout=8)
    except agg.ErroreAggiornamento as errore:
        logging.getLogger(__name__).info("Aggiornamenti: feed non disponibile: %s", errore)
        return False
    if not agg.esiste_aggiornamento(manifest.versione, __version__):
        return False

    from .ui.dialogo_aggiornamento import DialogoAggiornamento

    dialogo = DialogoAggiornamento(manifest, parent=None)
    if dialogo.exec() != QDialog.Accepted:
        return False
    # Il popup ha già lanciato la nuova versione staccata: chiudi la vecchia.
    pianificatore.ferma(timeout=10.0)
    app.quit()
    return True


def _esiste_almeno_un_utente(factory) -> bool:
    """True se esiste almeno una riga nella tabella ``utenti``."""
    from sqlalchemy import select

    from .sicurezza import Utente as UtenteModel

    with factory() as sessione:
        return sessione.scalars(select(UtenteModel).limit(1)).first() is not None


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
        comando_verifica=_comando_pg_restore(pg_dump),
    )


def _comando_pg_restore(pg_dump: str) -> tuple[str, ...] | None:
    """``pg_restore`` accanto a ``pg_dump`` (stessa cartella); ``None`` se non si trova."""
    percorso = Path(pg_dump)
    if percorso.name.lower().removesuffix(".exe") != "pg_dump":
        return None
    if percorso.parent == Path("."):  # solo il nome: lo risolve il PATH
        return ("pg_restore",)
    candidato = percorso.with_name("pg_restore" + percorso.suffix)
    if candidato.is_file():
        return (str(candidato),)
    logging.getLogger(__name__).warning("pg_restore non trovato accanto a pg_dump: backup non verificati")
    return None


def _configura_log() -> None:
    """Registro su file in %LOCALAPPDATA%\\magazzino_profili\\app.log.

    Se il file non è scrivibile, i messaggi restano su stderr e viene
    segnalato il motivo: non si ignora in silenzio.
    """
    cartella = Path.home() / "AppData" / "Local" / "magazzino_profili"
    try:
        cartella.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            filename=cartella / "app.log",
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
            encoding="utf-8",
        )
    except OSError as errore:
        logging.basicConfig(level=logging.INFO)
        logging.getLogger(__name__).warning("Log su file non disponibile: %s", errore)


if __name__ == "__main__":
    sys.exit(main())
