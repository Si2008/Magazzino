"""Fase 10 — CSV legacy e ODS legacy: BOM, errori, atomicità, non-troncamento.

Il fixture ``F`` configura SQLite per la transazionalità (SAVEPOINT corretti):
non rimuoverlo, senza di esso ``test_atomico_rollback`` fallisce per un
limite del driver pysqlite, non per un bug.
"""

import csv
import zipfile

import pytest
from sqlalchemy import event, func, select

from magazzino_profili.db import crea_engine, crea_session_factory, crea_tabelle
from magazzino_profili.domain import Movimento, Pezzo
from magazzino_profili.reports import esporta_inventario_csv, importa_peczi_csv, importa_ods_file
from magazzino_profili.reports.export_csv import INTESTAZIONI
from magazzino_profili.services import carica
from magazzino_profili.services.anagrafica import crea_profilo


@pytest.fixture()
def F(tmp_path):
    eng = crea_engine(url=f"sqlite:///{tmp_path / 't.db'}")

    @event.listens_for(eng, "connect")
    def _conn(dbapi, _):
        dbapi.isolation_level = None

    @event.listens_for(eng, "begin")
    def _b(conn):
        conn.exec_driver_sql("BEGIN")

    crea_tabelle(eng)
    f = crea_session_factory(eng)
    s = f()
    crea_profilo(s, "AB12", "Profilo AB12", 1.0, 6000, "t")
    s.close()
    return f


def _csv(path, righe, bom=False):
    testo = ";".join(INTESTAZIONI) + "\n" + "\n".join(righe) + "\n"
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + testo.encode("utf-8"))
    return path


def _conta(F):
    with F() as s:
        return (
            s.scalar(select(func.count()).select_from(Pezzo)),
            s.scalar(select(func.count()).select_from(Movimento)),
        )


def test_bom(F, tmp_path):
    p = _csv(tmp_path / "b.csv", ["AB12;Perché è;RAL 7016;6000;2;A1;x"], bom=True)
    assert importa_peczi_csv(F(), p, "t") == 1
    with F() as s:
        assert s.scalar(select(Pezzo.quantita)) == 2


def test_colore_vuoto_e_errore(F, tmp_path):
    p = _csv(tmp_path / "c.csv", ["AB12;x;;6000;2;;", "AB12;x;RAL 7016;6000;1;;"])
    with pytest.raises(ValueError, match="riga 2: colore mancante"):
        importa_peczi_csv(F(), p)
    assert _conta(F) == (0, 0)


def test_riga_vuota_ignorata_e_errori_multipli(F, tmp_path):
    p = _csv(tmp_path / "m.csv", [";;;;;;", "AB12;x;RAL 7016;0;2;;", "AB12;x;RAL 7016;6000;1_0;;"])
    with pytest.raises(ValueError) as e:
        importa_peczi_csv(F(), p)
    assert "riga 3" in str(e.value) and "riga 4" in str(e.value) and "riga 2" not in str(e.value)
    assert _conta(F) == (0, 0)


def test_atomico_rollback(F, tmp_path):
    p = _csv(
        tmp_path / "a.csv",
        ["AB12;x;RAL 7016;6000;1;;", "AB12;x;RAL 7016;3000;99999999999999999999999;;"],
    )
    with pytest.raises(RuntimeError, match="riga 3.*Nessuna riga è stata salvata"):
        importa_peczi_csv(F(), p, "t")
    assert _conta(F) == (0, 0)
    s = F()
    carica(s, "AB12", "RAL7016", 6000, 1, "t", "dopo")  # la sessione resta utilizzabile
    s.close()
    assert _conta(F) == (1, 1)


def test_duplicati_si_sommano_e_doppio_import(F, tmp_path):
    p = _csv(tmp_path / "d.csv", ["AB12;x;RAL 7016;6000;2;;AAA", "AB12;x;ral7016;6000;3;;BBB"])
    assert importa_peczi_csv(F(), p, "t") == 2
    assert _conta(F) == (1, 2)
    importa_peczi_csv(F(), p, "t")
    with F() as s:
        assert s.scalar(select(Pezzo.quantita)) == 10


def test_carica_invariata(F):
    s = F()
    p = carica(s, "ab 12", "ral 7016", 6000, 5, "t", "c", "Scaffale A")
    s.close()
    assert p.quantita == 5 and p.barcode == "AB12-RAL7016-6000"


def test_colonne_mancanti(F, tmp_path):
    (tmp_path / "x.csv").write_text(
        "Codice profil;Colore\nAB12;RAL 7016\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="Intestazione CSV mancante"):
        importa_peczi_csv(F(), tmp_path / "x.csv")
    assert _conta(F) == (0, 0)


def test_solo_intestazione(F, tmp_path):
    (tmp_path / "h.csv").write_text(";".join(INTESTAZIONI) + "\n", encoding="utf-8")
    assert importa_peczi_csv(F(), tmp_path / "h.csv", "t") == 0
    assert _conta(F) == (0, 0)


def test_file_vuoto_zero_byte(F, tmp_path):
    p = tmp_path / "v.csv"
    p.write_bytes(b"")
    with pytest.raises(ValueError, match="Intestazione del CSV vuota"):
        importa_peczi_csv(F(), p)
    assert _conta(F) == (0, 0)


# ------------------------------------------------------------- ODS legacy


def _ods(path, righe):
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


H = ["Profilo", "Colore", "Vassoio", "Dimensione_mm", "Pezzi"]


def test_ods_non_tronca(F, tmp_path):
    _ods(tmp_path / "a.ods", [H, ["AB12", "RAL7016", 4, 6000, 3.7], ["AB12", "RAL7016", 4, 3000, 2]])
    st = importa_ods_file(F(), tmp_path / "a.ods", "t")
    assert st["importate"] == 1 and st["saltate"] == 1
    with F() as s:
        assert s.scalar(select(Pezzo.quantita)) == 2


def test_ods_float_formattata(F, tmp_path):
    p = tmp_path / "f.ods"
    _ods(p, [H, ["AB12", "RAL7016", 4, 6000, 2]])
    x = zipfile.ZipFile(p).read("content.xml").decode()
    x = x.replace('office:value="2"><text:p>2<', 'office:value="2"><text:p>2,00<')
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("content.xml", x)
    assert importa_ods_file(F(), p, "t")["importate"] == 1


def test_ods_roundtrip_ubicazione_vassoio(F, tmp_path):
    """Una riga con vassoio numerico crea l'ubicazione 'Vassoio N' (comportamento legacy)."""
    _ods(tmp_path / "v.ods", [H, ["AB12", "RAL7016", 7, 6000, 3]])
    assert importa_ods_file(F(), tmp_path / "v.ods", "t")["importate"] == 1
    with F() as s:
        assert s.scalar(select(Pezzo.ubicazione)) == "Vassoio 7"
