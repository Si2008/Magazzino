"""Fase 7 — importa_ods: associazione dell'immagine dal catalogo.

Il fixture ``F`` configura SQLite per la transazionalità (SAVEPOINT corretti).
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, select

from magazzino_profili.db import crea_session_factory
from magazzino_profili.domain import Base, Profilo
from magazzino_profili.reports import importa_ods_file
from magazzino_profili.reports import importa_ods as mod_ods

def png(colore="red"):
    from PIL import Image
    from io import BytesIO
    dati = BytesIO()
    Image.new("RGB", (8, 8), colore).save(dati, format="PNG")
    return dati.getvalue()



@pytest.fixture()
def F(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 't.db'}")

    @event.listens_for(engine, "connect")
    def _conn(dbapi, _):
        dbapi.isolation_level = None

    @event.listens_for(engine, "begin")
    def _b(conn):
        conn.exec_driver_sql("BEGIN")

    Base.metadata.create_all(engine)
    return crea_session_factory(engine)


@pytest.fixture(autouse=True)
def _reset_catalogo_modulo(monkeypatch):
    """Il catalogo è un singleton di modulo: lo si azzera tra i test."""
    monkeypatch.setattr(mod_ods, "_catalogo_instance", None, raising=False)


def _ods(path: Path, righe: list[list]) -> Path:
    def cella(v):
        if v == "":
            return "<table:table-cell/>"
        if isinstance(v, (int, float)):
            return (
                f'<table:table-cell office:value-type="float" office:value="{v}">'
                f"<text:p>{v}</text:p></table:table-cell>"
            )
        return (
            f'<table:table-cell office:value-type="string">'
            f"<text:p>{v}</text:p></table:table-cell>"
        )

    corpo = "".join(
        "<table:table-row>" + "".join(cella(v) for v in r) + "</table:table-row>" for r in righe
    )
    xml = (
        '<?xml version="1.0"?>'
        '<office:document-content '
        'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
        'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0">'
        "<office:body><office:spreadsheet>"
        f'<table:table table:name="Foglio1">{corpo}</table:table>'
        "</office:spreadsheet></office:body></office:document-content>"
    )
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("content.xml", xml)
    return path


H = ["Profilo", "Colore", "Vassoio", "Dimensione_mm", "Pezzi"]


def test_profilo_nuovo_riceve_immagine(F, tmp_path, catalogo_isolato):
    (catalogo_isolato / "zz99.png").write_bytes(png())
    p = _ods(tmp_path / "a.ods", [H, ["ZZ 99", "RAL7016", 1, 6000, 2]])
    st = importa_ods_file(F(), p, "t")
    assert st["importate"] == 1 and st["profili_creati"] == 1
    prof = F().scalar(select(Profilo).where(Profilo.codice == "ZZ99"))
    assert prof.immagine_sezione == str((catalogo_isolato / "zz99.png").resolve())


def test_profilo_esistente_non_riceve_immagine(F, catalogo_isolato, tmp_path):
    (catalogo_isolato / "zz99.png").write_bytes(png())
    s = F()
    from magazzino_profili.services.anagrafica import crea_profilo

    crea_profilo(s, "ZZ99", "Esistente", 1.0, 6000, "t", auto_immagine=False)
    s.close()

    p = _ods(tmp_path / "b.ods", [H, ["zz99", "RAL7016", 1, 6000, 2]])
    importa_ods_file(F(), p, "t")
    prof = F().scalar(select(Profilo).where(Profilo.codice == "ZZ99"))
    assert prof.immagine_sezione is None


def test_catalogo_assente_import_ok(F, catalogo_isolato, monkeypatch, tmp_path):
    monkeypatch.setenv("MAGAZZINO_CATALOGO_IMMAGINI", str(tmp_path / "non-esiste"))
    p = _ods(tmp_path / "a.ods", [H, ["ZZ 99", "RAL7016", 1, 6000, 2]])
    st = importa_ods_file(F(), p, "t")
    assert st["importate"] == 1
    prof = F().scalar(select(Profilo).where(Profilo.codice == "ZZ99"))
    assert prof.immagine_sezione is None


def test_png_invalido_import_ok_senza_immagine(F, catalogo_isolato, tmp_path):
    (catalogo_isolato / "zz99.png").write_text("testo, non un PNG")
    p = _ods(tmp_path / "a.ods", [H, ["ZZ 99", "RAL7016", 1, 6000, 2]])
    st = importa_ods_file(F(), p, "t")
    assert st["importate"] == 1
    prof = F().scalar(select(Profilo).where(Profilo.codice == "ZZ99"))
    assert prof.immagine_sezione is None
