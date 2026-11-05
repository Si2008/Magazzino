"""Fase 13/14 — la config accanto all'eseguibile PyInstaller (sys.frozen).

Simuliamo l'eseguibile impostando ``sys.frozen`` e ``sys.executable``
su una cartella di test: nessun processo congelato viene avviato.
"""

from __future__ import annotations

import sys
import textwrap

import pytest

from magazzino_profili.db import config as cfg

CONFIG = textwrap.dedent(
    """
    [database]
    host = "localhost"
    porta = 5432
    utente = "test"
    password = "password-di-test"
    dbname = "magazzino_test"
    """
).strip()


def test_candidati_includono_cartella_exe_solo_se_frozen(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "MagazzinoProfili.exe"))
    try:
        candidati = cfg._candidati_config(None)
        assert (tmp_path / "config.toml") in candidati
    finally:
        monkeypatch.delattr(sys, "frozen", raising=False)
    candidati = cfg._candidati_config(None)
    assert (tmp_path / "config.toml") not in candidati


def test_frozen_trova_la_config_accanto_all_exe(tmp_path, monkeypatch):
    cartella_exe = tmp_path / "cartella_exe"
    cartella_exe.mkdir()
    (cartella_exe / "config.toml").write_text(CONFIG, encoding="utf-8")
    cwd_altro = tmp_path / "cwd_senza_config"
    cwd_altro.mkdir()
    monkeypatch.chdir(cwd_altro)  # cwd senza config: serve il candidato exe
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(cartella_exe / "MagazzinoProfili.exe"))
    try:
        let = cfg.leggi_config()
        assert let.utente == "test" and let.password == "password-di-test"
        assert let.dbname == "magazzino_test"
    finally:
        monkeypatch.delattr(sys, "frozen", raising=False)
