"""Fase 7 — CatalogoImmagini: ricerca per codice normalizzato, indice, sicurezza."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from magazzino_profili.services import catalogo_immagini as mod  # noqa: E402
from magazzino_profili.services.catalogo_immagini import (  # noqa: E402
    CatalogoImmagini,
    cartella_catalogo,
    png_valido,
)

FIRMA = b"\x89PNG\r\n\x1a\n"


def _png(cartella: Path, nome: str, corpo: bytes = b"payload" * 10) -> Path:
    f = cartella / nome
    f.write_bytes(FIRMA + corpo)
    return f


# --------------------------------------------------------------------------
# trova()
# --------------------------------------------------------------------------
def test_trova_varie_grafie(catalogo_isolato: Path):
    f = _png(catalogo_isolato, "az2001.png")
    c = CatalogoImmagini(catalogo_isolato)
    assert c.trova("AZ 2001") == f
    assert c.trova("az2001") == f
    assert c.trova("AZ 2002") is None


def test_trova_grafia_con_trattino(catalogo_isolato: Path):
    # normalizza_codice conserva il trattino: la chiave è AZ-2001.
    f = _png(catalogo_isolato, "az-2001.png")
    c = CatalogoImmagini(catalogo_isolato)
    assert c.trova("az-2001") == f
    assert c.trova("az2001") is None  # chiave diversa: AZ2001


def test_trova_codice_con_slash_nessun_accesso_fuori(catalogo_isolato: Path):
    c = CatalogoImmagini(catalogo_isolato)
    assert c.trova("..\\..\\etc") is None
    assert c.trova("../../etc/passwd") is None
    assert c.trova("a/b") is None


def test_trova_ambiguita_ignorata(catalogo_isolato: Path):
    _png(catalogo_isolato, "AZ2001.png")
    _png(catalogo_isolato, "az 2001.png", b"altro" * 10)
    assert CatalogoImmagini(catalogo_isolato).trova("az 2001") is None


def test_trova_file_senza_firma_ignorato(catalogo_isolato: Path):
    (catalogo_isolato / "az2001.png").write_text("non sono un png")
    assert CatalogoImmagini(catalogo_isolato).trova("az2001") is None


def test_png_valido_rifiuta_firma_errata(catalogo_isolato: Path):
    f = catalogo_isolato / "x.png"
    f.write_bytes(b"XXXX\r\n\x1a\n" + b"dati")
    assert png_valido(f) is False
    assert png_valido(catalogo_isolato / "assente.png") is False


def test_indice_ricostruito_dopo_aggiunta(catalogo_isolato: Path):
    c = CatalogoImmagini(catalogo_isolato)
    assert c.trova("az2001") is None
    import time

    time.sleep(0.01)  # il mtime deve cambiare tra una stat e l'altra
    _png(catalogo_isolato, "az2001.png")
    assert c.trova("az2001") is not None


def test_indice_ricostruito_dopo_rimozione(catalogo_isolato: Path):
    f = _png(catalogo_isolato, "az2001.png")
    c = CatalogoImmagini(catalogo_isolato)
    assert c.trova("az2001") == f
    import time

    time.sleep(0.01)
    f.unlink()
    assert c.trova("az2001") is None


def test_file_con_prefisso_sottolineato_ignorado(catalogo_isolato: Path):
    _png(catalogo_isolato, "_atl150.png")
    assert CatalogoImmagini(catalogo_isolato).trova("atl150") is None


# --------------------------------------------------------------------------
# cartella_catalogo(): ordine delle fonti
# --------------------------------------------------------------------------
def test_ordine_variabile_config_default(tmp_path, monkeypatch):
    # 1) variabile d'ambiente prevale
    monkeypatch.delenv(mod.VARIABILE_AMBIENTE, raising=False)
    monkeypatch.setenv(mod.VARIABILE_AMBIENTE, str(tmp_path / "dalla_var"))
    assert cartella_catalogo() == tmp_path / "dalla_var"

    # 2) poi [immagini] catalogo in config.toml
    monkeypatch.delenv(mod.VARIABILE_AMBIENTE)
    config = tmp_path / "config.toml"
    config.write_text('[immagini]\ncatalogo = "catalogo_da_config"\n', encoding="utf-8")
    assert cartella_catalogo(tmp_path / "config.toml") == tmp_path / "catalogo_da_config"

    # 3) poi la cartella predefinita
    assert cartella_catalogo() == mod._base_programma() / "catalogo_immagini"


def test_percorso_relativo_rispetto_base_non_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # la CWD non deve contare
    monkeypatch.setenv(mod.VARIABILE_AMBIENTE, "rel_catalogo")
    assert cartella_catalogo() == mod._base_programma() / "rel_catalogo"


def test_config_malformato_default_senza_eccezioni(tmp_path, monkeypatch):
    monkeypatch.delenv(mod.VARIABILE_AMBIENTE, raising=False)
    config = tmp_path / "config.toml"
    config.write_text("[immagini\ncatalogo =", encoding="utf-8")  # TOML non valido
    assert mod._valore_da_config(config) is None  # nessuna eccezione
    assert cartella_catalogo(tmp_path / "config.toml") == mod._base_programma() / "catalogo_immagini"
    assert cartella_catalogo() == mod._base_programma() / "catalogo_immagini"


def test_config_con_chiave_mancante(tmp_path, monkeypatch):
    monkeypatch.delenv(mod.VARIABILE_AMBIENTE, raising=False)
    config = tmp_path / "config.toml"
    config.write_text("[database]\nhost = 'x'\n", encoding="utf-8")
    # file leggibile ma chiave assente → None (poi default in cartella_catalogo)
    assert mod._valore_da_config(config) is None
