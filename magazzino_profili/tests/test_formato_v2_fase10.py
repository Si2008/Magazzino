"""Fase 10 — Formato V2: esportazione e validazione CSV e ODS (separati).

I valori usati sono quelli REALI del modello (Fasi 7-8):
- stati: ``Caricato`` / ``Scaricato`` (vincolo ``stato_valido``);
- ``numero_vassoio``: testo libero.
"""

import csv
import time
import zipfile
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from magazzino_profili.db import crea_engine, crea_session_factory, crea_tabelle
from magazzino_profili.domain import Pezzo, Profilo
from magazzino_profili.reports import formato_v2 as f2
from magazzino_profili.reports import ods_v2
from magazzino_profili.services import carica
from magazzino_profili.services.anagrafica import crea_profilo


@pytest.fixture()
def F(tmp_path):
    eng = crea_engine(url=f"sqlite:///{tmp_path / 't.db'}")
    crea_tabelle(eng)
    f = crea_session_factory(eng)
    s = f()
    crea_profilo(s, "AB12", 'Profilo  "è"; AB12\ncon a capo', 1.0, 6000, "t")
    carica(s, "AB12", "RAL 7016", 6000, 5, "t", "c", "Scaffale; A")
    carica(s, "AB12", "RAL 7016", 3000, 2, "t", "c")
    s.close()
    return f


def _valori(r):
    return [
        (
            x.id_pezzo, x.codice_profilo, x.descrizione, x.colore, x.lunghezza_mm,
            x.quantita, x.ubicazione, x.barcode,
        )
        for x in r.righe
    ]


@pytest.mark.parametrize("fmt", ["csv", "ods"])
def test_roundtrip(F, tmp_path, fmt):
    with F() as s:
        if fmt == "csv":
            out = f2.esporta_inventario_csv_v2(s, tmp_path / "i.csv")
            r = f2.valida_csv_v2(out)
        else:
            out = ods_v2.esporta_inventario_ods_v2(s, tmp_path / "i.ods")
            r = ods_v2.valida_ods_v2(out)
        assert r.valido, r.errori
        attesi = f2.righe_v2_da_db(s)
    assert len(r.righe) == 2 == len(attesi)
    assert r.righe[0].descrizione == ('Profilo  "è"; AB12\ncon a capo' if fmt == "csv" else "")
    assert r.righe[0].ubicazione == "Scaffale; A" and r.righe[1].ubicazione is None
    assert [x.id_pezzo for x in r.righe] == sorted(x.id_pezzo for x in r.righe)


def test_ods_reale(F, tmp_path):
    with F() as s:
        out = ods_v2.esporta_inventario_ods_v2(s, tmp_path / "i.ods")
    z = zipfile.ZipFile(out)
    i = z.infolist()[0]
    assert i.filename == "mimetype" and i.compress_type == 0
    assert z.read("mimetype") == b"application/vnd.oasis.opendocument.spreadsheet"
    righe = ods_v2.leggi_righe_ods(out)
    assert tuple(righe[0]) == f2.INTESTAZIONI_V2 and len(righe) == 3


def test_timestamp_e_bom(F, tmp_path):
    assert f2._iso_utc(datetime(2026, 10, 20, 10, 0, tzinfo=timezone(timedelta(hours=2)))) == "2026-10-20T08:00:00+00:00"
    assert f2._iso_utc(datetime(2026, 10, 20, 8, 0)) == "2026-10-20T08:00:00+00:00"  # naive (SQLite) = UTC
    assert f2._iso_utc(None) == ""
    with F() as s:
        out = f2.esporta_inventario_csv_v2(s, tmp_path / "i.csv")
    (tmp_path / "b.csv").write_bytes(out.read_text(encoding="utf-8-sig").encode("utf-8-sig"))
    assert f2.valida_csv_v2(tmp_path / "b.csv").valido is True


def _h(*righe):
    return [list(f2.INTESTAZIONI_V2), *righe]


OK = ["2", "1", "AB12", "d", "RAL7016", "6000", "3", "", "4", "AB12-RAL7016-6000", "Caricato", "", "", "1", "0"]


def mod(**k):
    r = list(OK)
    for nome, v in k.items():
        r[f2.INTESTAZIONI_V2.index(nome.replace("_", " "))] = v
    return r


@pytest.mark.parametrize(
    "riga,frag",
    [
        (mod(Versione_formato="1"), "deve essere 2"),
        (mod(ID_pezzo="0"), "almeno 1"),
        (mod(ID_pezzo="x"), "non è un intero"),
        (mod(Quantita="-1"), "non è un intero"),
        (mod(**{"Lunghezza_(mm)": "0"}), "almeno 1"),
        (mod(Barcode=""), "mancante"),
        (mod(Stato_barcode="BOH"), "non valido"),
        (mod(**{"Eliminato_il_UTC": "2026-10-20T10:00:00"}), "fuso"),
        (mod(**{"Eliminato_il_UTC": "ieri"}), "ISO"),
        (OK[:-1], "colonne"),
        (mod(Scorta_minima="x"), "non è un intero"),
    ],
)
def test_errori(riga, frag):
    r = f2.valida_righe_v2(_h(riga))
    assert not r.valido and frag in str(r.errori[0]), r.errori


def test_vassoio_e_stato_validi():
    """``numero_vassoio`` è testo libero; gli stati ammessi sono Caricato/Scaricato."""
    r = f2.valida_righe_v2(_h(mod(Numero_vassoio="Vassoio 12/B")))
    assert r.valido and r.righe[0].numero_vassoio == "Vassoio 12/B"
    assert f2.valida_righe_v2(_h(mod(Stato_barcode="Scaricato"))).valido
    assert not f2.valida_righe_v2(_h(mod(Stato_barcode="Scaduto"))).valido


def test_duplicati_header_vuoto():
    r = f2.valida_righe_v2(_h(OK, OK))
    assert len(r.errori) == 2  # ID e barcode duplicati
    assert not f2.valida_righe_v2([]).valido
    assert not f2.valida_righe_v2([list(reversed(f2.INTESTAZIONI_V2))]).valido
    assert f2.valida_righe_v2(_h([""] * 14, OK)).valido


def test_malformati(tmp_path):
    (tmp_path / "v.csv").write_bytes(b"")
    assert not f2.valida_csv_v2(tmp_path / "v.csv").valido
    (tmp_path / "l.csv").write_bytes("\xe8;a".encode("latin-1"))
    assert "UTF-8" in str(f2.valida_csv_v2(tmp_path / "l.csv").errori[0])
    (tmp_path / "q.csv").write_text(";".join(f2.INTESTAZIONI_V2) + '\n2;"aperta\n', encoding="utf-8")
    assert not f2.valida_csv_v2(tmp_path / "q.csv").valido
    (tmp_path / "x.ods").write_bytes(b"non e' uno zip")
    assert "non valido" in str(ods_v2.valida_ods_v2(tmp_path / "x.ods").errori[0])


def test_riferimenti(F):
    r = f2.valida_righe_v2(_h(mod(Codice_profilo="ZZ99")))
    with F() as s:
        assert "non in anagrafica" in str(f2.verifica_riferimenti_v2(s, r)[0])


def test_piezzo_completo_e_eliminato(F, tmp_path):
    """Vassoio, stato, timestamp e scorta valorizzati + pezzo eliminato presente nell'export."""
    utc = timezone.utc
    con = datetime(2026, 10, 20, 8, 0, tzinfo=utc)
    elim = datetime(2026, 10, 21, 9, 30, tzinfo=utc)
    with F() as s:
        pezzo = s.scalars(select(Pezzo).order_by(Pezzo.id)).first()
        pezzo.numero_vassoio = "Vassoio 4"
        pezzo.stato = "Scaricato"
        pezzo.data_ultimo_cambio_stato = con
        pezzo.eliminato_il = elim
        pezzo.scorta_minima = 5
        s.commit()

    for fmt in ("csv", "ods"):
        out = tmp_path / ("c.csv" if fmt == "csv" else "c.ods")
        with F() as s:
            if fmt == "csv":
                out = f2.esporta_inventario_csv_v2(s, out)
                r = f2.valida_csv_v2(out)
            else:
                out = ods_v2.esporta_inventario_ods_v2(s, out)
                r = ods_v2.valida_ods_v2(out)
        assert r.valido, r.errori
        assert len(r.righe) == 2
        prima = r.righe[0]
        assert prima.numero_vassoio == "Vassoio 4"
        assert prima.stato_barcode == "Scaricato"
        assert prima.stato_cambiato_il == con
        assert prima.eliminato_il == elim
        assert prima.scorta_minima == 5
        assert r.righe[1].numero_vassoio is None and r.righe[1].stato_barcode == "Caricato"


def test_2000_righe(F, tmp_path):
    """Un numero significativo di righe: conteggio esatto e tempi ragionevoli."""
    with F() as s:
        # 2000 combinazioni extra (una lunghezza diversa per riga).
        for i in range(2000):
            carica(s, "AB12", "RAL 7016", 1000 + i, 1, "t", "bulk")
        assert s.scalar(select(Pezzo).limit(1)) is not None
    n = 2002
    t0 = time.monotonic()
    for fmt, out_name in (("csv", "n.csv"), ("ods", "n.ods")):
        with F() as s:
            if fmt == "csv":
                out = f2.esporta_inventario_csv_v2(s, tmp_path / out_name)
                r = f2.valida_csv_v2(out)
            else:
                out = ods_v2.esporta_inventario_ods_v2(s, tmp_path / out_name)
                r = ods_v2.valida_ods_v2(out)
        assert r.valido, r.errori
        assert len(r.righe) == n
    assert time.monotonic() - t0 < 60


def _ods_minimo(path, righe_xml):
    xml = (
        '<?xml version="1.0"?>'
        '<office:document-content '
        'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
        'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0">'
        "<office:body><office:spreadsheet>"
        f'<table:table table:name="Inventario">{righe_xml}</table:table>'
        "</office:spreadsheet></office:body></office:document-content>"
    )
    manifest = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">'
        '<manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.spreadsheet"/>'
        '<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>'
        '<manifest:file-entry manifest:full-path="meta.xml" manifest:media-type="text/xml"/>'
        "</manifest:manifest>"
    )
    meta = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<office:document-meta xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" office:version="1.2">'
        "<office:meta/>"
        "</office:document-meta>"
    )
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/vnd.oasis.opendocument.spreadsheet")
        z.writestr("META-INF/manifest.xml", manifest)
        z.writestr("meta.xml", meta)
        z.writestr("content.xml", xml)


def test_ods_celle_ripetute_libreoffice(tmp_path):
    """Celle ripetute (LibreOffice) e riga finale ripetuta 1048576 volte: ignorate."""
    header = f2.INTESTAZIONI_V2

    def cell(v):
        return f'<table:table-cell office:value-type="string"><text:p>{v}</text:p></table:table-cell>'

    # Riga dati: 3 valori reali + una cella ripetuta che copre le altre 11 colonne.
    riga = (
        "".join(cell(v) for v in ("2", "7", "AB12"))
        + '<table:table-cell/>'  # Descrizione vuota
        + '<table:table-cell table:number-columns-repeated="10"/>'
    )
    corpo = (
        "<table:table-row>" + "".join(cell(h) for h in header) + "</table:table-row>"
        f"<table:table-row>{riga}</table:table-row>"
        # Riga vuota ripetuta da LibreOffice alla fine del foglio.
        '<table:table-row table:number-rows-repeated="1048576">'
        '<table:table-cell table:number-columns-repeated="16384"/>'
        "</table:table-row>"
    )
    p = tmp_path / "rip.ods"
    _ods_minimo(p, corpo)
    righe = ods_v2.leggi_righe_ods(p)
    assert len(righe) == 2
    assert righe[1][:3] == ["2", "7", "AB12"]
    assert len(righe[1]) == len(f2.INTESTAZIONI_V2)
