"""Verifica reale PostgreSQL in un cluster NUOVO; nessun servizio o DB operativo."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pg-bin",required=True,type=Path)
    p.add_argument("--destinazione",required=True,type=Path)
    p.add_argument("--porta",type=int,default=55947)
    p.add_argument("--pytest",action="store_true")
    p.add_argument("--pytest-non-eseguiti",type=Path,help="JUnit precedente: esegue soltanto i test saltati su un DB nuovo dedicato")
    a=p.parse_args()
    root=a.destinazione.resolve()
    if root.exists() or not 49152<=a.porta<=65535:
        raise SystemExit("Servono cartella nuova e porta di test fra 49152 e 65535")
    for nome in ("pg_ctl.exe","pg_dump.exe","pg_restore.exe"):
        if not (a.pg_bin/nome).is_file(): raise SystemExit("Binario PostgreSQL assente: "+nome)
    root.mkdir(parents=True)
    esiti=[];avviato=False;engines=[]
    def registra(nome): esiti.append({"test":nome,"stato":"superato"})
    def esegui(arg):
        with (root/"comandi.log").open("a",encoding="utf-8") as log:
            subprocess.run(list(map(str,arg)),check=True,stdout=log,stderr=subprocess.STDOUT,timeout=120,
                           creationflags=0x08000000 if os.name=="nt" else 0)
    ctl=a.pg_bin/"pg_ctl.exe";data=root/"cluster-sintetico"
    try:
        esegui([ctl,"initdb","-D",data,"-o","--auth=trust --username=installer_test --encoding=UTF8 --locale=C"])
        esegui([ctl,"-D",data,"-l",root/"postgres.log","-o",f"-h 127.0.0.1 -p {a.porta} -c fsync=on","-w","start"])
        avviato=True
        import psycopg
        from sqlalchemy import create_engine,text,inspect
        from magazzino_profili.domain import Base
        from magazzino_profili.db import migrazioni as m
        from magazzino_profili.backup.backup_db import esegui_backup,verifica_backup
        base=f"postgresql://installer_test@127.0.0.1:{a.porta}/"
        with psycopg.connect(base+"postgres",autocommit=True) as admin:
            for nome in ("installer_test","ripristino_test","regressione_test"):
                admin.execute("CREATE DATABASE "+nome)
        e=create_engine((base+"installer_test").replace("postgresql://","postgresql+psycopg://"));engines.append(e)
        Base.metadata.create_all(e)
        with e.begin() as c:
            c.execute(text("ALTER TABLE pezzi DROP COLUMN unitario CASCADE"))
            c.execute(text("ALTER TABLE pezzi ADD CONSTRAINT combinazione UNIQUE(profilo_id,colore_id,lunghezza_mm)"))
            c.execute(text("INSERT INTO profili(id,codice,descrizione,peso_kg_per_metro,lunghezza_standard_mm) VALUES(1,'TEST01','Dato sintetico',1.2,6000)"))
            c.execute(text("INSERT INTO colori(id,codice_normalizzato,nome_visualizzato) VALUES(1,'RAL7016','RAL7016')"))
            c.execute(text("INSERT INTO pezzi(id,profilo_id,colore_id,lunghezza_mm,quantita,barcode) VALUES(1,1,1,6000,5,'TEST-BARCODE')"))
        dump=esegui_backup("127.0.0.1",a.porta,"installer_test","","installer_test",root/"backup",1,
                          [str(a.pg_bin/"pg_dump.exe")],comando_verifica=[str(a.pg_bin/"pg_restore.exe")],conserva_precedenti=True)
        registra("Backup reale verificato con pg_restore --list prima della migrazione")
        assert len(m.applica_migrazioni(e,crea_schema=True))==12
        with e.connect() as c:
            assert c.execute(text("SELECT barcode,quantita,unitario FROM pezzi WHERE id=1")).one()==("TEST-BARCODE",5,False)
            assert c.scalar(text("SELECT count(*) FROM migrazioni_applicate"))==12
        assert m.applica_migrazioni(e,crea_schema=True)==[]
        registra("Schema storico aggiornato alla versione 12, dati conservati e riavvio idempotente")
        originali=m.CARTELLA_MIGRAZIONI
        nuovo=root/"migrazioni-con-errore";shutil.copytree(originali,nuovo)
        (nuovo/"013_errore.sql").write_text("CREATE TABLE prova_rollback (id INTEGER); UPDATE pezzi SET quantita=99 WHERE id=1; SELECT 1/0;",encoding="utf-8")
        m.CARTELLA_MIGRAZIONI=nuovo
        try:
            try:m.applica_migrazioni(e)
            except Exception:pass
            else:raise AssertionError("Migrazione volutamente errata non rifiutata")
            with e.connect() as c:
                assert c.scalar(text("SELECT quantita FROM pezzi WHERE id=1"))==5
                assert c.scalar(text("SELECT count(*) FROM migrazioni_applicate"))==12
            assert "prova_rollback" not in inspect(e).get_table_names()
            registra("Errore SQL: rollback reale DDL, dati e registro; nessun avvio applicazione")
        finally:m.CARTELLA_MIGRAZIONI=originali
        verifica_backup(dump,[str(a.pg_bin/"pg_restore.exe")])
        esegui([a.pg_bin/"pg_restore.exe","--exit-on-error","--dbname",base+"ripristino_test",dump])
        r=create_engine((base+"ripristino_test").replace("postgresql://","postgresql+psycopg://"));engines.append(r)
        with r.connect() as c:assert c.execute(text("SELECT barcode,quantita FROM pezzi WHERE id=1")).one()==("TEST-BARCODE",5)
        assert "unitario" not in {c["name"] for c in inspect(r).get_columns("pezzi")}
        registra("Ripristino fisico backup su database VUOTO separato: schema storico e pezzi recuperati")
        if a.pytest or a.pytest_non_eseguiti:
            env=os.environ.copy()
            env["MAGAZZINO_TEST_DB_URL"]=(base+"regressione_test").replace("postgresql://","postgresql+psycopg://")
            env["MAGAZZINO_PG_URL"]=env["MAGAZZINO_TEST_DB_URL"]
            env["PATH"]=str(a.pg_bin)+os.pathsep+env.get("PATH","")
            # I test esistenti hanno il proprio isolamento schema/fixture.
            selezione=["magazzino_profili/tests/test_correzioni_postgres.py","magazzino_profili/tests/test_migrazioni_postgres.py"]
            if a.pytest_non_eseguiti:
                import xml.etree.ElementTree as ET
                selezione=[]
                for t in ET.parse(a.pytest_non_eseguiti).iter("testcase"):
                    if t.find("skipped") is None:continue
                    parti=t.get("classname","").split(".")
                    indice=next(i for i,p in enumerate(parti) if p.startswith("test_"))
                    nome="/".join(parti[:indice+1])+".py"
                    if parti[indice+1:]:nome+="::"+"::".join(parti[indice+1:])
                    selezione.append(nome+"::"+t.get("name"))
                if not selezione:raise ValueError("Nessun test non eseguito nel JUnit indicato")
            esegui_test=[sys.executable,"-B","-m","pytest",*selezione,"-q","--junitxml="+str(root/"esito-postgres.xml")]
            with (root/"pytest.log").open("w",encoding="utf-8") as log:
                subprocess.run(esegui_test,env=env,check=True,stdout=log,stderr=subprocess.STDOUT,timeout=180)
            registra("Suite regressione PostgreSQL e concorrenza")
    except Exception as errore:
        esiti.append({"test":"Verifica PostgreSQL","stato":"fallito","motivo":str(errore)})
        raise
    finally:
        for engine in engines:engine.dispose()
        if avviato:
            try:esegui([ctl,"-D",data,"-m","fast","-w","stop"])
            except Exception as errore:esiti.append({"test":"Arresto cluster isolato","stato":"fallito","motivo":str(errore)})
            else:registra("Cluster isolato arrestato; nessuna modifica al servizio operativo")
        (root/"esiti.json").write_text(json.dumps(esiti,ensure_ascii=False,indent=2),encoding="utf-8")
        print(json.dumps(esiti,ensure_ascii=False,indent=2))


if __name__=="__main__":main()
