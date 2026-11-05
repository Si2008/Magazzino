"""Regressioni dell'analisi: solo dati sintetici in cartelle pytest."""
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from magazzino_profili.db import crea_session_factory
from magazzino_profili.domain import Base, Profilo, Pezzo, Movimento
from magazzino_profili.services.pezzi_unitari import crea_pezzi_unitari, ricarica_barcode
from magazzino_profili.services import scarica

@pytest.fixture
def factory(tmp_path):
    engine=create_engine("sqlite:///"+str(tmp_path/"sintetico.db"))
    Base.metadata.create_all(engine)
    with Session(engine) as s, s.begin():
        s.add(Profilo(codice="ab12",descrizione="Profilo di prova",peso_kg_per_metro=1.2,lunghezza_standard_mm=6000))
    yield crea_session_factory(engine)
    engine.dispose()

def crea(factory, quantita=5):
    with factory() as s:
        return crea_pezzi_unitari(s,codice="ab12",colore="RAL7016",lunghezza_mm=6000,quantita=quantita,
            utente="test",causale="Prova",numero_vassoio="4",ubicazione="A")

def test_cinque_pezzi_cinque_barcode_senza_quantita(factory):
    pezzi=crea(factory)
    assert len({p.barcode for p in pezzi})==5
    assert all(p.barcode.startswith("MP-") and len(p.barcode)==35 for p in pezzi)
    assert all(p.quantita==1 and p.unitario and p.stato=="Caricato" and p.numero_vassoio=="4" for p in pezzi)
    with factory() as s:
        assert s.scalar(select(func.count()).select_from(Movimento))==5
        assert s.scalar(select(Profilo.codice))=="AB12"

def test_scarica_esattamente_il_pezzo_letto_e_rientra_stesso_barcode(factory):
    pezzi=crea(factory,2)
    with factory() as s: scarica(s,pezzi[0].barcode,1,"test","Uscita")
    with factory() as s:
        assert s.get(Pezzo,pezzi[0].id).quantita==0
        assert s.get(Pezzo,pezzi[1].id).quantita==1
    with factory() as s: ricarica_barcode(s,pezzi[0].barcode,1,"test","Rientro")
    with factory() as s:
        assert s.get(Pezzo,pezzi[0].id).quantita==1
        assert s.get(Pezzo,pezzi[0].id).barcode==pezzi[0].barcode
        assert s.get(Pezzo,pezzi[0].id).stato=="Caricato"

def test_rifiuta_doppio_carico_e_non_crea_movimenti(factory):
    p=crea(factory,1)[0]
    with factory() as s:
        with pytest.raises(ValueError,match="singolo pezzo"):
            ricarica_barcode(s,p.barcode,1,"test","Duplicato")
    with factory() as s:
        assert s.get(Pezzo,p.id).quantita==1
        assert s.scalar(select(func.count()).select_from(Movimento))==1

def test_scadenza_non_elimina_mai_quantita_positive_neppure_stato_errato(factory):
    from magazzino_profili.services.stati import lista_scaduti_per_eliminazione
    p=crea(factory,1)[0]
    now=datetime.now(timezone.utc)
    with factory() as s, s.begin():
        r=s.get(Pezzo,p.id);r.stato="Scaricato";r.data_ultimo_cambio_stato=now-timedelta(hours=49)
    with factory() as s:
        assert lista_scaduti_per_eliminazione(s,now=lambda:now)==[]

def test_scadenza_48_ore_utc_riapertura(factory):
    from magazzino_profili.services.stati import lista_scaduti_per_eliminazione
    p=crea(factory,1)[0]
    with factory() as s: scarica(s,p.barcode,1,"test","Uscita")
    t=datetime(2026,3,28,23,30,tzinfo=timezone.utc)
    with factory() as s, s.begin():s.get(Pezzo,p.id).data_ultimo_cambio_stato=t
    with factory() as s:assert lista_scaduti_per_eliminazione(s,now=lambda:t+timedelta(hours=48,microseconds=-1))==[]
    with factory() as s:assert lista_scaduti_per_eliminazione(s,now=lambda:t+timedelta(hours=48))==[p.id]

def test_snapshot_csv_e_ods_conservano_identita_unitaria(factory,tmp_path):
    from magazzino_profili.reports.formato_v2 import esporta_inventario_csv_v2,valida_csv_v2,importa_inventario_v2
    from magazzino_profili.reports.ods_v2 import esporta_inventario_ods_v2,valida_ods_v2
    pezzi=crea(factory,3)
    with factory() as s:esporta_inventario_csv_v2(s,tmp_path/"unitari.csv")
    with factory() as s:esporta_inventario_ods_v2(s,tmp_path/"unitari.ods")
    for risultato in (valida_csv_v2(tmp_path/"unitari.csv"),valida_ods_v2(tmp_path/"unitari.ods")):
        assert risultato.valido,risultato.errori
        assert all(r.unitario for r in risultato.righe)
        with factory() as s:assert importa_inventario_v2(s,risultato,"test")==3
    with factory() as s:assert s.scalar(select(func.count()).select_from(Movimento))==3

def test_backup_excel_preserva_seriali_multipli(factory,tmp_path):
    from magazzino_profili.reports.backup_excel import esporta_backup_logico_excel,valida_backup_logico_excel
    crea(factory,3)
    with factory() as s:esporta_backup_logico_excel(s,tmp_path/"completo.xlsx")
    b=valida_backup_logico_excel(tmp_path/"completo.xlsx")
    assert len(b.tabelle["Pezzi"])==3 and all(p["unitario"] for p in b.tabelle["Pezzi"])

def test_file_precedente_preservato_se_export_fallisce(tmp_path):
    from magazzino_profili.file_sicuri import destinazione_atomica
    file=tmp_path/"backup.xlsx";file.write_bytes(b"precedente")
    with pytest.raises(RuntimeError):
        with destinazione_atomica(file) as temporaneo:
            temporaneo.write_bytes(b"incompleto");raise RuntimeError("Simulazione")
    assert file.read_bytes()==b"precedente"
    assert list(tmp_path.iterdir())==[file]

def test_paginazione_limita_risultati(factory):
    from magazzino_profili.services.consultazione import cerca_pezzi
    crea(factory,220)
    with factory() as s:
        prima=cerca_pezzi(s,limite=200);seconda=cerca_pezzi(s,limite=200,offset=200)
        assert len(prima)==200 and len(seconda)==20
        assert not ({p.id for p in prima}&{p.id for p in seconda})
        assert cerca_pezzi(s,conteggio=True)==220

def test_sola_lettura_blocca_tutte_le_rettifiche(factory,qapp,monkeypatch):
    from magazzino_profili.ui.tabella_pezzi import TabellaPezzi
    p=crea(factory,1)[0]
    w=TabellaPezzi(factory,sola_lettura=True)
    w._tabella.selectRow(0)
    for azione in (lambda:w._imposta_stato("Scaricato"),w._elimina_barcode,w._modifica_barcode,w._imposta_vassoio):azione()
    with factory() as s:
        r=s.get(Pezzo,p.id);assert r.barcode==p.barcode and r.stato=="Caricato" and r.eliminato_il is None and r.numero_vassoio=="4"
    w.close()

def test_claim_destinatario_conferma_e_presenza(factory):
    from magazzino_profili.services.telefono import registra_scansione,prendi_scansioni,conferma_scansione,pc_collegato
    from magazzino_profili.domain import ScansioneTelefono
    a,b="a"*32,"b"*32
    with factory() as s:id_=registra_scansione(s,"mp-prova","test",destinatario=a)
    with factory() as s:assert prendi_scansioni(s,b)==[]
    with factory() as s:assert prendi_scansioni(s,a)==[(id_,"MP-PROVA")]
    with factory() as s:assert prendi_scansioni(s,a)==[]
    with factory() as s:assert pc_collegato(s,a)
    with factory() as s:assert s.get(ScansioneTelefono,id_).letta is False
    with factory() as s:assert conferma_scansione(s,id_,a,"compilata","Scheda compilata")
    with factory() as s:assert s.get(ScansioneTelefono,id_).esito=="compilata"


def test_scorta_per_materiale_non_per_numero_di_etichette(factory):
    from magazzino_profili.services import consultazione as c
    pezzi=crea(factory,20)
    with factory() as s:
        righe=c.cerca_pezzi(s,soglia_globale=5)
        assert all(c.stato_scorta(p,5)=="ok" for p in righe)
        assert c.pezzi_da_riordinare(s,5)==[]
    for p in pezzi[:16]:
        with factory() as s:scarica(s,p.barcode,1,"test","Uscita")
    with factory() as s:
        avvisi=c.pezzi_da_riordinare(s,5)
        assert len(avvisi)==1 and c.quantita_per_scorta(avvisi[0])==4
        assert c.riepilogo_inventario(s,5)["da_riordinare"]==1
        assert len(c.cerca_pezzi(s,stato="sotto",soglia_globale=5))==20


def test_conversione_conserva_totale_storico_e_blocca_piano_obsoleto(factory):
    from magazzino_profili.services import carica
    from magazzino_profili.services.pezzi_unitari import piano_conversione,converti_aggregati
    with factory() as s:storico=carica(s,"AB12","NERO",6000,5,"test","Storico")
    with factory() as s:piano=piano_conversione(s)
    with factory() as s:etichette=converti_aggregati(s,piano,"test")
    assert len(set(etichette))==5
    with factory() as s:
        assert s.get(Pezzo,storico.id).quantita==0
        assert s.scalar(select(func.sum(Pezzo.quantita)))==5
        assert s.scalar(select(func.count()).select_from(Movimento).where(Movimento.pezzo_id==storico.id))==2
    with factory() as s:
        with pytest.raises(ValueError,match="cambiate"):converti_aggregati(s,piano,"test")


def test_archivio_portabile_ripristina_immagini_e_barcode(factory,tmp_path):
    from PIL import Image
    from magazzino_profili.reports.archivio import esporta_archivio_dati,ripristina_archivio_dati
    origine=tmp_path/"sezione.png";Image.new("RGB",(8,8),"red").save(origine)
    with factory() as s,s.begin():s.scalar(select(Profilo)).immagine_sezione=str(origine)
    crea(factory,3)
    with factory() as s:esporta_archivio_dati(s,tmp_path/"backup.zip")
    nuovo=create_engine("sqlite:///"+str(tmp_path/"ripristino.db"));Base.metadata.create_all(nuovo)
    try:
        with Session(nuovo) as s:ripristina_archivio_dati(s,tmp_path/"backup.zip",modalita="db_vuoto",cartella_immagini=tmp_path/"immagini_ripristinate")
        with Session(nuovo) as s:
            p=s.scalar(select(Profilo));assert p.immagine_sezione!=str(origine)
            assert __import__("pathlib").Path(p.immagine_sezione).read_bytes()==origine.read_bytes()
            assert s.scalar(select(func.sum(Pezzo.quantita)))==3
            assert s.scalar(select(func.count()).select_from(Pezzo).where(Pezzo.unitario.is_(True)))==3
    finally:nuovo.dispose()


def test_catalogo_compare_su_profilo_storico_senza_modificare_db(factory,catalogo_isolato,qapp):
    from PIL import Image
    from magazzino_profili.services.immagini import immagine_del_profilo
    from magazzino_profili.ui.scheda_carico import SchedaCarico
    file=catalogo_isolato/"AB12.png";Image.new("RGB",(40,60),"white").save(file)
    with factory() as s:
        profilo=s.scalar(select(Profilo));assert profilo.immagine_sezione is None
        assert immagine_del_profilo(profilo)==file
    w=SchedaCarico(factory,"operatore");w.codice.setText("ab12")
    assert w._percorso_sezione==file and not w.immagine_sezione.pixmap().isNull()
    w.close()
    with factory() as s:assert s.scalar(select(Profilo)).immagine_sezione is None


def test_blocchi_indipendenti_per_cartelle_diverse(tmp_path):
    from magazzino_profili.file_sicuri import blocco_cartella
    import threading
    occupata,riparti,seconda=threading.Event(),threading.Event(),threading.Event()
    def a():
        with blocco_cartella(tmp_path/"backup"):
            occupata.set();riparti.wait(3)
    def b():
        with blocco_cartella(tmp_path/"immagini"):seconda.set()
    t1=threading.Thread(target=a);t1.start();assert occupata.wait(1)
    t2=threading.Thread(target=b);t2.start()
    try:assert seconda.wait(1),"Una copia immagine non deve attendere pg_dump in un'altra cartella"
    finally:riparti.set();t1.join(3);t2.join(3)


def test_backup_excel_ha_le_schede_del_programma_e_preserva_soglia(factory,tmp_path):
    from magazzino_profili.reports.backup_excel import esporta_backup_logico_excel,valida_backup_logico_excel
    from magazzino_profili.services.impostazioni import imposta_soglia
    from openpyxl import load_workbook
    crea(factory,3)
    with factory() as s:imposta_soglia(s,7)
    with factory() as s:esporta_backup_logico_excel(s,tmp_path/"programma.xlsx")
    wb=load_workbook(tmp_path/"programma.xlsx",read_only=True)
    try:
        assert {"Inventario","Carico","Scarico","Profili","Avvisi"}.issubset(wb.sheetnames)
        assert len(list(wb["Inventario"].rows))==4
    finally:wb.close()
    assert valida_backup_logico_excel(tmp_path/"programma.xlsx").soglia_scorta==7


def test_import_ods_unitario_non_inventa_peso_di_profili_sconosciuti(factory,tmp_path):
    from magazzino_profili.tests.test_importa_ods_fase7 import _ods,H
    from magazzino_profili.reports.importa_ods import importa_ods_file
    file=_ods(tmp_path/"sconosciuto.ods",[H,["NUOVO99","RAL7016",1,6000,2]])
    with factory() as s:
        with pytest.raises(ValueError,match="peso e lunghezza standard reali"):
            importa_ods_file(s,file,unitari=True)
    with factory() as s:
        assert s.scalar(select(func.count()).select_from(Profilo))==1
        assert s.scalar(select(func.count()).select_from(Pezzo))==0


def test_esportazione_legge_a_blocchi_senza_query_per_ogni_pezzo(factory):
    from sqlalchemy import insert,event
    from magazzino_profili.services.consultazione import itera_pezzi
    originale=crea(factory,1)[0]
    with factory() as s,s.begin():
        s.execute(insert(Pezzo),[dict(profilo_id=originale.profilo_id,colore_id=originale.colore_id,
            lunghezza_mm=6000,quantita=1,unitario=True,barcode=f"SERIALE-{i:08d}",stato="Caricato") for i in range(1200)])
    with factory() as s:
        query=[]
        def conta(conn,cursor,statement,parameters,context,executemany):query.append(statement)
        event.listen(s.get_bind(),"before_cursor_execute",conta)
        try:
            massimo=0;numero=0
            for pezzo in itera_pezzi(s):
                assert pezzo.profilo.codice=="AB12" and pezzo.colore.codice_normalizzato=="RAL7016"
                numero+=1;massimo=max(massimo,len(s.identity_map))
            assert numero==1201 and massimo<=550
            assert len(query)<=10,"Una SELECT per ogni barcode annullerebbe il vantaggio dei blocchi"
        finally:event.remove(s.get_bind(),"before_cursor_execute",conta)
