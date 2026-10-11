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
from magazzino_profili.sicurezza import crea_utente, Ruolo
from magazzino_profili.sicurezza.utenti import Utente

PG_NAME = "magazzino_profili"
PG_USER = "postgres"
PG_PORT = 5432


def _random_password(length: int) -> str:
    return "".join(secrets.choice(ascii_letters + digits) for _ in range(length))


def _password_file() -> str:
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
    subprocess.run(
        [
            _exe("initdb"),
            "-D",
            str(CARTELLA_DATA),
            "-U",
            PG_USER,
            "--auth=md5",
            "--auth-host=md5",
            "--auth-local=md5",
            "--pwfile=" + str(pwfile),
        ],
        check=True,
    )
    print("data folder created")


def _ensure_db(password: str) -> None:
    url = "postgresql+psycopg://" + PG_USER + ":" + password + f"@localhost:{PG_PORT}/{PG_NAME}"
    try:
        create_engine(url).connect().close()
        print("database exists")
        return
    except OperationalError:
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


def _write_config(password: str) -> None:
    with open("config.toml", encoding="utf-8") as file:
        content = file.read()
    content = re.sub(r'host = "[^"]+"', 'host = "localhost"', content)
    content = re.sub(r"porta = \d+", f"porta = {PG_PORT}", content)
    content = re.sub(r'utente = "[^"]+"', f'utente = "{PG_USER}"', content)
    content = re.sub(r'password = "[^"]+"', f'password = "{password}"', content)
    content = re.sub(r'dbname = "[^"]+"', f'dbname = "{PG_NAME}"', content)
    if "pg_dump" not in content:
        riga = "pg_dump = '" + _exe("pg_dump") + "'"
        content = content.rstrip() + chr(10) + riga + chr(10)
    with open("config.toml", "w", encoding="utf-8") as file:
        file.write(content)
    print("config.toml updated")


def _first_user() -> None:
    config = leggi_config()
    engine = crea_engine(config=config)
    crea_tabelle(engine)
    applica_migrazioni(engine)
    factory = crea_session_factory(engine)

    with factory() as session:
        if session.scalar(select(Utente)):
            print("users already exist")
            return

    name = "amministratore"
    password = _random_password(12)
    with factory() as session:
        crea_utente(session, name, password, Ruolo.AMMINISTRATORE)
    print("first user created: " + name + " / " + password + "  (save it!)")


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
    if "--no-user" not in sys.argv:
        _first_user()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
