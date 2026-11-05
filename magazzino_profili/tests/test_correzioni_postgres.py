"""Migrazioni e concorrenza multiprocesso su PostgreSQL di prova esplicito."""
import os
from pathlib import Path
from uuid import uuid4
from concurrent.futures import ProcessPoolExecutor
import multiprocessing
import pytest
from sqlalchemy import create_engine,text,select,func
from sqlalchemy.engine import make_url
from magazzino_profili.domain import Base,Pezzo,Profilo
from magazzino_profili.db import crea_session_factory

URL=os.environ.get("MAGAZZINO_TEST_DB_URL")
pytestmark=pytest.mark.skipif(not URL,reason="Serve cluster PostgreSQL sintetico dedicato")

@pytest.fixture
def ambiente():
    u=make_url(URL)
    assert (u.database or "").endswith("_test") or (u.database or "").startswith("test_")
    schema="prova_"+uuid4().hex
    admin=create_engine(URL)
    with admin.begin() as c:c.execute(text(f"CREATE SCHEMA {schema}"))
    engine=create_engine(URL,connect_args={"options":"-csearch_path="+schema})
    try:yield engine,schema
    finally:
        engine.dispose()
        with admin.begin() as c:c.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()

def test_migrazione_da_schema_aggregato_non_cambia_i_dati(ambiente):
    from magazzino_profili.db.migrazioni import applica_migrazioni
    from magazzino_profili.services.pezzi_unitari import crea_pezzi_unitari
    e,_=ambiente;Base.metadata.create_all(e)
    with e.begin() as c:
        c.execute(text("ALTER TABLE pezzi DROP COLUMN unitario CASCADE"))
        c.execute(text("ALTER TABLE pezzi ADD CONSTRAINT combinazione UNIQUE(profilo_id,colore_id,lunghezza_mm)"))
        c.execute(text("INSERT INTO profili(id,codice,descrizione,peso_kg_per_metro,lunghezza_standard_mm) VALUES(1,'AB12','Storico',1.2,6000)"))
        c.execute(text("INSERT INTO colori(id,codice_normalizzato,nome_visualizzato) VALUES(1,'RAL7016','RAL7016')"))
        c.execute(text("INSERT INTO pezzi(id,profilo_id,colore_id,lunghezza_mm,quantita,barcode) VALUES(1,1,1,6000,5,'STORICO')"))
        c.execute(text("SELECT setval(pg_get_serial_sequence('pezzi','id'),1)"))
    applicate=applica_migrazioni(e)
    assert "010_barcode_unitari.sql" in applicate
    f=crea_session_factory(e)
    with f() as s:
        p=s.get(Pezzo,1);assert p.quantita==5 and p.barcode=="STORICO" and not p.unitario
    with f() as s:
        nuovi=crea_pezzi_unitari(s,codice="AB12",colore="RAL7016",lunghezza_mm=6000,quantita=3,utente="test",causale="Prova")
        assert len(nuovi)==3
    with f() as s:assert s.scalar(select(func.sum(Pezzo.quantita)))==8
    assert applica_migrazioni(e)==[]

def test_checksum_impedisce_modifiche_a_migrazioni_applicate(ambiente,tmp_path,monkeypatch):
    import shutil
    from magazzino_profili.db import migrazioni as m
    e,_=ambiente;Base.metadata.create_all(e)
    cartella=tmp_path/"migrations";shutil.copytree(m.CARTELLA_MIGRAZIONI,cartella)
    monkeypatch.setattr(m,"CARTELLA_MIGRAZIONI",cartella)
    m.applica_migrazioni(e)
    p=cartella/"007_indici_operativi.sql";p.write_text(p.read_text()+"\n-- alterazione simulata\n")
    with pytest.raises(RuntimeError,match="modificata"):m.applica_migrazioni(e)

def _crea_da_processo(url,schema):
    from magazzino_profili.services.idempotenza import esegui
    from magazzino_profili.services.pezzi_unitari import _crea_in_transazione
    e=create_engine(url,connect_args={"options":"-csearch_path="+schema})
    f=crea_session_factory(e)
    try:
        def azione(s):
            pezzi=_crea_in_transazione(s,"AB12","NERO",6000,2,"test","Prova concorrente")
            return {"barcode":[p.barcode for p in pezzi]}
        return esegui(f,"test","stessa-richiesta","creazione",{"numero":2},azione)
    finally:e.dispose()

def test_idempotenza_reale_fra_due_processi(ambiente):
    e,schema=ambiente;Base.metadata.create_all(e);f=crea_session_factory(e)
    with f() as s,s.begin():s.add(Profilo(codice="AB12",descrizione="Prova",peso_kg_per_metro=1.2,lunghezza_standard_mm=6000))
    with ProcessPoolExecutor(max_workers=2,mp_context=multiprocessing.get_context("spawn")) as pool:
        futuri=[pool.submit(_crea_da_processo,URL,schema) for _ in range(2)]
        risultati=[f.result(timeout=40) for f in futuri]
    assert risultati[0]==risultati[1]
    with f() as s:assert s.scalar(select(func.count()).select_from(Pezzo))==2
