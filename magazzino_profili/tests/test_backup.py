"""Test del backup: execution, retention and configuration."""

from decimal import Decimal  # noqa: F011 (not needed, removed below)

import re
import sys
from pathlib import Path

import pytest

from magazzino_profili import backup as pkg_backup

# Fake pg_dump: writes a file on the path passed after "-f".
FAKE_PG_DUMP = (
    "import sys,pathlib\n"
    "for i,a in enumerate(sys.argv):\n"
    "    if a == '-f':\n"
    "        pathlib.Path(sys.argv[i+1]).write_bytes(b'PGDUMP')\n"
)

# Name of the backup file: prefix + date/time + suffix.
NOME_BACKUP = re.compile(r"magazzino_profili_\d{8}_\d{6}(?:_\d{6}_[a-f0-9]{8})?\.dump")


def _fake_pgdump() -> list[str]:
    return [sys.executable, "-c", FAKE_PG_DUMP]


def test_backup_creates_the_file(tmp_path):
    """The backup must produce a file inside the folder."""
    out = pkg_backup.esegui_backup(
        "localhost",
        5432,
        "ut",
        "password",
        "db",
        tmp_path,
        7,
        _fake_pgdump(),
    )
    assert out.is_file()
    assert NOME_BACKUP.fullmatch(out.name)
    assert out.read_bytes() == b"PGDUMP"


def test_backup_error(tmp_path):
    """A failing command raises ``BackupErrore`` (not silently ignored)."""
    with pytest.raises(pkg_backup.BackupErrore):
        pkg_backup.esegui_backup(
            "localhost",
            5432,
            "ut",
            "password",
            "db",
            tmp_path,
            7,
            [sys.executable, "-c", "import sys; sys.exit(3)"],
        )


def test_retention(tmp_path):
    """Only the last ``max_backups`` backup must remain."""
    n = 5
    for i in range(n + 3):
        nome = tmp_path / f"magazzino_profili_202601{i}0_{i:06d}.dump"
        nome.write_bytes(b"x")

    for i in range(n + 3, n + 5):
        pkg_backup.esegui_backup(
            "localhost",
            5432,
            "ut",
            "password",
            "db",
            tmp_path,
            n,
            _fake_pgdump(),
        )

    remaining = [p for p in tmp_path.iterdir() if NOME_BACKUP.fullmatch(p.name)]
    assert len(remaining) == n


def test_retention_function(tmp_path):
    """The retention alone deletes the oldest backup."""
    for i in range(4):
        (tmp_path / f"magazzino_profili_202601{i}0_000000.dump").write_bytes(b"x")
    pkg_backup.rimuovi_backup_venuti(tmp_path, 2)
    remaining = sorted(p.name for p in tmp_path.iterdir() if NOME_BACKUP.fullmatch(p.name))
    assert remaining == ["magazzino_profili_20260120_000000.dump", "magazzino_profili_20260130_000000.dump"]


def test_config_reads_the_backup_section(tmp_path):
    """The parameters are read from the section ``[backup]``."""
    cfg = tmp_path / "config.toml"
    cfg.write_text('[backup]\ncartella = "bk"\nintervallo_ore = 12\nmax_backup = 3\n', encoding="utf-8")
    cfg_backup = pkg_backup.leggi_config_backup(cfg)
    assert Path(cfg_backup.cartella) == tmp_path / "bk"
    assert cfg_backup.intervallo_ore == 12
    assert cfg_backup.max_backup == 3


def test_config_validation(tmp_path):
    """A non-positive interval or number of backup is an error."""
    cfg = tmp_path / "config.toml"
    cfg.write_text('[backup]\nintervallo_ore = 0\nmax_backup = 3\n', encoding="utf-8")
    with pytest.raises(ValueError):
        pkg_backup.leggi_config_backup(cfg)


def test_planner_starts_and_stops(tmp_path):
    """The planner runs the backup at startup and stops on demand."""
    calls = []

    def azion():
        calls.append(1)

    planner = pkg_backup.PianificatoreBackup(999, azion)
    planner.avvia()
    assert len(calls) == 1
    planner.ferma()
    assert len(calls) == 1


def test_planner_swallows_backup_error(tmp_path):
    """A backup error must not crash the planner."""
    def azion():
        raise pkg_backup.BackupErrore("pg_dump missing")

    planner = pkg_backup.PianificatoreBackup(999, azion)
    planner.avvia()
    planner.ferma()
