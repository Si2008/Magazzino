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
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

NOME_FILE_DEFAULT = "config.toml"
# Radice del progetto: questo file è in magazzino_profili/db/config.py
_RADICE_PROGETTO = Path(__file__).resolve().parents[2]
# Segnaposto della password in config.example.toml: se l'utente l'ha
# copiato in config.toml senza cambiarla, va segnalato (solo un avviso).
PASSWORD_SEGNAPOSTO = "LA_TUA_PASSWORD"


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
    if os.environ.get("MAGAZZINO_CONFIG"):
        return [Path(os.environ["MAGAZZINO_CONFIG"]).expanduser()]
    candidati = [Path.cwd() / NOME_FILE_DEFAULT]
    if getattr(sys, "frozen", False):
        # Eseguibile PyInstaller: la config vive ACCANTO all'exe
        # (non è incorporata, perché contiene le credenziali).
        candidati.append(Path(sys.executable).parent / NOME_FILE_DEFAULT)
    candidati.append(_RADICE_PROGETTO / NOME_FILE_DEFAULT)
    return candidati


def trova_config(percorso: str | Path | None = None) -> Path | None:
    """Unica ricerca della configurazione per desktop, backup e server."""
    return next((p.resolve() for p in _candidati_config(Path(percorso) if percorso else None)
                 if p.is_file()), None)


def leggi_sezione(nome: str, percorso: str | Path | None = None) -> tuple[dict, Path]:
    file = trova_config(percorso)
    base = file.parent if file else (Path(sys.executable).parent if getattr(sys, "frozen", False)
                                     else _RADICE_PROGETTO)
    if file is None:
        return {}, base
    with file.open("rb") as fonte:
        sezione = tomllib.load(fonte).get(nome, {})
    if not isinstance(sezione, dict):
        raise ErroreConfigurazione(f"La sezione [{nome}] deve essere una tabella TOML")
    return sezione, base


def scrivi_url_pubblico(url: str):
    """Modifica soltanto l'URL web, preservando tutte le altre impostazioni."""
    import re
    import json
    from ..file_sicuri import destinazione_atomica, blocco_cartella
    from ..services.telefono import valida_url_pubblico
    url = valida_url_pubblico(url)
    file = trova_config()
    if file is None:
        raise ErroreConfigurazione("Configurazione del programma assente")
    with blocco_cartella(file.parent):
        righe = file.read_text(encoding="utf-8").splitlines(keepends=True)
        indice = next((i for i, riga in enumerate(righe) if riga.strip() == "[web]"), None)
        valore = "url_pubblico = " + json.dumps(url) + "\n"
        if indice is None:
            righe.extend(["\n[web]\n", valore])
        else:
            fine = next((i for i in range(indice + 1, len(righe)) if righe[i].lstrip().startswith("[")), len(righe))
            esistente = next((i for i in range(indice + 1, fine) if re.match(r"\s*url_pubblico\s*=", righe[i])), None)
            if esistente is None:
                righe.insert(indice + 1, valore)
            else:
                righe[esistente] = valore
        with destinazione_atomica(file) as tmp:
            tmp.write_text("".join(righe), encoding="utf-8")
    return url


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
    except (KeyError, TypeError, ValueError) as errore:
        raise ErroreConfigurazione(
            "La sezione [database] deve contenere le chiavi "
            "host, porta, utente, password, dbname"
        ) from errore

    # Avviso (non bloccante): la password è ancora quella di esempio.
    if not 1 <= configurazione.porta <= 65535 or not configurazione.host or not configurazione.dbname:
        raise ErroreConfigurazione("Host, nome database e porta 1..65535 sono obbligatori")
    if configurazione.password in (PASSWORD_SEGNAPOSTO, "1234"):
        print(
            "AVVISO: la password del database in config.toml è ancora il "
            "valore di esempio di config.example.toml. Imposta una password "
            "reale e diversa da quella di esempio."
        )
    return configurazione
