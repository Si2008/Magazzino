import pytest
from PySide6.QtGui import QColor
from sqlalchemy import select
from magazzino_profili.domain import Colore
from magazzino_profili.tests.test_correzioni_dati import factory,crea
from magazzino_profili.ui import gestione_colori,registro_colori


def test_tonalita_scelta_salvata_e_annullamento_non_modifica(factory,qapp,monkeypatch):
    crea(factory,1)
    with factory() as s:registro_colori.ricarica_da_database(s)
    monkeypatch.setattr(gestione_colori.QColorDialog,'getColor',lambda *args:QColor('#345678'))
    gestione_colori.scegli_colore(None,factory,'RAL7016')
    with factory() as s:assert s.scalar(select(Colore.colore_hex))=='#345678'
    assert registro_colori.registro().swatch('RAL7016').colori==('#345678',)
    monkeypatch.setattr(gestione_colori.QColorDialog,'getColor',lambda *args:QColor())
    gestione_colori.scegli_colore(None,factory,'RAL7016')
    with factory() as s:assert s.scalar(select(Colore.colore_hex))=='#345678'


def test_ponte_accetta_solo_api_del_magazzino():
    from magazzino_profili.services.percorsi_remoti import percorso_api_consentito
    assert percorso_api_consentito('POST','/api/scarico')
    assert percorso_api_consentito('GET','/api/pezzi/MP-TEST')
    assert not percorso_api_consentito('POST','/update/file.exe')
    assert not percorso_api_consentito('GET','http://127.0.0.1:80/api/salute')
    assert not percorso_api_consentito('GET','/static/config.toml')


def test_ponte_inoltra_idempotenza_e_non_apre_percorsi_arbitrari(monkeypatch):
    import json,base64
    from magazzino_profili.ui import ponte_vercel as ponte
    risposte=[];richieste=[]
    dati={'richiesta_id':'stessa-richiesta','barcode':'MP-TEST','quantita':1,'causale':'Prova'}
    def json_finto(url,corpo=None):
        if corpo is not None:risposte.append(corpo);return {'ok':True}
        return {'lavori':[{'id':'job1','metodo':'POST','percorso':'/api/scarico','dati':dati},
                          {'id':'job2','metodo':'GET','percorso':'/static/config.toml'},
                          {'id':'job3','metodo':'POST','percorso':'/api/scarico','dati':dati,'scadenza':1}]}
    class Risposta:
        status=200;headers={'Content-Type':'application/json'}
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,n):return b'{"quantita_giacenza":0}'
    def apri(req,**kwargs):richieste.append(req);return Risposta()
    monkeypatch.setattr(ponte,'_json',json_finto)
    monkeypatch.setattr(ponte.urllib.request,'urlopen',apri)
    ponte.esegui_giro('http://127.0.0.1:9876','a'*32)
    assert len(richieste)==1 and richieste[0].full_url=='http://127.0.0.1:9876/api/scarico'
    assert json.loads(richieste[0].data)==dati
    assert len(risposte)==1 and risposte[0]['id']=='job1'
    assert json.loads(base64.b64decode(risposte[0]['contenuto']))['quantita_giacenza']==0


def test_pulsante_telefono_avvia_ponte_e_qr_vercel(factory,qapp,monkeypatch):
    from magazzino_profili.ui import finestra_principale as ui
    from magazzino_profili.services.collegamento_remoto import PAGINA_TELEFONO
    from urllib.parse import urlsplit,parse_qs
    w=ui.FinestraPrincipale(factory,'AMMINISTRATORE','operatore')
    w._server_telefono.origine_locale='http://127.0.0.1:9876';collegamenti=[];url=[]
    monkeypatch.setattr(w,'_avvia_server_telefono',lambda:None)
    monkeypatch.setattr(w._server_telefono.ponte,'avvia',lambda *args:collegamenti.append(args))
    monkeypatch.setattr(w._controllo_telefono,'avvia',lambda:None)
    monkeypatch.setattr(ui.servizio_telefono,'leggi_url_pubblico',lambda:None)
    class Dialogo:
        def __init__(self,controllo,indirizzo,parent):url.append(indirizzo)
        def exec(self):return 0
        def deleteLater(self):pass
    monkeypatch.setattr(ui,'DialogoTelefono',Dialogo)
    w._apri_dialogo_telefono()
    assert collegamenti==[('http://127.0.0.1:9876',w._controllo_telefono.destinatario)]
    assert url[0].startswith(PAGINA_TELEFONO)
    assert parse_qs(urlsplit(url[0]).query)=={'pc':[w._controllo_telefono.destinatario]}
    w.close()
