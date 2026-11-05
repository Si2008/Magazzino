"""Fase 13 completa — rotte del feed di aggiornamento (``/update/...``).

TestClient in-process: nessuna rete, nessun telefono, nessun database
(crea_app con session_factory finto e ``cartella_rilasci`` finta).
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from magazzino_profili.web.app import crea_app
from magazzino_profili.web.routes_update import NOME_INSTALLER, crea_router

SEGRETO = "segreto-di-test-molto-lungo-1234567890"


def _app(cartella):
    app = crea_app(
        session_factory=object(),  # le rotte del feed non usano il database
        durata_token_secondi=3600,
        segrete_token=SEGRETO,
        cartella_rilasci=cartella,
    )
    return TestClient(app)


def test_manifest_200_con_contenuto(tmp_path):
    (tmp_path / "manifest.json").write_text(
        json.dumps({"versione": "1.0.0"}), encoding="utf-8"
    )
    with _app(tmp_path) as c:
        r = c.get("/update/manifest.json")
        assert r.status_code == 200
        assert r.json() == {"versione": "1.0.0"}
        assert r.headers["content-type"].startswith("application/json")


def test_manifest_404_se_la_cartella_e_vuota(tmp_path):
    with _app(tmp_path) as c:
        r = c.get("/update/manifest.json")
    assert r.status_code == 404


def test_installer_200_nome_valido(tmp_path):
    nome = "MagazzinoProfili-1.0.0.exe"
    (tmp_path / nome).write_bytes(b"EXE")
    with _app(tmp_path) as c:
        r = c.get(f"/update/{nome}")
    assert r.status_code == 200 and r.content == b"EXE"


def test_installer_404_nome_non_valido(tmp_path):
    (tmp_path / "altro.exe").write_bytes(b"x")
    (tmp_path / "manifest.json").write_text("{}", encoding="utf-8")
    with _app(tmp_path) as c:
        for nome in ["altro.exe", "MagazzinoProfili-1.0.exe", "..%2Fmanifest.json", "x"]:
            assert c.get(f"/update/{nome}").status_code == 404


def test_anti_path_traversal(tmp_path):
    (tmp_path.parent / "segreto.exe").write_bytes(b"segreto")
    with _app(tmp_path) as c:
        assert c.get("/update/..%2Fsegreto.exe").status_code == 404
        assert c.get("/update/..%2F..%2Fsegreto.exe").status_code == 404
    assert (tmp_path.parent / "segreto.exe").exists()  # intatto, non servito


def test_senza_cartella_rilasci_le_rotte_non_esistono(tmp_path):
    with _app(None) as c:
        assert c.get("/update/manifest.json").status_code == 404
        assert c.get("/update/MagazzinoProfili-1.0.0.exe").status_code == 404


def test_regex_nome_installer():
    assert NOME_INSTALLER.fullmatch("MagazzinoProfili-1.0.0.exe")
    assert NOME_INSTALLER.fullmatch("MagazzinoProfili-10.20.30.exe")
    assert not NOME_INSTALLER.fullmatch("MagazzinoProfili-1.0.exe")
    assert not NOME_INSTALLER.fullmatch("MagazzinoProfili-1.0.0.EXE")
    assert not NOME_INSTALLER.fullmatch("../MagazzinoProfili-1.0.0.exe")


def test_router_standalone(tmp_path):
    router = crea_router(tmp_path)
    assert any("manifest.json" in str(r.path) for r in router.routes)
