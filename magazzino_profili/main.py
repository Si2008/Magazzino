"""Avvio desktop senza login: tutti i privilegi. Backup e migrazioni protette; nessun accesso al DB operativo durante i test."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import os
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
    app = QApplication.instance() or QApplication(sys.argv)
    from .services.postazione import impostazioni,configurazione_database
    from .db.config import trova_config
    if not os.environ.get('MAGAZZINO_CONFIG') and configurazione_database():os.environ['MAGAZZINO_CONFIG']=configurazione_database()
    if trova_config() is None and impostazioni()[0]!='secondario':
        from .ui.postazione import configura
        if not configura(): return 0
        if configurazione_database():os.environ['MAGAZZINO_CONFIG']=configurazione_database()
    if impostazioni()[0]=='secondario':
        from .ui.postazione import FinestraSecondaria
        finestra=FinestraSecondaria();finestra.show()
        QTimer = __import__('PySide6.QtCore',fromlist=['QTimer']).QTimer
        QTimer.singleShot(0,lambda:_controlla_aggiornamento_in_background(finestra,app,None))
        return app.exec()

    # 1) Configurazione del database.
    try:
        configuration = leggi_config()
    except Exception as errore:  # noqa: BLE001
        QMessageBox.critical(
            None,
            "Database",
            "Impossibile leggere il file config.toml: verificare percorso e sintassi."
            + chr(10) + f"Dettaglio: {errore}"
        )
        return 1

    # 2) Engine + tables + migrations. The local server is started if needed.
    engine = None
    try:
        if configuration.host in ("localhost", "127.0.0.1", "::1"):
            ensure_running(configuration.host, configuration.porta)
        engine = crea_engine(config=configuration)
        _backup_prima_migrazioni(engine, configuration)
        crea_tabelle(engine)
        applica_migrazioni(engine)
        factory = crea_session_factory(engine)
    except Exception as errore:  # noqa: BLE001
        if engine is not None:
            engine.dispose()
        QMessageBox.critical(
            None,
            "Database",
            "Impossibile connettersi al database: verificare che il server PostgreSQL sia avviato "
            "e che i parametri in config.toml siano corretti."
            + chr(10) + chr(10) + "Eseguire setup_database.py per avviare il server." + chr(10) + f"Dettaglio: {errore}",
        )
        return 1

    # 3) Backup automatico all'avvio e ogni N ore (ultimi K conservati).
    try:
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
        from .services.scadenze import PianificatoreScadenze, leggi_config_scadenze
        parametri_scadenze = leggi_config_scadenze()
        scadenze = PianificatoreScadenze(factory, parametri_scadenze.intervallo_secondi)
    except Exception as errore:
        engine.dispose()
        QMessageBox.critical(None, "Configurazione servizi", f"Backup o scadenze non configurati correttamente: {errore}")
        return 1
    try:
        pianificatore.avvia(asincrono=True)
        scadenze.avvia()
        return _apri_interfaccia(app, factory, pianificatore, scadenze)
    finally:
        try:
            scadenze.ferma(timeout=10.0)
        finally:
            pianificatore.ferma(timeout=610.0)
            engine.dispose()


def _backup_prima_migrazioni(engine, configurazione):
    """Un aggiornamento di schema non deve partire senza un dump verificato."""
    from sqlalchemy import inspect
    from .db.migrazioni import migrazioni_pendenti
    if engine.dialect.name != "postgresql" or "pezzi" not in inspect(engine).get_table_names():
        return
    if migrazioni_pendenti(engine):
        p = leggi_config_backup()
        if _comando_pg_restore(p.pg_dump) is None:
            raise RuntimeError("Migrazione sospesa: pg_restore necessario per verificare il backup preventivo")
        _esegui_backup_singolo(configurazione, p.cartella, p.max_backup, p.pg_dump)


def _apri_interfaccia(app, factory, pianificatore, scadenze=None):

    from .sicurezza import Ruolo

    # 5) Finestra principale con i permessi del ruolo.
    finestra = FinestraPrincipale(factory, Ruolo.AMMINISTRATORE, "operatore")
    finestra._pianificatore_backup = pianificatore
    finestra._pianificatore_scadenze = scadenze
    finestra.showMaximized()
    from .services.aggiornamenti import conferma_versione_avviata
    try:
        conferma_versione_avviata()
    except Exception:
        logging.getLogger(__name__).exception("Versione aperta ma attivazione del launcher non riuscita")
    from PySide6.QtCore import QTimer
    if "--avvio-background" in sys.argv and getattr(finestra, "_tray", None):
        finestra.hide()
    QTimer.singleShot(0, lambda: _controlla_aggiornamento_in_background(finestra, app, pianificatore))
    from .db.config import leggi_sezione
    web, _ = leggi_sezione("web")
    if web.get("avvio_automatico", bool(web)):
        QTimer.singleShot(0, finestra._avvia_server_telefono)
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


def _controlla_aggiornamento_in_background(finestra, app, pianificatore):
    """Il feed non blocca l'apertura della finestra né il thread grafico."""
    from .services import aggiornamenti as agg
    from .ui.lavori import Lavoro
    from . import __version__
    configurazione = agg.leggi_config_aggiornamento()
    if not (configurazione.abilitato and configurazione.feed_url):
        return
    def controlla():
        return agg.leggi_feed(configurazione.feed_url, timeout=8)
    def ricevuto(manifest):
        if not agg.esiste_aggiornamento(manifest.versione, __version__):
            return
        from .ui.dialogo_aggiornamento import DialogoAggiornamento
        from PySide6.QtWidgets import QDialog
        lavoro.wait(2000)
        if lavoro in finestra._lavori:
            finestra._lavori.remove(lavoro)
        dialogo = DialogoAggiornamento(manifest, parent=finestra, prima_del_riavvio=finestra._prepara_riavvio,
                                       ripristina_servizi=finestra._riprendi_servizi)
        if dialogo.exec() == QDialog.Accepted:
            finestra._esci_davvero = True
            finestra.close()
    lavoro = Lavoro(controlla, finestra)
    if not hasattr(finestra, "_lavori"):
        finestra._lavori = []
    finestra._lavori.append(lavoro)
    lavoro.riuscito.connect(ricevuto)
    lavoro.fallito.connect(lambda messaggio: logging.getLogger(__name__).info("Feed aggiornamenti: %s", messaggio))
    lavoro.finished.connect(lambda: finestra._lavori.remove(lavoro) if lavoro in finestra._lavori else None)
    lavoro.finished.connect(lavoro.deleteLater)
    lavoro.start()


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
    cartella = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "magazzino_profili"
    try:
        cartella.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            handlers=[RotatingFileHandler(cartella / "app.log", maxBytes=5_000_000,
                                          backupCount=3, encoding="utf-8")],
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
    except OSError as errore:
        logging.basicConfig(level=logging.INFO)
        logging.getLogger(__name__).warning("Log su file non disponibile: %s", errore)


if __name__ == "__main__":
    sys.exit(main())
