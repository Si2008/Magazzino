"""Lettura della configurazione del database da ``config.toml``.

Il file può stare:
1. nel percorso esplicito passato a :func:`leggi_config`;
2. nell'attuale directory di lavoro (``config.toml``);
3. (solo eseguibile PyInstaller) accanto all'eseguibile stesso;
4. alla radice del progetto (due livelli sopra questo file).

Formato atteso::

    [database]
    host = "localhost"
    porta = 5432
    nome = "magazzino_profili"
    utente = "LA_TUA_UTENZA"
    password = "LA_TUA_PASSWORD"
    dbname = "magazzino_profili"
"""

from __future__ import annotations

import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

NOME_FILE_DEFAULT = "config.toml"
# Radice del progetto: questo file è in magazzino_profili/db/config.py
_RADICE_PROGETTO = Path(__file__).resolve().parents[2]
# Segnaposto della password in config.example.toml: se l'utente l'ha
# copiato in config.toml senza cambiarla, va segnalato (solo un avviso).
PASSWORD_SEGNAPOSTO = 1234


class ErroreConfigurazione(Exception):
    """Configurazione del database assente o incompleta."""


@dataclass(frozen=True)
class ConfigurazioneDatabase:
    """Parametri di connessione a PostgreSQL (driver psycopg v3)."""

    host: str
    porta: int
    utente: str
    password: str
    dbname: str

    @property
    def database_url(self) -> str:
        """URL SQLAlchemy completo: ``postgresql+psycopg://...``."""
        return (
            f"postgresql+psycopg://{quote(self.utente, safe='')}"
            f":{quote(self.password, safe='')}@{self.host}:{self.porta}/{self.dbname}"
        )


def _candidati_config(percorso: Path | None) -> list[Path]:
    if percorso is not None:
        return [Path(percorso)]
    candidati = [Path.cwd() / NOME_FILE_DEFAULT]
    if getattr(sys, "frozen", False):
        # Eseguibile PyInstaller: la config vive ACCANTO all'exe
        # (non è incorporata, perché contiene le credenziali).
        candidati.append(Path(sys.executable).parent / NOME_FILE_DEFAULT)
    candidati.append(_RADICE_PROGETTO / NOME_FILE_DEFAULT)
    return candidati


def leggi_config(percorso: str | Path | None = None) -> ConfigurazioneDatabase:
    """Carica ``config.toml`` e restituisce i parametri di connessione.

    Solleva :class:`ErroreConfigurazione` se il file non esiste o se
    mancano chiavi della sezione ``[database]``.
    """
    candidati = _candidati_config(percorso)
    percorso_file = next((p for p in candidati if p.is_file()), None)
    if percorso_file is None:
        cercati = ", ".join(str(p) for p in candidati)
        raise ErroreConfigurazione(
            f"File di configurazione non trovato. Percorsi cercati: {cercati}"
        )

    with open(percorso_file, "rb") as file:
        dati = tomllib.load(file)

    try:
        sezione = dati["database"]
        configurazione = ConfigurazioneDatabase(
            host=str(sezione["host"]),
            porta=int(sezione["porta"]),
            utente=str(sezione["utente"]),
            password=str(sezione["password"]),
            dbname=str(sezione["dbname"]),
        )
    except (KeyError, TypeError) as errore:
        raise ErroreConfigurazione(
            "La sezione [database] deve contenere le chiavi "
            "host, porta, utente, password, dbname"
        ) from errore

    # Avviso (non bloccante): la password è ancora quella di esempio.
    if configurazione.password == PASSWORD_SEGNAPOSTO:
        print(
            "AVVISO: la password del database in config.toml è ancora il "
            "valore di esempio di config.example.toml. Imposta una password "
            "reale e diversa da quella di esempio."
        )
    return configurazione
