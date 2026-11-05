"""Backup automatico del database PostgreSQL tramite ``pg_dump``.

Comportamento richiesto:
- un backup viene eseguito all'avvio del programma;
- un nuovo backup viene eseguito ogni ``N`` ore (``N`` in config.toml);
- sono conservati solo gli ultimi ``K`` backup (``K`` in config.toml):
  i più vecchi vengono cancellati.

La password non viene passata sulla linea di comando: viene
esposta al processo ``pg_dump`` tramite la variabile d'ambiente
``PGPASSWORD``.
"""

from __future__ import annotations

import logging
import os
import subprocess
import threading
import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from ..db.config import leggi_sezione
from ..file_sicuri import blocco_cartella, destinazione_atomica

PERCORSO_CONFIG_PREDEFINITO = Path(__file__).resolve().parents[2] / "config.toml"

logger = logging.getLogger(__name__)

# Prefisso comune dei file di backup.
PREFISSO_FILE = "magazzino_profili_"
# Suffisso dei file di backup (formato custom di pg_dump).
SUFFISSO_FILE = ".dump"


class BackupErrore(Exception):
    """Il backup non è andato a buon fine."""


@dataclass
class ConfigurazioneBackup:
    """Parametri del backup letti da ``config.toml`` (sezione [backup])."""

    cartella: str = "backup"
    intervallo_ore: int = 6
    max_backup: int = 7
    pg_dump: str = "pg_dump"


def leggi_config_backup(
    percorso_config: str | Path | None = None,
) -> ConfigurazioneBackup:
    """Legge la sezione ``[backup]`` di config.toml con valori di ripiego."""
    cartella, intervallo, massimo = "backup", 6, 7
    dump = "pg_dump"
    sezione, base = leggi_sezione("backup", percorso_config)
    cartella = str(sezione.get("cartella", cartella))
    if not Path(cartella).is_absolute():
        cartella = str(base / cartella)
    dump = str(sezione.get("pg_dump", "pg_dump"))
    if ("/" in dump or "\\" in dump) and not Path(dump).is_absolute():
        dump = str(base / dump)
    intervallo = int(sezione.get("intervallo_ore", intervallo))
    massimo = int(sezione.get("max_backup", massimo))
    if intervallo <= 0 or massimo <= 0:
        raise ValueError("intervallo_ore e max_backup devono essere positivi")
    return ConfigurazioneBackup(
        cartella=cartella,
        intervallo_ore=intervallo,
        max_backup=massimo,
        pg_dump=dump,
    )


def esegui_backup(
    host: str,
    porta: int,
    utente: str,
    password: str,
    dbname: str,
    cartella: str | Path,
    max_backup: int = 7,
    comando_base: tuple[str, ...] | list[str] = ("pg_dump",),
    *,
    comando_verifica: tuple[str, ...] | list[str] | None = None,
) -> Path:
    """Backup serializzato fra processi; pubblicazione solo dopo verifica."""
    if isinstance(max_backup, bool) or max_backup < 1:
        raise ValueError("max_backup deve essere positivo")
    cartella = Path(cartella)
    cartella.mkdir(parents=True, exist_ok=True)
    finale = cartella / (PREFISSO_FILE + datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                        + "_" + uuid4().hex[:8] + SUFFISSO_FILE)
    with blocco_cartella(cartella):
        with destinazione_atomica(finale) as temporaneo:
            _crea_dump(host, porta, utente, password, dbname, temporaneo,
                       comando_base, comando_verifica)
        rimuovi_backup_venuti(cartella, max_backup)
    return finale


def _crea_dump(host, porta, utente, password, dbname, file_output,
               comando_base, comando_verifica):
    """Esegue un backup del database e applica il limite di ``max_backup``.

    - ``comando_base`` è il prefisso del comando da eseguire (di default
      ``pg_dump``): utile nei test per sostituire l'eseguibile;
    - il file creato ha nome ``magazzino_profili_AAAAmmgg_HHMMSS.dump``;
    - dopo la creazione, i backup più vecchi oltre ``max_backup``
      vengono cancellati.

    Restituisce il percorso del file appena creato.
    """
    comando = list(comando_base) + [
        "-h", host,
        "-p", str(porta),
        "-U", utente,
        "-d", dbname,
        "-Fc",
        "-f", str(file_output),
    ]

    ambiente = dict(os.environ)
    ambiente["PGPASSWORD"] = password or ""

    try:
        risultato = subprocess.run(
            comando,
            env=ambiente,
            capture_output=True,
            text=True,
            timeout=600,
        )
    except (subprocess.TimeoutExpired, OSError) as errore:
        raise BackupErrore(f"Impossibile eseguire il backup: {errore}") from errore

    if risultato.returncode != 0:
        dettaglio = (risultato.stderr or "").strip()
        raise BackupErrore(
            f"pg_dump terminato con codice {risultato.returncode}: {dettaglio}"
        )
    if not file_output.is_file():
        raise BackupErrore("Il comando ha terminato ma il file di backup non esiste")
    if file_output.stat().st_size == 0:
        file_output.unlink(missing_ok=True)
        raise BackupErrore("Il file di backup è vuoto")
    if comando_verifica is not None:
        try:
            verifica_backup(file_output, comando_verifica)
        except BackupErrore:
            file_output.unlink(missing_ok=True)  # un backup illeggibile non deve sostituire quelli buoni
            raise

    return file_output


def verifica_backup(
    file_backup: str | Path,
    comando_verifica: tuple[str, ...] | list[str],
    timeout: int = 120,
) -> None:
    """Controlla che l'archivio sia leggibile (``pg_restore --list``). Solleva ``BackupErrore``."""
    try:
        risultato = subprocess.run(
            [*comando_verifica, "--list", str(file_backup)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, OSError) as errore:
        raise BackupErrore(f"Impossibile verificare il backup: {errore}") from errore
    if risultato.returncode != 0:
        dettaglio = (risultato.stderr or "").strip()
        raise BackupErrore(f"Il backup non è leggibile (pg_restore codice {risultato.returncode}): {dettaglio}")


def rimuovi_backup_venuti(cartella: str | Path, max_backup: int) -> None:
    """Cancella i backup più vecchi mantenendo solo gli ultimi ``max_backup``.

    L'ordinamento è per nome file (il nome contiene la data/ora nel
    formato ``AAAAmmgg_HHMMSS``, quindi l'ordine lessicografico coincide
    con l'ordine cronologico).
    """
    cartella_p = Path(cartella)
    if not cartella_p.is_dir():
        return

    file = sorted(
        p for p in cartella_p.iterdir()
        if p.is_file()
        and p.name.startswith(PREFISSO_FILE)
        and p.name.endswith(SUFFISSO_FILE)
    )
    in_eccedenza = len(file) - max_backup
    for vecchio in file[: max(0, in_eccedenza)]:
        vecchio.unlink()


class PianificatoreBackup:
    """Esegue il backup all'avvio e poi ogni ``intervallo_ore`` ore.

    Il piano usa un ``threading.Timer`` di sottofondo: non blocca
    l'interfaccia e non richiede librerie aggiuntive.
    """

    def __init__(self, intervallo_ore: int, azione_backup) -> None:
        self.intervallo_ore = intervallo_ore
        self.azione_backup = azione_backup
        self._timer: threading.Timer | None = None
        self._blocco = threading.Lock()
        self._attivo = False
        self._generazione = 0
        self._worker = None
        self._in_corso = threading.Event()
        self.ultimo_esito = "Backup non ancora eseguito"

    def _esegui_e_ripiani(self) -> None:
        self._worker = threading.current_thread()
        self._in_corso.set()
        try:
            self.azione_backup()
            self.ultimo_esito = "Backup completato: " + datetime.now().astimezone().isoformat(timespec="seconds")
        except BackupErrore as errore:
            self.ultimo_esito = f"Backup non riuscito: {errore}"
            logger.error("Backup automatico non riuscito: %s", errore)
        except Exception:
            self.ultimo_esito = "Backup non riuscito: consultare il registro"
            logger.exception("Errore imprevisto durante il backup automatico")
        finally:
            self._in_corso.clear()
            self._pianifica_prossimo()
            self._worker = None

    @property
    def in_corso(self):
        return self._in_corso.is_set() or (self._worker is not None and self._worker.is_alive())

    def _pianifica_prossimo(self) -> None:
        with self._blocco:
            if not self._attivo:
                return
            self._timer = threading.Timer(
                self.intervallo_ore * 3600, self._esegui_e_ripiani
            )
            self._timer.daemon = True
            self._timer.start()

    def avvia(self, *, asincrono: bool = False) -> None:
        """Avvia il servizio: backup immediato + pianificazione ricorrente.

        Idempotente: se un backup è già in corso o pianificato, una seconda
        chiamata non avvia una seconda generazione (nessun backup in doppio).
        """
        with self._blocco:
            if self._attivo:
                return
            self._generazione += 1
            self._attivo = True
        if asincrono:
            self._worker = threading.Thread(target=self._esegui_e_ripiani,
                                            name="backup-iniziale", daemon=True)
            self._worker.start()
        else:
            self._esegui_e_ripiani()

    def ferma(self, timeout: float = 10.0) -> bool:
        """Ferma il servizio in modo deterministico.

        Nessun timer sopravvive alla chiamata; il backup in corso (se presente)
        è una chiamata singola e va a termine nel suo thread.
        ``timeout`` resta come parametro per compatibilità di interfaccia.
        """
        with self._blocco:
            self._generazione += 1
            self._attivo = False
            if self._timer is not None:
                self._timer.cancel()
                timer = self._timer
                self._timer = None
            else:
                timer = None
        for worker in (timer, self._worker):
            if worker is not None and worker is not threading.current_thread() and worker.is_alive():
                worker.join(timeout)
        return not self.in_corso
