"""API mobile su SQLite sintetico; nessuna configurazione operativa."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,select,func
from magazzino_profili.db import crea_session_factory
from magazzino_profili.domain import Base,Pezzo,Profilo,Movimento
from magazzino_profili.sicurezza import crea_utente,Ruolo
from magazzino_profili.web.app import crea_app

@pytest.fixture
def ambiente(tmp_path):
    engine=create_engine("sqlite:///"+str(tmp_path/"web-test.db"),connect_args={"check_same_thread":False})
    Base.metadata.create_all(engine);factory=crea_session_factory(engine)
    with factory() as s:
        crea_utente(s,"admin","Password123!",Ruolo.AMMINISTRATORE)
        crea_utente(s,"lettura","Password123!",Ruolo.SOLA_LETTURA)
        s.add(Profilo(codice="AB12",descrizione="Profilo",peso_kg_per_metro=1.2,lunghezza_standard_mm=6000));s.commit()
    with TestClient(crea_app(session_factory=factory,segrete_token="segreto-test-casuale-abbastanza-lungo-1234567890")) as client:
        yield client,factory,{}
    engine.dispose()

def dati():return dict(richiesta_id="crea-uno",codice_profilo="ab12",colore="RAL7016",lunghezza_mm=6000,quantita=3,numero_vassoio="4",ubicazione="A",causale="Prova")


def test_cors_solo_pagina_pubblicata_vercel(ambiente):
    c,_,_=ambiente
    origine='https://magazzino-profili-telefono.vercel.app'
    r=c.options('/api/pezzi',headers={'Origin':origine,'Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'content-type'})
    assert r.status_code==200 and r.headers['access-control-allow-origin']==origine
    r=c.options('/api/pezzi',headers={'Origin':'https://altro.example','Access-Control-Request-Method':'POST'})
    assert r.status_code==400 and 'access-control-allow-origin' not in r.headers

def test_creazione_unitaria_retry_immagine_e_scarico(ambiente):
    c,f,h=ambiente
    a=c.post("/api/pezzi",json=dati(),headers=h);assert a.status_code==200,a.text
    pezzi=a.json()["pezzi"];assert len(pezzi)==3 and len({p["barcode"] for p in pezzi})==3
    b=c.post("/api/pezzi",json=dati(),headers=h);assert b.json()==a.json()
    with f() as s:assert s.scalar(select(func.count()).select_from(Pezzo))==3
    barcode=pezzi[0]["barcode"]
    png=c.get("/api/barcode/"+barcode+"/immagine",headers=h);assert png.status_code==200 and png.content.startswith(b"\x89PNG")
    payload=dict(richiesta_id="scarica-uno",barcode=barcode,quantita=1,causale="Uscita")
    uscita=c.post("/api/scarico",json=payload,headers=h);assert uscita.status_code==200,uscita.text
    assert uscita.json()["stato"]=="Scaricato" and uscita.json()["quantita_giacenza"]==0
    assert c.post("/api/scarico",json=payload,headers=h).json()==uscita.json()
    with f() as s:
        assert s.scalar(select(func.count()).select_from(Movimento))==4
        assert s.scalar(select(func.sum(Pezzo.quantita)))==2

def test_stessa_chiave_con_dati_diversi_rifiutata(ambiente):
    c,f,h=ambiente
    assert c.post("/api/pezzi",json=dati(),headers=h).status_code==200
    x=dati();x["quantita"]=5
    assert c.post("/api/pezzi",json=x,headers=h).status_code==409
    with f() as s:assert s.scalar(select(func.count()).select_from(Pezzo))==3

def test_quantita_non_intera_rifiutata_e_accesso_libero(ambiente):
    c,f,h=ambiente
    x=dati();x["quantita"]=1.5
    assert c.post("/api/pezzi",json=x).status_code==422
    assert c.post("/api/pezzi",json=dati()).status_code==200
    with f() as s:assert s.scalar(select(func.count()).select_from(Pezzo))==3

def test_pagina_mobile_risorse_locali_e_stato_servizio(ambiente):
    c,_,_=ambiente
    r=c.get("/?pc="+"a"*32);assert r.status_code==200
    assert 'id="form-nuovo"' in r.text and 'id="form-manuale"' in r.text
    assert c.get("/static/telefono.css").status_code==200
    assert c.get("/static/scansione.js").status_code==200
    assert c.get("/api/salute").json()["database_disponibile"] is True


def test_immagine_compare_automaticamente_nel_catalogo_mobile(ambiente,catalogo_isolato):
    from PIL import Image
    c,f,_=ambiente
    file=catalogo_isolato/"AB12.png";Image.new("RGB",(16,16),"white").save(file)
    profili=c.get("/api/profili?cerca=ab12").json()
    assert profili[0]["url_immagine"]=="/api/profili/AB12/sezione"
    risposta=c.get(profili[0]["url_immagine"])
    assert risposta.status_code==200 and risposta.content==file.read_bytes()
    assert c.post("/api/pezzi",json=dati()).status_code==200
    assert c.get(profili[0]["url_immagine"]).content==file.read_bytes()
    with f() as s:assert s.scalar(select(Profilo)).immagine_sezione is None


def test_vecchio_qr_dopo_riavvio_non_lascia_scansione_in_attesa_per_sempre(ambiente):
    from datetime import datetime,timedelta,timezone
    from magazzino_profili.domain import ScansioneTelefono
    c,f,_=ambiente
    r=c.post("/api/scansione",json={"barcode":"MP-TEST","destinatario":"a"*32,"richiesta_id":"vecchio-qr"})
    assert r.status_code==200
    with f() as s,s.begin():s.get(ScansioneTelefono,r.json()["id"]).creata_il=datetime.now(timezone.utc)-timedelta(minutes=3)
    esito=c.get("/api/scansioni/"+str(r.json()["id"])).json()
    assert esito["esito"]=="scaduta" and "nuovo QR" in esito["dettaglio"]


def test_caratteri_di_controllo_non_arrivano_al_database(ambiente):
    c,_,_=ambiente
    r=c.post("/api/scansione",json={"barcode":"MP-\u0000-TEST"})
    assert r.status_code==422 and "controllo" in r.json()["detail"]
