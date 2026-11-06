"""Setup of the PostgreSQL server used by Magazzino Profili.

Idempotent: it copies the PostgreSQL binaries in a stable folder, it creates
the data folder and the database, it writes config.toml with the parameters
found, and (if needed) it creates the first user AMMINISTRATORE.

It works without administrator rights: everything lives in the user folder
(``%LOCALAPPDATA%/magazzino_profili``).

Usage::

    python setup_database.py              # init + start + config + first user
    python setup_database.py --no-user    # without creating the first user
"""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import subprocess
import sys
from string import ascii_letters, digits

from sqlalchemy import create_engine, select
from sqlalchemy.exc import OperationalError

from magazzino_profili.db import (
    crea_engine,
    crea_session_factory,
    crea_tabelle,
    leggi_config,
)
from magazzino_profili.db.migrazioni import applica_migrazioni
from magazzino_profili.db.server import CARTELLA_DATA, CARTELLA_PGSQL, ensure_running

PG_NAME = "magazzino_profili"
PG_USER = "postgres"
PG_PORT = 5432


def _random_password(length: int) -> str:
    return "".join(secrets.choice(ascii_letters + digits) for _ in range(length))


def _password_file() -> str:
    if CARTELLA_DATA.is_dir():
        # Non generare nuove credenziali per un cluster già inizializzato.
        return leggi_config().password
    file = CARTELLA_DATA.parent / "pg_pass"
    if file.is_file():
        return file.read_text(encoding="utf-8").strip()
    value = _random_password(16)
    file.write_text(value, encoding="utf-8")
    return value


def _copy_bin() -> None:
    if (CARTELLA_PGSQL / "bin" / "pg_isready.exe").is_file():
        print("binaries already in place")
        return
    import postgresql_binaries

    bin_dir = postgresql_binaries.bin()
    shutil.copytree(bin_dir.parent, CARTELLA_PGSQL, dirs_exist_ok=True)
    print("binaries copied in", CARTELLA_PGSQL)


def _exe(name: str) -> str:
    return str(CARTELLA_PGSQL / "bin" / (name + ".exe"))


def _initdb(password: str) -> None:
    if CARTELLA_DATA.is_dir():
        print("data folder already exists")
        return
    CARTELLA_DATA.mkdir(parents=True)
    pwfile = CARTELLA_DATA.parent / "pg_pass"
    pwfile.write_text(password, encoding="utf-8")
    try:
        subprocess.run(
            [
                _exe("initdb"),
                "-D",
                str(CARTELLA_DATA),
                "-U",
                PG_USER,
                "--auth=scram-sha-256",
                "--pwfile=" + str(pwfile),
            ],
            check=True,
        )
    finally:
        pwfile.unlink(missing_ok=True)  # la password in chiaro non deve restare su disco
    print("data folder created")


def _ensure_db(password: str) -> None:
    url = "postgresql+psycopg://" + PG_USER + ":" + password + f"@localhost:{PG_PORT}/{PG_NAME}"
    try:
        create_engine(url).connect().close()
        print("database exists")
        return
    except OperationalError as errore:
        originale = getattr(errore, "orig", None)
        if getattr(originale, "sqlstate", None) != "3D000":
            raise RuntimeError("PostgreSQL non accessibile: verificare credenziali e server; "
                               "nessun database è stato creato o modificato") from errore
        print("database missing: creating it")
    env = {**os.environ, "PGPASSWORD": password}
    subprocess.run(
        [
            _exe("createdb"),
            "-h",
            "localhost",
            "-p",
            str(PG_PORT),
            "-U",
            PG_USER,
            PG_NAME,
        ],
        check=True,
        env=env,
    )
    print("database created")


def _imposta_chiavi(testo: str, sezione: str, valori: dict[str, str], sovrascrivi: bool = True) -> str:
    """Imposta chiavi TOML solo dentro la sezione indicata.

    ``valori`` contiene già la forma TOML (es. ``'"localhost"'``, ``'5432'``).
    Le altre sezioni non vengono toccate. Le chiavi mancanti vengono
    inserite subito dopo l'intestazione della sezione (creata se assente).
    Con ``sovrascrivi=False`` una chiave già presente resta invariata.
    """
    nl = "\n"
    fuori: list[str] = []
    trovate: set[str] = set()
    dentro = False
    intestazione_idx: int | None = None
    for riga in testo.splitlines(keepends=True):
        stripped = riga.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            dentro = stripped == f"[{sezione}]"
            if dentro:
                intestazione_idx = len(fuori)
            fuori.append(riga)
            continue
        if dentro:
            corrispondenza = re.match(r"^(\s*)([A-Za-z_]\w*)\s*=", riga)
            if corrispondenza and corrispondenza.group(2) in valori:
                chiave = corrispondenza.group(2)
                trovate.add(chiave)
                if sovrascrivi:
                    fuori.append(f"{corrispondenza.group(1)}{chiave} = {valori[chiave]}{nl}")
                else:
                    fuori.append(riga)
                continue
        fuori.append(riga)
    mancanti = [k for k in valori if k not in trovate]
    if mancanti:
        if intestazione_idx is None:
            fuori.append(f"{nl}[{sezione}]{nl}")
            intestazione_idx = len(fuori) - 1
        fuori[intestazione_idx + 1:intestazione_idx + 1] = [f"{k} = {valori[k]}{nl}" for k in mancanti]
    return "".join(fuori)


def _write_config(password: str) -> None:
    with open("config.toml", encoding="utf-8") as file:
        content = file.read()
    content = _imposta_chiavi(content, "database", {
        "host": json.dumps("localhost"),
        "porta": str(PG_PORT),
        "utente": json.dumps(PG_USER),
        "password": json.dumps(password),
        "dbname": json.dumps(PG_NAME),
    })
    content = _imposta_chiavi(
        content, "backup", {"pg_dump": json.dumps(_exe("pg_dump"))}, sovrascrivi=False
    )
    with open("config.toml", "w", encoding="utf-8") as file:
        file.write(content)
    print("config.toml updated")


def _prepara_schema():
    config = leggi_config()
    engine = crea_engine(config=config)
    try:
        from magazzino_profili.main import _backup_prima_migrazioni
        _backup_prima_migrazioni(engine, config)
        crea_tabelle(engine)
        applica_migrazioni(engine)
    finally:
        engine.dispose()


def main() -> int:
    password = _password_file()
    _copy_bin()
    _initdb(password)
    if not ensure_running():
        print("ERRORE: the server did not start, check the log in", CARTELLA_DATA)
        return 1
    print("server ready")
    _ensure_db(password)
    _write_config(password)
    _prepara_schema()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
