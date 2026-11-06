"""Regressioni distribuzione: solo filesystem temporaneo, nessun setup eseguito."""
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import tomllib

import pytest
from sqlalchemy import create_engine, inspect, text
from magazzino_profili import percorsi_installazione as perc
from magazzino_profili.db import migrazioni as mig
from magazzino_profili.services import aggiornamenti as ag


@pytest.fixture
def installazione(tmp_path, monkeypatch):
    from PySide6.QtCore import QSettings
    formato = QSettings.defaultFormat()
    impostazioni = perc.preferenze("MagazzinoProfili", "Desktop").fileName()
    monkeypatch.setenv("MAGAZZINO_INSTALLATO", "1")
    monkeypatch.setenv("MAGAZZINO_DATI", str(tmp_path / "dati"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "locale"))
    monkeypatch.delenv("MAGAZZINO_CONFIG", raising=False)
    monkeypatch.delenv("MAGAZZINO_PREFERENZE_TEST", raising=False)
    monkeypatch.setattr(tempfile, "tempdir", tempfile.tempdir)
    yield tmp_path
    QSettings.setDefaultFormat(formato)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(Path(impostazioni).parent.parent))


def configurazione(p):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('[database]\nhost="localhost"\nporta=59999\nutente="test"\npassword="solo-test"\ndbname="installer_test"\n'
                 '[backup]\npg_dump="bin/pg_dump.exe"\n[immagini]\ncatalogo="catalogo"\n', encoding="utf-8")
    (p.parent / "catalogo").mkdir(exist_ok=True)
    return p


def test_runtime_separa_dati_temp_e_preferenze(installazione, monkeypatch):
    from PySide6.QtCore import QSettings
    perc.prepara_runtime(migra_preferenze=False, attiva_mutex=False)
    assert json.loads((perc.cartella_dati()/".magazzino-profili-dati.json").read_text())["app_id"] == perc.APP_ID
    assert Path(tempfile.gettempdir()) == perc.cartella_dati()/"temporanei"
    assert Path(perc.preferenze("MagazzinoProfili", "Desktop").fileName()).is_relative_to(perc.cartella_dati())
    assert os.environ["MAGAZZINO_CONFIG"] == str(perc.config_installata())
    assert not perc.dati_legacy().exists()
    assert ag.cartella_cache().is_relative_to(perc.cartella_dati())


def test_runtime_rifiuta_dati_dentro_programma(installazione, monkeypatch):
    monkeypatch.setenv("MAGAZZINO_DATI", str(Path(sys.executable).parent/"dati-finti"))
    with pytest.raises(RuntimeError, match="separata"):
        perc.prepara_runtime(migra_preferenze=False, attiva_mutex=False)


def test_runtime_non_usa_cartella_altrui(installazione):
    perc.cartella_dati().mkdir()
    (perc.cartella_dati()/".magazzino-profili-dati.json").write_text('{"app_id":"altro"}')
    with pytest.raises(RuntimeError, match="altro programma"):
        perc.prepara_runtime(migra_preferenze=False, attiva_mutex=False)


def test_import_config_conserva_origine_e_cred_impostate(installazione):
    fonte = configurazione(installazione/"portabile/config.toml")
    originale = fonte.read_bytes()
    cartella = fonte.parent/"immagini_sezioni";cartella.mkdir()
    (cartella/"AA1.png").write_bytes(b"immagine-sintetica")
    nuovo = perc.importa_config(fonte)
    dati = tomllib.loads(nuovo.read_text(encoding="utf-8"))
    assert dati["database"]["password"] == "solo-test" and fonte.read_bytes() == originale
    assert Path(dati["immagini"]["catalogo"]) == fonte.parent/"catalogo"
    assert Path(dati["backup"]["pg_dump"]) == fonte.parent/"bin/pg_dump.exe"
    assert Path(dati["backup"]["cartella"]) == perc.cartella_dati()/"backup"
    assert (perc.cartella_dati()/"immagini_sezioni/AA1.png").read_bytes() == b"immagine-sintetica"
    perc.importa_config(fonte)
    assert len(list(perc.cartella_dati().glob("config-precedente-*.toml"))) == 1


def test_config_malformata_non_sostituisce_destinazione(installazione):
    destinazione = perc.importa_config(configurazione(installazione/"buona/config.toml"))
    precedente = destinazione.read_bytes()
    male = installazione/"errata.toml";male.write_text("[database\n")
    with pytest.raises(Exception): perc.importa_config(male)
    assert destinazione.read_bytes() == precedente


def test_config_immagini_omonime_diverse_non_sovrascritte(installazione):
    fonte=configurazione(installazione/"portabile/config.toml")
    (fonte.parent/"immagini_sezioni").mkdir()
    (fonte.parent/"immagini_sezioni/AA.png").write_bytes(b"vecchia")
    (perc.cartella_dati()/"immagini_sezioni").mkdir(parents=True)
    nuova=perc.cartella_dati()/"immagini_sezioni/AA.png";nuova.write_bytes(b"nuova")
    with pytest.raises(FileExistsError): perc.importa_config(fonte)
    assert nuova.read_bytes()==b"nuova" and not perc.config_installata().exists()


def test_installed_config_non_legge_cwd_o_override_altrui(installazione, monkeypatch):
    from magazzino_profili.db.config import trova_config
    f=configurazione(installazione/"config.toml")
    monkeypatch.chdir(installazione);monkeypatch.setenv("MAGAZZINO_CONFIG",str(f))
    assert trova_config() is None
    assert trova_config(f)==f.resolve()


def test_backup_installato_scrive_solo_nei_dati(installazione):
    from magazzino_profili.backup.backup_db import leggi_config_backup
    fonte=configurazione(installazione/"portabile/config.toml")
    assert Path(leggi_config_backup(fonte).cartella)==perc.cartella_dati()/"backup"


@pytest.mark.skipif(os.name!="nt",reason="Mutex solo su Windows")
def test_mutex_nativo_creato_in_processo_isolato(installazione):
    import subprocess
    codice="from magazzino_profili import percorsi_installazione as p; p.MUTEX_APPLICAZIONE='Local\\\\MagazzinoProfili.TestInstaller'; p.prepara_runtime(migra_preferenze=False); assert p._mutex is not None"
    esito=subprocess.run([sys.executable,"-B","-c",codice],capture_output=True,text=True,timeout=20)
    assert esito.returncode==0,esito.stderr


@pytest.mark.parametrize("sql,numero", [
    ("SELECT ';'; SELECT 2;",2),
    ('DO $test$ BEGIN PERFORM 1; PERFORM 2; END $test$; SELECT 1;',2),
    ('/* esterno /* interno ; */ fine */ SELECT 1; -- commento ;\nSELECT 2;',2),
    ('SELECT \'un\\\'apostrofo;\'; SELECT "campo;";',2),
])
def test_separatore_sql(sql, numero):
    assert len(mig.separa_istruzioni(sql)) == numero


@pytest.mark.parametrize("sql", ["SELECT 'aperta", "/* commento", "DO $$ aperto"])
def test_separatore_rifiuta_sql_troncato(sql):
    with pytest.raises(ValueError): mig.separa_istruzioni(sql)


def prepara_schema(tmp_path, monkeypatch):
    script=tmp_path/"sql";script.mkdir()
    monkeypatch.setattr(mig,"CARTELLA_MIGRAZIONI",script)
    engine=create_engine("sqlite+pysqlite:///"+str(tmp_path/"sintetico.db"))
    with engine.begin() as c:
        c.execute(text("CREATE TABLE esempio (id INTEGER PRIMARY KEY, codice TEXT)"))
        c.execute(text("INSERT INTO esempio VALUES (1,'TEST')"))
    return script, engine


def test_migrazione_vecchia_conserva_dati_e_idempotente(tmp_path,monkeypatch):
    script,e=prepara_schema(tmp_path,monkeypatch)
    try:
        (script/"001_aggiunta.sql").write_text("ALTER TABLE esempio ADD COLUMN vassoio TEXT;")
        assert mig.applica_migrazioni(e)==["001_aggiunta.sql"]
        assert mig.applica_migrazioni(e)==[]
        with e.connect() as c: assert c.execute(text("SELECT id,codice,vassoio FROM esempio")).one()==(1,"TEST",None)
    finally: e.dispose()


def test_fallimento_ripristina_intero_lotto_schema_e_dati(tmp_path,monkeypatch):
    script,e=prepara_schema(tmp_path,monkeypatch)
    try:
        (script/"001_prima.sql").write_text("ALTER TABLE esempio ADD COLUMN nuova TEXT; UPDATE esempio SET codice='ALTERATO';")
        (script/"002_rotta.sql").write_text("INSERT INTO tabella_assente VALUES (1);")
        with pytest.raises(Exception): mig.applica_migrazioni(e)
        assert [col["name"] for col in inspect(e).get_columns("esempio")]==["id","codice"]
        assert "migrazioni_applicate" not in inspect(e).get_table_names()
        with e.connect() as c: assert c.scalar(text("SELECT codice FROM esempio"))=="TEST"
    finally:e.dispose()


def test_checksum_e_downgrade_bloccati(tmp_path,monkeypatch):
    script,e=prepara_schema(tmp_path,monkeypatch)
    try:
        file=script/"001.sql";file.write_text("SELECT 1;")
        mig.applica_migrazioni(e)
        file.write_text("SELECT 2;")
        with pytest.raises(RuntimeError,match="modificata"): mig.applica_migrazioni(e)
        file.unlink()  # Solo script temporaneo del test.
        with pytest.raises(RuntimeError,match="incompatibile"): mig.applica_migrazioni(e)
    finally:e.dispose()


def test_backup_preventivo_non_elimina_backup_esistenti(tmp_path):
    from magazzino_profili.backup.backup_db import esegui_backup
    vecchio=tmp_path/"magazzino_profili_20260101.dump";vecchio.write_bytes(b"precedente")
    comando=[sys.executable,"-c","import pathlib,sys;pathlib.Path(sys.argv[sys.argv.index('-f')+1]).write_bytes(b'PGDUMP-TEST')"]
    esegui_backup("localhost",59999,"test","","installer_test",tmp_path,1,comando,conserva_precedenti=True)
    assert vecchio.read_bytes()==b"precedente" and len(list(tmp_path.glob("*.dump")))==2


def firma_finta(tmp_path,monkeypatch,tipo):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
    chiave=Ed25519PrivateKey.generate()
    pubblica=base64.b64encode(chiave.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)).decode()
    f=tmp_path/"setup.exe";f.write_bytes(b"NON ESEGUIRE: setup sintetico")
    d=dict(versione="99.0.0",url_installer="https://esempio.invalid/setup.exe",sha256=hashlib.sha256(f.read_bytes()).hexdigest(),dimensione=f.stat().st_size)
    if tipo:d["tipo"]=tipo
    d["firma"]=base64.b64encode(chiave.sign(ag.forma_canonica(d))).decode()
    valida=ag.valida_manifest
    monkeypatch.setattr(ag,"valida_manifest",lambda dati:valida(dati,pubblica))
    return f,ag.valida_manifest(d)


def test_setup_firmato_non_crea_copia_portabile(installazione,monkeypatch):
    f,m=firma_finta(installazione,monkeypatch,"setup")
    assert ag.prepara_versione(m,f)==f
    assert not ag._cartella_versioni().exists()
    f.write_bytes(b"alterato")
    with pytest.raises(ag.ErroreAggiornamento,match="modificato"):ag.prepara_versione(m,f)


def test_installata_rifiuta_aggiornamento_portabile(installazione,monkeypatch):
    f,m=firma_finta(installazione,monkeypatch,None)
    with pytest.raises(ag.ErroreAggiornamento,match="portabile"):ag.prepara_versione(m,f)
    assert not ag.avvia_versione_attiva()


def test_setup_comando_senza_shell_e_preserva_cartella(installazione,monkeypatch):
    monkeypatch.setattr(sys,"platform","win32")
    chiamate=[]
    comando=ag.lancia_aggiornamento(str(installazione/"un setup.exe"),esegui=chiamate.append,setup=True)
    assert chiamate==[comando] and comando[0].endswith("un setup.exe")
    assert "/VERYSILENT" in comando and "/NORESTART" in comando and "/RIAVVIA=1" in comando
    assert "/DIR="+str(Path(sys.executable).resolve().parent) in comando
    assert "powershell.exe" not in comando


def test_installata_non_avvia_cluster_legacy(installazione,monkeypatch):
    from magazzino_profili.db import server
    monkeypatch.setattr(server,"is_ready",lambda *a,**k:pytest.fail("Non deve leggere cluster operativo"))
    assert server.ensure_running()


def test_iss_dati_conservati_e_identita_unica():
    root=Path(__file__).resolve().parents[2]
    script=(root/"installer/MagazzinoProfili.iss").read_text(encoding="utf-8")
    assert "PrivilegesRequired=lowest" in script and "compiler:Languages\\Italian.isl" in script
    assert "AppId={#AppIdFisso}" in script and "MutexRuntime = '{#MutexApp}'" in script
    assert "if not UninstallSilent" in script and "MB_DEFBUTTON2" in script
    assert 'Name: "{app}\\*"' not in script and "netsh" not in script.lower()
    assert "SenzaCollegamenti(Dati)" in script and "CheckForMutexes(MutexRuntime)" in script
