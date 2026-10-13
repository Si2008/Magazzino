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
    percorso = Path(percorso_config) if percorso_config else PERCORSO_CONFIG_PREDEFINITO
    if percorso.is_file():
        with open(percorso, "rb") as file:
            dati = tomllib.load(file)
        sezione = dati.get("backup", {})
        cartella = str(sezione.get("cartella", cartella))
        dump = str(sezione.get("pg_dump", "pg_dump"))
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
) -> Path:
    """Esegue un backup del database e applica il limite di ``max_backup``.

    - ``comando_base`` è il prefisso del comando da eseguire (di default
      ``pg_dump``): utile nei test per sostituire l'eseguibile;
    - il file creato ha nome ``magazzino_profili_AAAAmmgg_HHMMSS.dump``;
    - dopo la creazione, i backup più vecchi oltre ``max_backup``
      vengono cancellati.

    Restituisce il percorso del file appena creato.
    """
    cartella_p = Path(cartella)
    cartella_p.mkdir(parents=True, exist_ok=True)

    ora = datetime.now()
    nome_file = f"{PREFISSO_FILE}{ora.strftime('%Y%m%d_%H%M%S')}{SUFFISSO_FILE}"
    file_output = cartella_p / nome_file

    comando = list(comando_base) + [
        "-h", host,
        "-p", str(porta),
        "-U", utente,
        "-d", dbname,
        "-Fc",
        "-f", str(file_output),
    ]

    ambiente = dict(os.environ)
    ambiente["PGPASSWORD"] = password

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

    rimuovi_backup_venuti(cartella_p, max_backup)
    return file_output


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

    def _esegui_e_ripiani(self) -> None:
        # Qualunque esito (anche un errore imprevisto) viene registrato e il
        # backup successivo resta pianificato: un errore non può fermare il piano.
        try:
            self.azione_backup()
        except BackupErrore as errore:
            logger.error("Backup automatico non riuscito: %s", errore)
        except Exception:
            logger.exception("Errore imprevisto durante il backup automatico")
        finally:
            self._pianifica_prossimo()

    def _pianifica_prossimo(self) -> None:
        with self._blocco:
            if not self._attivo:
                return
            self._timer = threading.Timer(
                self.intervallo_ore * 3600, self._esegui_e_ripiani
            )
            self._timer.daemon = True
            self._timer.start()

    def avvia(self) -> None:
        """Avvia il servizio: backup immediato + pianificazione ricorrente."""
        with self._blocco:
            self._attivo = True
        self._esegui_e_ripiani()

    def ferma(self) -> None:
        """Interrompe la pianificazione (il backup in corso va a termine)."""
        with self._blocco:
            self._attivo = False
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
