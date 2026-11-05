"""Fase 11 — backup logico XLSX multi-foglio e restore (SQLite; PostgreSQL se disponibile).

Nessun test tocca il database reale. ``popola`` valorizza anche i campi
vassoio/stato/timestamp/eliminato (Fasi 7-8): il backup li deve preservare.
"""

import os
import zipfile
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from openpyxl import Workbook, load_workbook
from sqlalchemy import create_engine, delete, event, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from magazzino_profili.domain import Base, Colore, Movimento, Pezzo, Profilo, Spezzone
from magazzino_profili.reports import backup_excel as be
from magazzino_profili.reports import esporta_inventario_excel
from magazzino_profili.services import carica, scarica
from magazzino_profili.services.anagrafica import crea_profilo
from magazzino_profili.services.spezzoni import registra_spezzone

VAR = "MAGAZZINO_TEST_DB_URL"
TABELLE = [Profilo, Colore, Pezzo, Movimento, Spezzone]


def _sqlite(percorso):
    eng = create_engine(f"sqlite:///{percorso}")

    @event.listens_for(eng, "connect")
    def _c(dbapi, _):
        dbapi.isolation_level = None          # ricetta SQLAlchemy per

    @event.listens_for(eng, "begin")          # transazioni vere su pysqlite
    def _b(conn):
        conn.exec_driver_sql("BEGIN")

    Base.metadata.create_all(eng)
    return eng


@pytest.fixture(params=["sqlite", "postgres"])
def amb(request, tmp_path):
    if request.param == "sqlite":
        yield _sqlite(tmp_path / "a.db"), _sqlite(tmp_path / "b.db")
        return
    url = os.environ.get(VAR)
    if not url:
        pytest.skip(f"{VAR} non impostata")
    eng = create_engine(url.replace("postgresql://", "postgresql+psycopg://", 1))
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng, eng
    Base.metadata.drop_all(eng)


def svuota(eng):
    if eng.dialect.name == "postgresql":
        with eng.begin() as c:
            c.execute(text("TRUNCATE spezzoni, movimenti, pezzi, colori, profili RESTART IDENTITY CASCADE"))
    else:
        with eng.begin() as c:
            for m in reversed(TABELLE):
                c.execute(delete(m.__table__))


def snap(eng):
    with eng.connect() as c:
        return {m.__tablename__: [tuple(r) for r in c.execute(select(m.__table__).order_by(m.__table__.c.id))]
                for m in TABELLE}


def popola(eng):
    with Session(eng, expire_on_commit=False) as s:
        crea_profilo(s, "AB12", "Profilo AB12", Decimal("1.2500"), 6000, "t")
        crea_profilo(s, "CD22", "Altro", Decimal("2.7500"), 6500, "t")
        s.execute(Profilo.__table__.update().where(Profilo.codice == "AB12")
                  .values(descrizione='Profilo =1+1 "è"; con\na capo  ',
                          immagine_sezione="immagini_sezioni/AB-12.png"))
        s.commit()
    for cod, col, lung, q, ub in [("AB12", "RAL 7016", 6000, 10, "Vassoio 4"),
                                  ("AB12", "Bianco", 3000, 4, None),
                                  ("CD22", "RAL 7016", 6500, 7, "Scaffale; A")]:
        with Session(eng, expire_on_commit=False) as s:
            carica(s, cod, col, lung, q, "op", "Carico è €", ub)
    # Campi Fasi 7-8: vassoio, stato, timestamp con microsecondi, pezzo eliminato.
    with Session(eng, expire_on_commit=False) as s:
        p1 = s.scalars(select(Pezzo).where(Pezzo.barcode == "AB12-RAL7016-6000")).one()
        p1.numero_vassoio = "Vassoio 4"
        p1.stato = "Scaricato"
        p1.data_ultimo_cambio_stato = datetime(2026, 10, 20, 8, 0, 0, 123456, tzinfo=timezone.utc)
        p1.scorta_minima = 3
        p3 = s.scalars(select(Pezzo).where(Pezzo.barcode == "CD22-RAL7016-6500")).one()
        p3.eliminato_il = datetime(2026, 10, 21, 9, 30, tzinfo=timezone.utc)
        p3.stato = "Caricato"
        s.commit()
    with Session(eng, expire_on_commit=False) as s:
        scarica(s, "AB12-RAL7016-6000", 3, "op", "Scarico")
        # Snapshot storico deliberatamente impostato dopo il movimento.
        p = s.scalar(select(Pezzo).where(Pezzo.barcode == "AB12-RAL7016-6000"))
        p.stato = "Scaricato"
        p.data_ultimo_cambio_stato = datetime(2026, 10, 20, 8, 0, 0, 123456, tzinfo=timezone.utc)
        s.commit()
    with Session(eng, expire_on_commit=False) as s:
        registra_spezzone(s, 1, 800, 500, "op")


def _riapri_e_modifica(percorso, foglio, riga, colonna, valore, out):
    wb = load_workbook(percorso)
    ws = wb[foglio]
    col = [c.value for c in ws[1]].index(colonna) + 1
    ws.cell(row=riga, column=col, value=valore)
    wb.save(out)
    return out


# ------------------------------------------------------------------ export
def test_fogli_intestazioni_conteggi(amb, tmp_path):
    src, _ = amb
    popola(src)
    with Session(src) as s:
        out = be.esporta_backup_logico_excel(s, tmp_path / "b.xlsx")
    wb = load_workbook(out)
    assert wb.sheetnames == list(be.NOMI_FOGLI)
    for nome in be.FOGLI:
        assert tuple(c.value for c in wb[nome][1]) == be.INTESTAZIONI[nome]
        assert all(c.font.bold for c in wb[nome][1])
    assert [wb[n].max_row - 1 for n in be.FOGLI] == [0, 2, 2, 3, 4, 1, 0, 0]
    meta = {r[0].value: r[1].value for r in wb["Metadati"].iter_rows(min_row=2)}
    assert meta["versione_formato"] == be.VERSIONE_FORMATO and meta["righe_Pezzi"] == 3
    assert meta["applicazione"] == "Magazzino Profili"
    assert "utenti" not in wb.sheetnames


def test_intestazioni_coprono_lo_schema():
    for nome, modello in be.FOGLI.items():
        assert set(be.INTESTAZIONI[nome]) == {c.name for c in modello.__table__.columns}, nome


# ------------------------------------------------------------------ roundtrip
def test_roundtrip_db_vuoto(amb, tmp_path):
    src, dst = amb
    popola(src)
    prima = snap(src)
    with Session(src) as s:
        out = be.esporta_backup_logico_excel(s, tmp_path / "b.xlsx")
    bk = be.valida_backup_logico_excel(out)
    svuota(src)
    with Session(dst) as s:
        be.ripristina_backup_logico_excel(s, bk, modalita="db_vuoto")
    assert snap(dst) == prima                      # id, FK, Decimal, microsecondi, null: tutto uguale
    with Session(dst, expire_on_commit=False) as s:
        p = carica(s, "CD22", "Nero", 4000, 1, "op", "dopo")
        assert p.id == max(r[0] for r in prima["pezzi"]) + 1


def test_roundtrip_preserva_vassoio_stato_eliminati(amb, tmp_path):
    """Vassoio, stato, timestamp con microsecondi e pezzo eliminato: presenti e identici."""
    src, dst = amb
    popola(src)
    prima = snap(src)
    assert any(r[8] == "Vassoio 4" and r[9] == "Scaricato" for r in prima["pezzi"])
    assert any(r[11] is not None for r in prima["pezzi"])          # eliminato_il valorizzato
    with Session(src) as s:
        out = be.esporta_backup_logico_excel(s, tmp_path / "b.xlsx")
    wb = load_workbook(out)
    righe = [dict(zip((c.value for c in wb["Pezzi"][1]), (c.value for c in r))) for r in wb["Pezzi"].iter_rows(min_row=2)]
    assert any(r["numero_vassoio"] == "Vassoio 4" and r["stato"] == "Scaricato"
               and r["data_ultimo_cambio_stato"] == "2026-10-20T08:00:00.123456+00:00" for r in righe)
    assert any(r["eliminato_il"] == "2026-10-21T09:30:00+00:00" for r in righe)
    bk = be.valida_backup_logico_excel(out)
    svuota(src)
    with Session(dst) as s:
        be.ripristina_backup_logico_excel(s, bk, modalita="db_vuoto")
    assert snap(dst) == prima


def test_sequenze_senza_riallineamento_falliscono_su_postgres(amb, tmp_path, monkeypatch):
    src, dst = amb
    if src.dialect.name != "postgresql":
        pytest.skip("solo PostgreSQL")
    popola(src)
    with Session(src) as s:
        out = be.esporta_backup_logico_excel(s, tmp_path / "b.xlsx")
    bk = be.valida_backup_logico_excel(out)
    svuota(src)
    monkeypatch.setattr(be, "_riallinea_sequenze", lambda s: None)
    with Session(dst) as s:
        be.ripristina_backup_logico_excel(s, bk, modalita="db_vuoto")
    with pytest.raises(IntegrityError):
        with Session(dst) as s:
            carica(s, "CD22", "Nero", 4000, 1, "op", "dopo")


def test_testo_utente_resta_testo(amb, tmp_path):
    src, _ = amb
    popola(src)
    with Session(src) as s:
        out = be.esporta_backup_logico_excel(s, tmp_path / "b.xlsx")
    c = next(r for r in load_workbook(out)["Profili"].iter_rows(min_row=2))[2]
    assert c.value == 'Profilo =1+1 "è"; con\na capo  ' and c.data_type == "s"
    assert be.valida_backup_logico_excel(out).tabelle["Profili"][0]["descrizione"] == c.value


def test_testo_lungo_e_caratteri_illegali(amb, tmp_path):
    src, _ = amb
    popola(src)
    with Session(src) as s:
        s.execute(Profilo.__table__.update().where(Profilo.codice == "CD22").values(descrizione="x" * 40000))
        s.commit()
        with pytest.raises(be.BackupNonValidoError, match="oltre il limite"):
            be.esporta_backup_logico_excel(s, tmp_path / "l.xlsx")
        s.execute(Profilo.__table__.update().where(Profilo.codice == "CD22").values(descrizione="a\x1fb"))
        s.commit()
        with pytest.raises(be.BackupNonValidoError, match="carattere di controllo"):
            be.esporta_backup_logico_excel(s, tmp_path / "i.xlsx")
    assert not (tmp_path / "l.xlsx").exists() and not (tmp_path / "i.xlsx").exists()


# ------------------------------------------------------------------ validazione
@pytest.fixture()
def ok(amb, tmp_path):
    src, dst = amb
    popola(src)
    with Session(src) as s:
        return be.esporta_backup_logico_excel(s, tmp_path / "ok.xlsx"), src, dst


@pytest.mark.parametrize("foglio,riga,colonna,valore,frag", [
    ("Pezzi", 2, "profilo_id", 999, "Profili.id=999 inesistente"),
    ("Pezzi", 3, "id", 1, "duplicato"),
    ("Pezzi", 3, "barcode", "AB12-RAL7016-6000", "duplicato"),
    ("Pezzi", 2, "lunghezza_mm", "abc", "intero atteso"),
    ("Pezzi", 2, "quantita", -1, "almeno 0"),
    ("Pezzi", 2, "stato", "Scaduto", "non ammesso"),
    ("Pezzi", 2, "stato", "Caricato", None),                       # valore valido: nessun errore
    ("Movimenti", 2, "tipo", "BOH", "non ammesso"),
    ("Movimenti", 2, "data_ora", "2026-10-20T10:00:00", "fuso"),
    ("Movimenti", 2, "data_ora", "ieri", "ISO 8601"),
    ("Movimenti", 2, "pezzo_id", 77, "Pezzi.id=77"),
    ("Spezzoni", 2, "utilizzato", "si", "booleano"),
    ("Profili", 2, "peso_kg_per_metro", "pesante", "numero atteso"),
    ("Metadati", 2, "valore", 99, "versione_formato"),
])
def test_errori_con_foglio_riga_colonna(ok, tmp_path, foglio, riga, colonna, valore, frag):
    out, *_ = ok
    if foglio == "Metadati":
        wb = load_workbook(out)
        wb["Metadati"]["B2"] = valore
        wb.save(tmp_path / "x.xlsx")
    else:
        _riapri_e_modifica(out, foglio, riga, colonna, valore, tmp_path / "x.xlsx")
    if frag is None:
        bk = be.valida_backup_logico_excel(tmp_path / "x.xlsx")
        assert bk.tabelle["Pezzi"][0]["stato"] == "Caricato"
        return
    with pytest.raises(be.BackupNonValidoError) as e:
        be.valida_backup_logico_excel(tmp_path / "x.xlsx")
    testo = str(e.value)
    assert frag in testo and f"[{foglio}" in testo


def test_numeri_come_float_accettati(ok, tmp_path):
    """Excel/LibreOffice rileggono gli interi come float (5.0): vanno accettati."""
    out, *_ = ok
    x = _riapri_e_modifica(out, "Pezzi", 2, "quantita", 5.0, tmp_path / "f.xlsx")
    x = _riapri_e_modifica(x, "Profili", 2, "lunghezza_standard_mm", 6000.0, tmp_path / "f.xlsx")
    bk = be.valida_backup_logico_excel(tmp_path / "f.xlsx")
    assert bk.tabelle["Pezzi"][0]["quantita"] == 5
    assert bk.tabelle["Profili"][0]["lunghezza_standard_mm"] == 6000


def test_conteggio_metadati_e_righe_cancellate(ok, tmp_path):
    out, *_ = ok
    wb = load_workbook(out)
    wb["Pezzi"].delete_rows(4)
    wb.save(tmp_path / "x.xlsx")
    with pytest.raises(be.BackupNonValidoError, match="Metadati dichiara"):
        be.valida_backup_logico_excel(tmp_path / "x.xlsx")


def test_file_malformati(tmp_path, ok):
    out, *_ = ok
    (tmp_path / "c.xlsx").write_bytes(b"non e' uno zip")
    (tmp_path / "v.xlsx").write_bytes(b"")
    for nome in ("c.xlsx", "v.xlsx"):
        with pytest.raises(be.BackupNonValidoError, match="non apribile"):
            be.valida_backup_logico_excel(tmp_path / nome)
    wb = load_workbook(out)
    del wb["Spezzoni"]
    wb.save(tmp_path / "m.xlsx")
    with pytest.raises(be.BackupNonValidoError, match="fogli attesi"):
        be.valida_backup_logico_excel(tmp_path / "m.xlsx")
    wb = load_workbook(out)
    wb["Colori"]["B1"] = "xx"
    wb.save(tmp_path / "h.xlsx")
    with pytest.raises(be.BackupNonValidoError, match="intestazioni attese"):
        be.valida_backup_logico_excel(tmp_path / "h.xlsx")
    with pytest.raises(FileNotFoundError):
        be.valida_backup_logico_excel(tmp_path / "no.xlsx")


def test_file_storico_foglio_singolo_e_ripristino_parziale(amb, tmp_path):
    src, _ = amb
    popola(src)
    with Session(src) as s:
        esporta_inventario_excel(s, tmp_path / "storico.xlsx")
    with pytest.raises(be.BackupNonValidoError, match="NON è un backup completo") as e:
        be.valida_backup_logico_excel(tmp_path / "storico.xlsx")
    assert e.value.formato_storico is True


def test_backup_vuoto(amb, tmp_path):
    """Export da DB vuoto: 0 righe in ogni foglio, validazione e restore ok."""
    src, dst = amb
    with Session(src) as s:
        out = be.esporta_backup_logico_excel(s, tmp_path / "v.xlsx")
    bk = be.valida_backup_logico_excel(out)
    assert all(len(righe) == 0 for righe in bk.tabelle.values())
    with Session(dst) as s:
        be.ripristina_backup_logico_excel(s, bk, modalita="db_vuoto")
    assert all(righe == [] for righe in snap(dst).values())


# ------------------------------------------------------------------ restore: rifiuti e rollback
def test_db_non_vuoto_rifiutato_senza_modifiche(ok):
    out, src, dst = ok
    bk = be.valida_backup_logico_excel(out)
    if dst is not src:
        popola(dst)
    prima = snap(dst)
    with Session(dst) as s, pytest.raises(be.RipristinoRifiutatoError, match="non vuoto"):
        be.ripristina_backup_logico_excel(s, bk, modalita="db_vuoto")
    assert snap(dst) == prima


def test_merge_rifiuta_collisioni_e_non_aggiorna(ok):
    out, src, dst = ok
    bk = be.valida_backup_logico_excel(out)
    if dst is not src:
        popola(dst)
    prima = snap(dst)
    with Session(dst) as s, pytest.raises(be.RipristinoRifiutatoError, match="già presente"):
        be.ripristina_backup_logico_excel(s, bk, modalita="merge")
    assert snap(dst) == prima


def test_merge_aggiunge_solo_record_nuovi(ok, tmp_path):
    out, src, dst = ok
    bk = be.valida_backup_logico_excel(out)
    svuota(src)
    with Session(dst, expire_on_commit=False) as s:
        s.add(Profilo(id=100, codice="ZZ9", descrizione="esistente",
                      peso_kg_per_metro=Decimal("1"), lunghezza_standard_mm=6000))
        s.commit()
    with Session(dst) as s:
        be.ripristina_backup_logico_excel(s, bk, modalita="merge")
    with Session(dst) as s:
        assert sorted(s.scalars(select(Profilo.id))) == [1, 2, 100]
        assert s.get(Profilo, 100).descrizione == "esistente"


def test_rollback_completo_su_errore(ok, monkeypatch):
    out, src, dst = ok
    bk = be.valida_backup_logico_excel(out)
    svuota(src)

    def boom(s):
        raise RuntimeError("guasto simulato")

    monkeypatch.setattr(be, "_riallinea_sequenze", boom)
    with Session(dst) as s, pytest.raises(RuntimeError, match="guasto"):
        be.ripristina_backup_logico_excel(s, bk, modalita="db_vuoto")
    assert all(righe == [] for righe in snap(dst).values())


def test_sessione_gia_in_transazione_e_argomenti(ok):
    out, src, dst = ok
    bk = be.valida_backup_logico_excel(out)
    svuota(src)
    with Session(dst) as s:
        s.execute(select(Profilo.id)).all()
        with pytest.raises(be.RipristinoRifiutatoError, match="transazione"):
            be.ripristina_backup_logico_excel(s, bk, modalita="db_vuoto")
    with Session(dst) as s:
        with pytest.raises(TypeError):
            be.ripristina_backup_logico_excel(s, "file.xlsx", modalita="db_vuoto")
        with pytest.raises(ValueError):
            be.ripristina_backup_logico_excel(s, bk, modalita="sovrascrivi")


def test_molte_righe(amb, tmp_path):
    src, dst = amb
    with Session(src, expire_on_commit=False) as s:
        s.add(Profilo(id=1, codice="P", descrizione="p", peso_kg_per_metro=Decimal("1"),
                      lunghezza_standard_mm=6000))
        s.add(Colore(id=1, codice_normalizzato="C", nome_visualizzato="C"))
        s.commit()
        s.execute(Pezzo.__table__.insert(),
                  [dict(id=i, profilo_id=1, colore_id=1, lunghezza_mm=i, quantita=1, barcode=f"P-C-{i}")
                   for i in range(1, 2501)])
        s.commit()
    with Session(src) as s:
        out = be.esporta_backup_logico_excel(s, tmp_path / "g.xlsx")
    bk = be.valida_backup_logico_excel(out)
    assert len(bk.tabelle["Pezzi"]) == 2500
    prima = snap(src)
    svuota(src)
    with Session(dst) as s:
        be.ripristina_backup_logico_excel(s, bk, modalita="db_vuoto")
    assert snap(dst) == prima


def test_limite_righe_excel(amb, tmp_path, monkeypatch):
    src, _ = amb
    popola(src)
    monkeypatch.setattr(be, "MAX_RIGHE", 2)
    with Session(src) as s, pytest.raises(be.BackupNonValidoError, match="limite di un foglio"):
        be.esporta_backup_logico_excel(s, tmp_path / "x.xlsx")
    assert not (tmp_path / "x.xlsx").exists()
