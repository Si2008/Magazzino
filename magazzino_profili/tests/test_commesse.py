"""Regressioni commesse: solo inventario sintetico, nessuna base operativa."""
import pytest
from sqlalchemy import select, func
from magazzino_profili.services.commesse import (RichiestaTaglio, Materiale, decimi,
    misura, pianifica, calcola_prelievo)
from magazzino_profili.services.lettura_commessa import quote_da_testo, leggi_commessa_pdf
from magazzino_profili.tests.test_correzioni_dati import factory, crea
from magazzino_profili.domain import Pezzo, Movimento, Spezzone


def richiesta(lunghezza, quantita=1, profilo='AB12', colore='RAL7016', **kw):
    return RichiestaTaglio(profilo,colore,decimi(lunghezza),quantita,**kw)


def materiale(n, lunghezza, profilo='AB12', colore='RAL7016'):
    return Materiale(str(n),profilo,colore,decimi(lunghezza),f'BC-{n}',f'V{n}','A')


def test_piu_tagli_sullo_stesso_barcode_e_decimal_esatti():
    p=pianifica([richiesta('632,8',3)],[materiale(1,2000)])
    assert not p.mancanti and len(p.prelievi)==1 and len(p.prelievi[0].tagli)==3
    assert p.prelievi[0].residuo==1016
    assert misura(6328)=='632,8'


def test_preferisce_spezzone_e_non_riusa_materiale_per_altro_profilo_colore():
    p=pianifica([richiesta(1000,3)],[materiale(1,2200),materiale(2,6500),materiale(3,1500,colore='RAL9010'),materiale(4,1500,profilo='ZZ9')])
    assert [x.materiale.barcode for x in p.prelievi]==['BC-1','BC-2']
    assert len(p.prelievi[0].tagli)==2


def test_pezzo_esatto_non_riusa_barcode():
    p=pianifica([richiesta(1000,2)],[materiale(1,1000)])
    assert len(p.prelievi)==1 and p.prelievi[0].residuo==0
    assert p.mancanti[0].quantita==1


def test_sceglie_per_le_sole_misure_nominali_e_rifiuta_pezzo_troppo_corto():
    p=pianifica([richiesta(1990)],[materiale(1,2000)])
    assert len(p.prelievi)==1 and p.prelievi[0].residuo==100
    assert not pianifica([richiesta(2001)],[materiale(1,2000)]).prelievi


def test_modalita_esatta_e_barra_intera_non_condivisa():
    p=pianifica([richiesta(1000)],[materiale(1,2000)],consenti_pezzi_lunghi=False)
    assert p.mancanti
    p=pianifica([richiesta(1000,barra_intera=True),richiesta(500)],[materiale(1,2000)])
    assert len(p.prelievi)==1 and p.prelievi[0].chiuso and p.mancanti


@pytest.mark.parametrize('valore',['NaN','Infinity','0','-1','1.23','1e9','testo'])
def test_misure_non_valide(valore):
    with pytest.raises(ValueError):decimi(valore)


def test_limiti_e_materiali_duplicati():
    with pytest.raises(ValueError):pianifica([richiesta(1000,10000),richiesta(1000)],[materiale(1,6000)])
    with pytest.raises(ValueError,match='duplicato'):pianifica([richiesta(1000)],[materiale(1,6000),materiale(1,6000)])
    with pytest.raises(ValueError):richiesta(1000,0)


def test_query_solo_attivi_non_scaricati_non_eliminati_e_sola_lettura(factory):
    pezzi=crea(factory,4)
    with factory() as s,s.begin():
        s.get(Pezzo,pezzi[0].id).stato='Scaricato'  # anche se saldo incoerentemente positivo
        s.get(Pezzo,pezzi[1].id).quantita=0
        from datetime import datetime,timezone
        s.get(Pezzo,pezzi[2].id).eliminato_il=datetime.now(timezone.utc)
    with factory() as s:
        movimenti=s.scalar(select(func.count()).select_from(Movimento))
        p=calcola_prelievo(s,[richiesta(6000,2)])
        assert len(p.prelievi)==1 and p.prelievi[0].materiale.barcode==pezzi[3].barcode
        assert p.prelievi[0].materiale.vassoio=='4' and p.mancanti[0].quantita==1
        assert s.scalar(select(func.count()).select_from(Movimento))==movimenti
        assert not s.dirty and not s.new and not s.deleted


def test_spezzone_storico_posizione_da_confermare_e_non_doppio_con_origine(factory):
    pezzi=crea(factory,2)
    with factory() as s,s.begin():
        s.get(Pezzo,pezzi[0].id).quantita=0;s.get(Pezzo,pezzi[0].id).stato='Scaricato'
        s.add_all([Spezzone(pezzo_origine_id=x.id,lunghezza_mm=2000,utente='test') for x in pezzi])
    with factory() as s:
        p=calcola_prelievo(s,[richiesta(1800,2)])
        assert len(p.prelievi)==2
        residui=[x for x in p.prelievi if x.materiale.chiave.startswith('spezzone:')]
        assert len(residui)==1 and residui[0].materiale.vassoio=='Da confermare'
        assert all(not x.utilizzato for x in s.scalars(select(Spezzone)))


def test_quote_ocr_decimal_diviso_e_caratteri_incerti():
    assert quote_da_testo('347. 8 217.8_217.8')==[3478,2178,2178]
    with pytest.raises(ValueError):quote_da_testo('12O0')


def finto_pdf(monkeypatch,tmp_path,*,attese=2,quote='1200 1200',ocr_errore=False):
    import pypdf
    from PIL import Image
    class Immagine: image=Image.new('RGB',(1200,56),'white')
    class Pagina:
        images={'/img1':Immagine()}
        def __init__(self,eventi):self.eventi=eventi
        def extract_text(self,visitor_text=None,visitor_operand_before=None):
            if visitor_text is None:return 'Ordine: 1 Esempio - Rif. Esempio\n'
            for tipo,v in self.eventi:
                if tipo=='t':visitor_text(v,None,None,None,None)
                else:visitor_operand_before(b'Do',[v],None,None)
    # Seconda barra nella pagina successiva: non perderla, non deduplicarla.
    intestazione=[('t',v) for v in ['LISTA OTTIMIZZATA','Profilo','AB12','Colore','RAL7016',f'{attese} Ut.']]
    barra=[('i','/img1'),('t','6500'),('t','2420')]
    class Lettore:
        is_encrypted=False
        pages=[Pagina(intestazione+barra),Pagina(barra)]
    monkeypatch.setattr(pypdf,'PdfReader',lambda _:Lettore())
    pdf=tmp_path/'sintetico.pdf';pdf.write_bytes(b'%PDF-sintetico')
    def riconosci(cartella):
        if ocr_errore:raise RuntimeError('OCR assente')
        return {p.name:quote for p in cartella.glob('*.png')}
    return pdf,riconosci


def test_pdf_continuazione_quantita_diagrammi_e_nessuna_moltiplicazione_abaco(monkeypatch,tmp_path):
    pdf,ocr=finto_pdf(monkeypatch,tmp_path)
    d=leggi_commessa_pdf(pdf,riconoscitore=ocr)
    assert d.barre_originali==2 and len(d.righe)==1 and d.righe[0].quantita==4


def test_pdf_quote_incoerenti_o_ocr_assente_blocca_senza_indovinare(monkeypatch,tmp_path):
    pdf,ocr=finto_pdf(monkeypatch,tmp_path,quote='120')
    with pytest.raises(ValueError):leggi_commessa_pdf(pdf,riconoscitore=ocr)
    pdf,ocr=finto_pdf(monkeypatch,tmp_path,ocr_errore=True)
    with pytest.raises(ValueError):leggi_commessa_pdf(pdf,riconoscitore=ocr)


def test_pdf_incompleto_blocca_importazione(monkeypatch,tmp_path):
    pdf,ocr=finto_pdf(monkeypatch,tmp_path,attese=3)
    with pytest.raises(ValueError,match='dichiarate 3'):leggi_commessa_pdf(pdf,riconoscitore=ocr)


def test_ui_revisione_mappatura_colore_e_invalidazione(factory,qtbot):
    crea(factory,1)
    from magazzino_profili.ui.scheda_commesse import SchedaCommesse
    from magazzino_profili.services.lettura_commessa import DocumentoCommessa
    def avvia(titolo,azione,completato=None):
        valore=azione()
        if completato:completato(valore)
    w=SchedaCommesse(factory,avvia);qtbot.addWidget(w)
    d=DocumentoCommessa('Prova',[richiesta(1000),richiesta(2000)])
    w._mostra_documento(d,'non_aprire.pdf')
    assert not w.calcola.isEnabled()
    assert w.tabella.cellWidget(0,2) is None
    assert w._leggi_righe()[0].colore=='RAL7016'
    w.verifica.setChecked(True);assert w.calcola.isEnabled()
    w._calcola();assert w._piano and len(w._piano.prelievi)==1 and w.esporta.isEnabled()
    w.tabella.item(0,3).setText('500')
    assert w._piano is None and not w.esporta.isEnabled() and not w.verifica.isChecked()


def test_ui_paginazione_non_crea_migliaia_di_righe(factory,qtbot):
    from magazzino_profili.ui.scheda_commesse import SchedaCommesse
    w=SchedaCommesse(factory,lambda *_:None);qtbot.addWidget(w)
    p=pianifica([richiesta(1000,250)],[materiale(i,1000) for i in range(250)])
    w._ricevi_piano(p)
    assert w.risultati.rowCount()==100 and w.successiva.isEnabled()
    w._sfoglia(2);assert w.risultati.rowCount()==50 and not w.successiva.isEnabled()


def test_invarianti_piano_su_scorte_e_richieste_variate():
    import random
    for seme in range(30):
        caso=random.Random(seme)
        richieste=[richiesta(caso.randint(1,50)*100,caso.randint(1,5)) for _ in range(10)]
        materiali=[materiale(i,caso.randint(1,8)*1000) for i in range(20)]
        p=pianifica(richieste,materiali)
        assert len({x.materiale.chiave for x in p.prelievi})==len(p.prelievi)
        domande=sum(r.quantita for r in richieste)
        assert sum(len(x.tagli) for x in p.prelievi)+sum(r.quantita for r in p.mancanti)==domande
        for x in p.prelievi:
            assert x.residuo>=0
            if not x.chiuso:
                assert sum(r.lunghezza for r in x.tagli)+x.residuo==x.materiale.lunghezza


def test_scheda_principale_crea_commesse_solo_quando_aperta(factory,qtbot):
    from magazzino_profili.ui.finestra_principale import FinestraPrincipale
    from magazzino_profili.sicurezza import Ruolo
    w=FinestraPrincipale(factory,Ruolo.AMMINISTRATORE,'test');qtbot.addWidget(w)
    assert w._pagina_pronta('scheda_commesse') is None
    w._tab.setCurrentIndex(w._nomi_pagine.index('scheda_commesse'))
    assert w._pagina_pronta('scheda_commesse') is not None
    w.close()


def test_csv_prelievo_completo_con_mancanti_e_protezione_formule(factory,qtbot,monkeypatch,tmp_path):
    import csv
    from magazzino_profili.ui.scheda_commesse import SchedaCommesse, QFileDialog
    def avvia(titolo,azione,completato=None):
        risultato=azione()
        if completato:completato(risultato)
    w=SchedaCommesse(factory,avvia);qtbot.addWidget(w)
    m=Materiale('1','AB12','RAL7016',20000,'=2+2','4','Corsia A')
    p=pianifica([richiesta(1000,3)],[m])
    w._ricevi_piano(p)
    uscita=tmp_path/'prelievo.csv'
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *_:(str(uscita),'CSV'))
    w._esporta()
    with uscita.open(encoding='utf-8-sig',newline='') as f:righe=list(csv.reader(f,delimiter=';'))
    assert righe[1][4]=='4' and righe[1][5]=="'=2+2" and righe[1][3]=='2000'
    assert righe[2][0]=='Mancante' and righe[2][7]=='1'
    assert righe[-1][0]=='Avvertenze' and 'misure nominali' in righe[-1][8]
