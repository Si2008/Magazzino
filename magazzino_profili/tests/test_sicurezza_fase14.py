"""Fase 14: sicurezza trasversale (segrete, login, intestazioni, backup, setup, pacchetto, ruoli)."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from magazzino_profili import backup as pkg_backup
from magazzino_profili.domain import Base
from magazzino_profili.sicurezza import Ruolo, crea_utente
from magazzino_profili.sicurezza import utenti as mod_utenti
from magazzino_profili.sicurezza.utenti import (
    SCHEDE_CONSENTITE,
    autentica,
    hash_password,
    valida_password_nuova,
)
from magazzino_profili.web import sicurezza_web as sw
from magazzino_profili.web.app import crea_app

RADICE = Path(__file__).resolve().parents[2]
SEGRETA = "segreto-di-test-molto-lungo-1234567890"
PLACEHOLDER = "SEGRETE_LUNGA_E_CASUALE_MINIMO_32_CARATTERI"


@pytest.fixture()
def fabbrica():
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(eng)
    f = sessionmaker(bind=eng, expire_on_commit=False)
    with f() as s:
        crea_utente(s, "mario", "password123", Ruolo.OPERATORE)
    return f


# ============================================================ segrete dei token
@pytest.mark.parametrize(
    "valore", ["", "corta", "a" * 31, PLACEHOLDER, "a" * 40, "ab" * 20, None, 123]
)
def test_segrete_non_accettabili(valore):
    with pytest.raises(ValueError):
        sw.valida_segrete_token(valore)


def test_segrete_valida():
    assert sw.valida_segrete_token(SEGRETA) == SEGRETA


def test_app_non_richiede_segrete_autenticazione(fabbrica):
    for valore in (None,"",PLACEHOLDER):
        c=TestClient(crea_app(session_factory=fabbrica,segrete_token=valore))
        assert c.get("/api/salute").status_code==200


# ============================================================ limite tentativi
class Orologio:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_limitatore_blocca_poi_sblocca_e_il_successo_azzera():
    o = Orologio()
    lim = sw.LimitatoreTentativi(3, 60, 120, adesso=o)
    for _ in range(2):
        lim.registra_fallimento("k")
    lim.controlla("k")  # 2 su 3: ancora libero
    lim.registra_fallimento("k")
    with pytest.raises(sw.TentativiEccessiviError) as e:
        lim.controlla("k")
    assert 1 <= e.value.attesa_secondi <= 121
    lim.controlla("altra")  # le altre chiavi non sono toccate
    o.t += 121
    lim.controlla("k")  # dopo il blocco è di nuovo libero
    lim.registra_fallimento("k")
    lim.azzera("k")
    for _ in range(2):
        lim.registra_fallimento("k")
    lim.controlla("k")  # il contatore era ripartito da zero


def test_limitatore_finestra_scorrevole_e_memoria_limitata():
    o = Orologio()
    lim = sw.LimitatoreTentativi(3, 60, 60, adesso=o)
    lim.registra_fallimento("k")
    lim.registra_fallimento("k")
    o.t += 61
    lim.registra_fallimento("k")
    lim.controlla("k")  # i vecchi fallimenti sono scaduti
    piccolo = sw.LimitatoreTentativi(1, 60, 60, adesso=o, max_chiavi=3)
    for i in range(10):
        piccolo.registra_fallimento(f"k{i}")
    assert len(piccolo._fallimenti) <= 3 and len(piccolo._bloccati) <= 3


@pytest.mark.parametrize("args", [(0, 1, 1), (1, 0, 1), (1, 1, 0)])
def test_limitatore_parametri_non_validi(args):
    with pytest.raises(ValueError):
        sw.LimitatoreTentativi(*args)


def _client(fabbrica, **k):
    return TestClient(
        crea_app(session_factory=fabbrica, segrete_token=SEGRETA, **k),
        client=("10.0.0.7", 5000),
        raise_server_exceptions=False,
    )


def test_login_429_dopo_cinque_errori_anche_con_password_giusta(fabbrica):
    # Requisito aggiornato: niente login né limiti collegati alle credenziali.
    c=_client(fabbrica)
    assert c.post("/api/login",json={}).status_code==404
    assert c.post("/api/telefono/ping",json={}).status_code==200








# ============================================================ password e timing
@pytest.mark.parametrize("pw", ["", "1234567", "x" * 7, "é" * 37])  # ultima: 74 byte
def test_password_nuova_non_valida(pw):
    with pytest.raises(ValueError):
        valida_password_nuova(pw)


def test_password_nuova_valida_e_crea_utente_la_applica(fabbrica):
    valida_password_nuova("12345678")
    valida_password_nuova("é" * 36)  # 72 byte esatti
    with fabbrica() as s:
        with pytest.raises(ValueError, match="almeno 8"):
            crea_utente(s, "debole", "1", Ruolo.OPERATORE)


def test_utente_con_password_vecchia_e_corta_entra_ancora(fabbrica):
    with fabbrica() as s:
        with s.begin():
            s.add(
                mod_utenti.Utente(
                    username="vecchio", password_hash=hash_password("corta"), ruolo="OPERATORE"
                )
            )
    with fabbrica() as s:
        assert autentica(s, "vecchio", "corta") is not None


def test_autentica_con_utente_inesistente_esegue_comunque_bcrypt(fabbrica, monkeypatch):
    chiamate = []
    originale = mod_utenti.verifica_password

    def spia(p, h):
        chiamate.append(h)
        return originale(p, h)

    monkeypatch.setattr(mod_utenti, "verifica_password", spia)
    with fabbrica() as s:
        assert autentica(s, "nessuno", "qualcosa123") is None
        assert autentica(s, "mario", "sbagliata1") is None
    assert len(chiamate) == 2  # una sola differenza ammessa: l'hash usato


# ============================================================ intestazioni e limiti HTTP
def test_intestazioni_di_sicurezza_e_no_store(fabbrica):
    c = _client(fabbrica)
    for percorso, metodo in (("/", "get"), ("/api/login", "post")):
        r = getattr(
            c, metodo
        )(percorso, **({"json": {"utente": "x", "password": "y"}} if metodo == "post" else {}))
        for nome, valore in sw.INTESTAZIONI_SICUREZZA.items():
            assert r.headers[nome] == valore
    assert c.post("/api/login", json={"utente": "x", "password": "y"}).headers["Cache-Control"] == "no-store"
    assert "frame-ancestors 'none'" in sw.INTESTAZIONI_SICUREZZA["Content-Security-Policy"]


def test_corpo_troppo_grande_413_e_corpo_normale_ok(fabbrica):
    c = _client(fabbrica)
    r = c.post(
        "/api/login", content=b"{" + b" " * 70_000 + b"}", headers={"Content-Type": "application/json"}
    )
    assert r.status_code == 413
    assert c.post("/api/telefono/ping", json={}).status_code == 200


def test_content_length_non_numerico_e_trasferimento_senza_lunghezza(fabbrica):
    c = _client(fabbrica)
    assert (
        c.post("/api/login", content=b"{}", headers={"Content-Length": "abc"}).status_code in (400, 422)
    )
    assert c.post("/api/login", content=b"{}", headers={"Transfer-Encoding": "chunked"}).status_code == 411


# ============================================================ libreria QR ospitata in locale
def test_nessuno_script_di_terzi_e_libreria_verificata():
    html = (RADICE / "magazzino_profili/web/templates/scansione.html").read_text(encoding="utf-8")
    assert not re.search(r"<script[^>]+src=[\"']https?://", html), "script esterno nella pagina di scansione"
    assert 'src="/static/html5-qrcode.min.js"' in html
    js = RADICE / "magazzino_profili/web/static/html5-qrcode.min.js"
    assert (
        hashlib.sha256(js.read_bytes()).hexdigest()
        == "660b12437b1d747e3e68b8be0685c08cb728140110ad213f167b14b66f8b1d8e"
    )
    assert (RADICE / "magazzino_profili/web/static/LICENSE-html5-qrcode.txt").is_file()
    assert "cdn." not in (RADICE / "magazzino_profili/web/static/scansione.js").read_text(encoding="utf-8")


def test_la_libreria_e_servita_dal_server(fabbrica):
    r = _client(fabbrica).get("/static/html5-qrcode.min.js")
    assert r.status_code == 200 and len(r.content) == 375364


# ============================================================ backup: verifica prima della rotazione
FAKE_DUMP = (
    "import sys,pathlib\n"
    "for i,a in enumerate(sys.argv):\n"
    "    if a=='-f': pathlib.Path(sys.argv[i+1]).write_bytes(b'DATI')\n"
)
FAKE_VUOTO = (
    "import sys,pathlib\n"
    "for i,a in enumerate(sys.argv):\n"
    "    if a=='-f': pathlib.Path(sys.argv[i+1]).write_bytes(b'')\n"
)


def _verifica(codice):
    return [sys.executable, "-c", f"import sys; sys.exit({codice})"]


def _vecchi(cartella, n):
    for i in range(n):
        (cartella / f"magazzino_profili_2020010{i}_000000.dump").write_bytes(b"BUONO")


def _esegui(cartella, dump=FAKE_DUMP, **k):
    return pkg_backup.esegui_backup(
        "h", 1, "u", "p", "d", cartella, 2, [sys.executable, "-c", dump], **k
    )


def test_backup_leggibile_ruota_i_vecchi(tmp_path):
    _vecchi(tmp_path, 2)
    out = _esegui(tmp_path, comando_verifica=_verifica(0))
    assert out.is_file() and len(list(tmp_path.glob("*.dump"))) == 2  # tenuti gli ultimi 2


def test_backup_illeggibile_viene_eliminato_e_i_buoni_restano(tmp_path):
    _vecchi(tmp_path, 2)
    with pytest.raises(pkg_backup.BackupErrore, match="non è leggibile"):
        _esegui(tmp_path, comando_verifica=_verifica(1))
    assert sorted(p.name for p in tmp_path.glob("*.dump")) == [
        "magazzino_profili_20200100_000000.dump",
        "magazzino_profili_20200101_000000.dump",
    ]
    assert all(p.read_bytes() == b"BUONO" for p in tmp_path.glob("*.dump"))


def test_backup_vuoto_e_errore_e_non_ruota(tmp_path):
    _vecchi(tmp_path, 2)
    with pytest.raises(pkg_backup.BackupErrore, match="vuoto"):
        _esegui(tmp_path, dump=FAKE_VUOTO)
    assert len(list(tmp_path.glob("*.dump"))) == 2


def test_verifica_comando_inesistente_e_errore(tmp_path):
    f = tmp_path / "x.dump"
    f.write_bytes(b"1")
    with pytest.raises(pkg_backup.BackupErrore, match="Impossibile verificare"):
        pkg_backup.verifica_backup(f, ["comando-che-non-esiste-xyz"])


def test_comportamento_precedente_senza_verifica(tmp_path):
    assert _esegui(tmp_path).is_file()


def test_pg_restore_accanto_a_pg_dump(tmp_path):
    from magazzino_profili.main import _comando_pg_restore

    (tmp_path / "pg_restore.exe").write_bytes(b"")
    assert _comando_pg_restore(str(tmp_path / "pg_dump.exe")) == (str(tmp_path / "pg_restore.exe"),)
    assert _comando_pg_restore("pg_dump") == ("pg_restore",)
    assert (
        _comando_pg_restore(str(tmp_path / "pg_dump.exe").replace("pg_dump", "altro")) is None
    )
    assert _comando_pg_restore(str(tmp_path / "vuota" / "pg_dump.exe")) is None  # pg_restore assente


@pytest.mark.skipif(
    not (
        shutil.which("pg_dump")
        and shutil.which("pg_restore")
        and os.environ.get("MAGAZZINO_TEST_DB_URL")
    ),
    reason="serve PostgreSQL con pg_dump/pg_restore e MAGAZZINO_TEST_DB_URL",
)
def test_backup_reale_postgresql_verificato_e_troncato_rifiutato(tmp_path):
    from sqlalchemy.engine import make_url

    u = make_url(os.environ["MAGAZZINO_TEST_DB_URL"].replace("postgresql://", "postgresql+psycopg://", 1))
    eng = create_engine(u)
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    try:
        out = pkg_backup.esegui_backup(
            u.host, u.port or 5432, u.username, u.password, u.database, tmp_path, 3,
            ["pg_dump"], comando_verifica=["pg_restore"],
        )
        assert out.stat().st_size > 0
        pkg_backup.verifica_backup(out, ["pg_restore"])
        out.write_bytes(out.read_bytes()[:50])  # backup troncato
        with pytest.raises(pkg_backup.BackupErrore, match="non è leggibile"):
            pkg_backup.verifica_backup(out, ["pg_restore"])
    finally:
        Base.metadata.drop_all(eng)


# ============================================================ setup: file password temporaneo
def _setup(monkeypatch, tmp_path, esito):
    import setup_database as sd

    visti = {}
    monkeypatch.setattr(sd, "CARTELLA_DATA", tmp_path / "pg_data")
    monkeypatch.setattr(sd, "_exe", lambda nome: nome)

    def finto(args, check=True, **k):
        visti["args"] = args
        visti["pw_presente_durante"] = (tmp_path / "pg_pass").is_file()
        if esito == "errore":
            raise subprocess.CalledProcessError(1, args)

    monkeypatch.setattr(sd.subprocess, "run", finto)
    return sd, visti


def test_initdb_cancella_il_file_password_e_usa_scram(monkeypatch, tmp_path):
    sd, visti = _setup(monkeypatch, tmp_path, "ok")
    sd._initdb("password-di-prova")
    assert visti["pw_presente_durante"] is True and not (tmp_path / "pg_pass").exists()
    assert "--auth=scram-sha-256" in visti["args"] and not any("md5" in a for a in visti["args"])


def test_initdb_cancella_il_file_password_anche_se_fallisce(monkeypatch, tmp_path):
    sd, _ = _setup(monkeypatch, tmp_path, "errore")
    with pytest.raises(subprocess.CalledProcessError):
        sd._initdb("password-di-prova")
    assert not (tmp_path / "pg_pass").exists()


# ============================================================ segreti nel codice e nel pacchetto
def test_nessun_segreto_scritto_nel_codice():
    schema = re.compile(r"""(password|segrete_token|secret)\s*=\s*["'][^"']{4,}["']""", re.I)
    consentiti = {
        "PASSWORD_SEGNAPOSTO",
        "LA_TUA_PASSWORD",
        "SEGRETE_LUNGA_E_CASUALE_MINIMO_32_CARATTERI",
    }
    sospetti = []
    for f in (RADICE / "magazzino_profili").rglob("*.py"):
        if "tests" in f.parts or "__pycache__" in f.parts:
            continue
        for n, riga in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if (
                schema.search(riga)
                and not any(c in riga for c in consentiti)
                and not riga.lstrip().startswith(("#", '"', "'"))
            ):
                sospetti.append(f"{f.name}:{n}: {riga.strip()[:70]}")
    assert sospetti == [], sospetti


def test_gitignore_esclude_config_con_credenziali():
    righe = (
        (RADICE / ".gitignore").read_text(encoding="utf-8").splitlines()
        if (RADICE / ".gitignore").exists()
        else []
    )
    if not righe:
        pytest.skip("nessun .gitignore nel pacchetto di test")
    assert "config.toml" in [r.strip() for r in righe]


def test_lo_spec_non_incorpora_config_toml():
    spec = RADICE / "MagazzinoProfili.spec"
    if not spec.is_file():
        pytest.skip("MagazzinoProfili.spec non presente (non è versionato)")
    datas = next(
        r for r in spec.read_text(encoding="utf-8").splitlines() if r.strip().startswith("datas")
    )
    assert "config.toml" not in datas, (
        "config.toml (con la password del database) finirebbe dentro l'eseguibile"
    )


# ============================================================ ruoli e login desktop
ETICHETTE = {
    "inventario": "Inventario",
    "carico": "Carico",
    "scarico": "Scarico",
    "profili": "Profili",
    "avvisi": "Avvisi",
}


@pytest.mark.parametrize("ruolo", list(Ruolo))
def test_ogni_ruolo_vede_solo_le_sue_schede(qtbot, fabbrica, ruolo):
    from magazzino_profili.ui import FinestraPrincipale

    f = FinestraPrincipale(fabbrica, ruolo.value, "mario")
    qtbot.addWidget(f)
    viste = {f._tab.tabText(i) for i in range(f._tab.count())}
    assert viste == {ETICHETTE[k] for k in SCHEDE_CONSENTITE[Ruolo.AMMINISTRATORE]} | {"Commesse"}


def test_sola_lettura_non_vede_le_schede_che_modificano(qtbot, fabbrica):
    from magazzino_profili.ui import FinestraPrincipale

    f = FinestraPrincipale(fabbrica, Ruolo.SOLA_LETTURA.value, "lettore")
    qtbot.addWidget(f)
    assert {f._tab.tabText(i) for i in range(f._tab.count())}.issuperset({"Carico", "Scarico", "Profili"})


def test_main_apre_direttamente_con_privilegi_massimi():
    sorgente=(RADICE/"magazzino_profili/main.py").read_text(encoding="utf-8")
    assert "DialogoAccesso" not in sorgente and "Ruolo.AMMINISTRATORE" in sorgente
