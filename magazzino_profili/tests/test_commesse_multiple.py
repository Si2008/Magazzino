"""Archivio, omonimie, invio e collegamenti: solo dati sintetici."""
import hashlib,json
from dataclasses import replace
import pytest
from sqlalchemy import select,func
from magazzino_profili.tests.test_correzioni_dati import factory,crea
from magazzino_profili.services import archivio_commesse as a,sincronizza_commesse as rete
from magazzino_profili.services.lettura_commessa import DocumentoCommessa,estrai_cognome
from magazzino_profili.services.commesse import RichiestaTaglio,calcola_prelievo
from magazzino_profili.domain import Commessa,RigaCommessa,AssegnazioneCommessa,Movimento


def documento(nome='Esempio',identita='a',profilo='AB12',colore='RAL7016'):
    return DocumentoCommessa('Ordine prova',[RichiestaTaglio(profilo,colore,10000,2)],cognome=nome,impronta=hashlib.sha256(identita.encode()).hexdigest())


def test_cognome_letto_e_obbligatorio():
    assert estrai_cognome('Ordine: 26 ESEMPIO - Rif. Esempio\nCliente 67')=='Esempio'
    assert estrai_cognome('Cognome: D’Amico Rossi\n')=='D’Amico Rossi'
    for testo in ['Cliente: 67','Rif.\nCliente 67','Cognome:   \n']:
        with pytest.raises(ValueError,match='cognome'):estrai_cognome(testo)


def test_codici_e_colori_originali_senza_catalogo(factory):
    d=documento(profilo='profilo speciale α / senza cifre',colore='RAF - 9010 Soft')
    c,nuova=a.importa(factory,d)
    riletta=a.carica(factory,c.identita)
    assert nuova and riletta.righe==d.righe and riletta.cognome=='Esempio'


def test_reimportazione_omonimo_e_nessuna_sovrascrittura(factory):
    d=documento();c,_=a.importa(factory,d)
    assert a.importa(factory,replace(d,nome='file rinominato'))[1] is False
    altra=documento(nome='ESEMPIO',identita='b')
    with pytest.raises(a.CognomePresente):a.importa(factory,altra)
    assert len(a.elenco(factory))==1
    c2,_=a.importa(factory,altra,accetta_omonimo=True)
    assert c2.id!=c.id and len(a.elenco(factory))==2
    assert a.carica(factory,c.identita).righe==d.righe


def test_identita_stessa_con_dati_diversi_rifiutata(factory):
    d=documento();a.importa(factory,d)
    with pytest.raises(ValueError,match='contenuto diverso'):a.importa(factory,replace(d,righe=[RichiestaTaglio('Altro','Blu',10000,1)]))
    assert len(a.elenco(factory))==1


@pytest.mark.parametrize('dati',[b'{}',b'[]',b'{"formato":99}',b'errore',b'\xff'])
def test_pacchetti_malformati_non_modificano_db(factory,dati):
    with pytest.raises(ValueError):a.documento(dati)
    assert a.elenco(factory)==[]


def test_offline_invii_e_ricevute_durevoli(tmp_path):
    locale=a.ArchivioLocale(tmp_path/'pc_secondario');d=documento();locale.salva(d)
    with pytest.raises(OSError):rete.invia(locale,tmp_path/'principale_spento')
    assert len(locale.elenco())==1
    share=tmp_path/'rete';share.mkdir()
    assert 'in attesa' in rete.invia(locale,share)[0]
    assert len(rete.da_ricevere(share))==1
    rete.invia(locale,share);assert len(rete.da_ricevere(share))==1
    rete.conferma(share,d,'ricevuta')
    assert 'ricevuta' in rete.invia(locale,share)[0] and not rete.da_ricevere(share)


def test_omonimie_archivio_secondario(tmp_path):
    locale=a.ArchivioLocale(tmp_path/'locale');d=documento();assert locale.salva(d)
    assert not locale.salva(d)
    with pytest.raises(a.CognomePresente):locale.salva(documento(identita='b'))
    assert locale.salva(documento(identita='b'),accetta_omonimo=True)
    assert len(locale.elenco())==2


def test_assegnazione_persistente_inventario_carico_scarico(factory):
    from magazzino_profili.services.consultazione import pezzo_per_barcode,cerca_pezzi
    from magazzino_profili.services.scarico import scarica
    from magazzino_profili.services.pezzi_unitari import crea_pezzi_unitari
    d=documento();c,_=a.importa(factory,d)
    with factory() as s:
        p=crea_pezzi_unitari(s,codice='AB12',colore='RAL7016',lunghezza_mm=6000,quantita=1,numero_vassoio='4',utente='test',causale='Commessa',commessa_id=c.id)[0]
    with factory() as s:assert pezzo_per_barcode(s,p.barcode)._commessa_cognome=='Esempio'
    with factory() as s:scarica(s,p.barcode,1,'test','Uscita')
    with factory() as s:
        assert cerca_pezzi(s)[0]._commessa_cognome=='Esempio'
        assert s.scalar(select(func.count()).select_from(AssegnazioneCommessa))==1
        assert s.scalar(select(func.count()).select_from(Movimento))==2


def test_prelievo_non_prende_pezzi_di_altra_commessa(factory):
    crea(factory,1);d=documento();c,_=a.importa(factory,d)
    c2,_=a.importa(factory,documento(nome='Rossi',identita='b'))
    with factory() as s:piano=calcola_prelievo(s,d.righe,commessa_id=c.id)
    a.assegna_piano(factory,c.identita,piano)
    with factory() as s:
        assert calcola_prelievo(s,d.righe,commessa_id=c2.id).mancanti
        assert not calcola_prelievo(s,d.righe,commessa_id=c.id).mancanti


def test_backup_ripristina_commesse_e_associazioni(factory,tmp_path):
    from magazzino_profili.reports.backup_excel import esporta_backup_logico_excel,valida_backup_logico_excel,ripristina_backup_logico_excel
    d=documento();a.importa(factory,d);crea(factory,1)
    with factory() as s:p=calcola_prelievo(s,d.righe)
    a.assegna_piano(factory,d.impronta,p)
    with factory() as s:out=esporta_backup_logico_excel(s,tmp_path/'completo.xlsx')
    b=valida_backup_logico_excel(out)
    assert len(b.tabelle['Commesse'])==1 and len(b.tabelle['RigheCommesse'])==1
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from magazzino_profili.domain import Base
    e=create_engine('sqlite:///'+str(tmp_path/'ripristino_sintetico.db'));Base.metadata.create_all(e)
    with Session(e) as s:ripristina_backup_logico_excel(s,b,modalita='db_vuoto')
    with Session(e) as s:
        assert s.scalar(select(func.count()).select_from(AssegnazioneCommessa))==1
        assert s.scalar(select(Commessa.cognome))=='Esempio'
    e.dispose()


def test_ui_colore_immutabile_e_commesse_multiple(factory,qtbot):
    from magazzino_profili.ui.scheda_commesse import SchedaCommesse
    a.importa(factory,documento());a.importa(factory,documento(nome='Rossi',identita='b'))
    w=SchedaCommesse(factory,lambda *_:None);qtbot.addWidget(w)
    assert w.elenco_commesse.count()==2
    w._apri_salvata()
    assert w.tabella.cellWidget(0,2) is None and w.tabella.item(0,1).text()=='RAL7016'
    assert w.tabella.editTriggers()==w.tabella.EditTrigger.NoEditTriggers
    w.elenco_commesse.setCurrentIndex(1);w._apri_salvata()
    assert w._documento.cognome=='Rossi'


def test_secondario_non_apre_database(monkeypatch,qapp):
    from magazzino_profili import main as avvio
    from magazzino_profili.services import postazione
    from magazzino_profili.ui import postazione as ui
    from PySide6.QtCore import QTimer
    monkeypatch.setattr(avvio,'_configura_log',lambda:None)
    monkeypatch.setattr(postazione,'impostazioni',lambda:('secondario',''))
    monkeypatch.setattr(avvio,'leggi_config',lambda:pytest.fail('Il secondario non deve leggere il database'))
    monkeypatch.setattr(QTimer,'singleShot',lambda *_:None)
    monkeypatch.setattr(qapp,'exec',lambda:0)
    class Finta:
        def show(self):pass
    creata=[]
    monkeypatch.setattr(ui,'FinestraSecondaria',lambda: creata.append(Finta()) or creata[-1])
    assert avvio.main()==0
    assert len(creata)==1


def test_avvio_secondario_senza_config_apre_la_finestra_completa(monkeypatch,qapp):
    from magazzino_profili import main as avvio
    from magazzino_profili.services import postazione
    from magazzino_profili.ui import postazione as ui
    from PySide6.QtCore import QTimer
    monkeypatch.setattr(avvio,'_configura_log',lambda:None)
    monkeypatch.setattr(postazione,'impostazioni',lambda:('secondario',''))
    monkeypatch.setattr(postazione,'configurazione_database',lambda:'')
    monkeypatch.setattr(avvio,'leggi_config',lambda:pytest.fail('Il secondario non deve richiedere config.toml'))
    monkeypatch.setattr(QTimer,'singleShot',lambda *_:None)
    monkeypatch.setattr(qapp,'exec',lambda:0)
    creata=[]
    originale=ui.FinestraSecondaria
    monkeypatch.setattr(ui,'FinestraSecondaria',lambda:creata.append(originale()) or creata[-1])
    assert avvio.main()==0
    assert len(creata)==1 and creata[0]._factory is None
    assert [creata[0]._tab.tabText(i) for i in range(creata[0]._tab.count())]==[
        'Inventario','Carico','Scarico','Avvisi','Commesse']


def test_config_principale_rifiuta_file_assente_o_invalido(tmp_path):
    from magazzino_profili.services.postazione import valida_configurazione_database
    with pytest.raises(Exception,match='config.toml non trovato'):
        valida_configurazione_database(tmp_path/'assente.toml')
    invalido=tmp_path/'invalido.toml';invalido.write_text('[web]\nporta=1234\n',encoding='utf-8')
    with pytest.raises(Exception,match=r'sezione \[database\]'):
        valida_configurazione_database(invalido)
    valido=tmp_path/'valido.toml'
    valido.write_text('[database]\nhost="127.0.0.1"\nporta=5432\nutente="test"\npassword="test"\ndbname="magazzino"\n',encoding='utf-8')
    assert valida_configurazione_database(valido)==valido.resolve()


def test_secondario_usa_la_stessa_finestra_e_navigazione_senza_database(qapp,qtbot):
    from magazzino_profili.ui.postazione import FinestraSecondaria
    from magazzino_profili.ui.finestra_principale import FinestraPrincipale
    w=FinestraSecondaria();qtbot.addWidget(w)
    assert isinstance(w,FinestraPrincipale)
    assert [w._tab.tabText(i) for i in range(w._tab.count())]==[
        'Inventario','Carico','Scarico','Avvisi','Commesse']
    assert w._factory is None and w._secondario
    assert w.windowTitle().endswith('PC secondario')
    assert w._materializza_pagina('scheda_commesse')._locale is not None
    assert w._pagina_pronta('scheda_inventario') is not None
    w._esegui_cambio_tema()
    assert w._tab.count()==5 and w._secondario


def test_nome_colore_esatto_e_univoco_senza_cambiare_la_commessa(factory):
    from magazzino_profili.domain import Colore
    p=crea(factory,1)[0]
    with factory() as s,s.begin():s.get(Colore,p.colore_id).nome_visualizzato='RAF - 9010 Soft'
    d=documento(colore='RAF - 9010 Soft')
    with factory() as s:
        piano=calcola_prelievo(s,d.righe)
        assert not piano.mancanti and piano.prelievi[0].materiale.colore=='RAF - 9010 Soft'
    assert d.righe[0].colore=='RAF - 9010 Soft'
    with factory() as s,s.begin():s.add(Colore(codice_normalizzato='ALTRO',nome_visualizzato='RAF - 9010 Soft'))
    with factory() as s:assert calcola_prelievo(s,d.righe).mancanti


def test_backup_vecchio_formato_tre_senza_commesse_resta_leggibile(factory,tmp_path):
    from magazzino_profili.reports import backup_excel as be
    from openpyxl import load_workbook
    with factory() as s:out=be.esporta_backup_logico_excel(s,tmp_path/'vecchio.xlsx')
    wb=load_workbook(out)
    for nome in ['Commesse','RigheCommesse','AssegnazioniCommesse']:del wb[nome]
    for r in wb['Metadati'].iter_rows():
        if r[0].value=='versione_formato':r[1].value=3
    wb.save(out);wb.close()
    validato=be.valida_backup_logico_excel(out)
    assert validato.tabelle['Commesse']==() and validato.tabelle['RigheCommesse']==()


def test_invii_rifiutati_ripubblicati_e_omonimie_riprese(tmp_path):
    locale=a.ArchivioLocale(tmp_path/'locale');d=documento();locale.salva(d)
    share=tmp_path/'rete';share.mkdir();rete.invia(locale,share)
    rete.rifiuta(share,d.impronta+'.json','File non valido')
    assert not rete.da_ricevere(share)
    assert 'reinviato' in rete.invia(locale,share)[0]
    assert len(rete.da_ricevere(share))==1
    rete.conferma(share,d,'in attesa di conferma omonimia')
    assert len(rete.da_ricevere(share))==1
    rete.conferma(share,d,'ricevuta')
    assert not rete.da_ricevere(share)
