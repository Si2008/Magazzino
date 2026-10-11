"""Server PostgreSQL local used by the application.

The server is not bundled inside the executable: it lives in a folder of
the user (no administrator rights are required). The binaries are looked
for in:

1. ``%LOCALAPPDATA%/magazzino_profili/pgsql/bin`` (folder created by
   ``setup_database.py``);
2. the ``postgresql_binaries`` pip package (if installed).

Usage::

    from magazzino_profili.db import server

    if not server.is_ready(host="localhost", porta=5432):
        server.start(host="localhost", porta=5432)
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

# Cartella of the database (user folder: no administrator rights needed).
CARTELLA_DATA = Path.home() / "AppData" / "Local" / "magazzino_profili" / "pg_data"
# Folder where setup_database.py copies the PostgreSQL binaries.
CARTELLA_PGSQL = Path.home() / "AppData" / "Local" / "magazzino_profili" / "pgsql"
# Timeout of the start (seconds).
TIMEOUT_START = 30


def _cartella_bin() -> str | None:
    """Cartella with the PostgreSQL executables, ``None`` if not found."""
    cartella = CARTELLA_PGSQL / "bin"
    if (cartella / "pg_isready.exe").is_file():
        return str(cartella)
    try:
        import postgresql_binaries

        return str(postgresql_binaries.bin())
    except Exception:
        return None


def _commanda(cartella_bin: str, name: str) -> str:
    """Full path of a PostgreSQL executable."""
    return str(Path(cartella_bin) / f"{name}.exe")


def is_ready(host: str = "localhost", porta: int = 5432) -> bool:
    """``True`` if a PostgreSQL server answers on the port."""
    cartella_bin = _cartella_bin()
    if not cartella_bin:
        return False
    try:
        result = subprocess.run(
            [_commanda(cartella_bin, "pg_isready"), "-h", host, "-p", str(porta)],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def start(host: str = "localhost", porta: int = 5432) -> bool:
    """Start the server (if needed) and wait until it answers.

    The server is started detached, with its output redirected in a log
    file inside the data folder: this way the child processes created by
    the postmaster keep valid handles.
    """
    if is_ready(host, porta):
        return True

    cartella_bin = _cartella_bin()
    if not cartella_bin or not CARTELLA_DATA.is_dir():
        return False

    log_file = (CARTELLA_DATA / "log_app").open("ab")  # noqa: SIM115
    try:
        subprocess.Popen(  # noqa: SIM511
            [_commanda(cartella_bin, "postgres.exe"), "-D", str(CARTELLA_DATA)],
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            cwd=str(CARTELLA_DATA),
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
    except OSError:
        return False

    for _ in range(TIMEOUT_START):
        time.sleep(1)
        if is_ready(host, porta):
            return True
    return False


def ensure_running(host: str = "localhost", porta: int = 5432) -> bool:
    """Best effort: ``True`` when the server is reachable."""
    return is_ready(host, porta) or start(host, porta)
