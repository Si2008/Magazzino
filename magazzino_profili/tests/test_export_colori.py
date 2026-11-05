"""Fogli per codice colore e reimport completo, soltanto dati sintetici."""
from openpyxl import load_workbook
from odf.opendocument import load
from odf.table import Table
from sqlalchemy import select,func
from magazzino_profili.domain import Colore,Movimento
from magazzino_profili.tests.test_correzioni_dati import factory
from magazzino_profili.services.pezzi_unitari import crea_pezzi_unitari
from magazzino_profili.reports.export_excel import esporta_inventario_excel
from magazzino_profili.reports.ods_v2 import esporta_inventario_ods_v2,valida_ods_v2
from magazzino_profili.reports.formato_v2 import importa_inventario_v2
from magazzino_profili.reports.fogli_colore import nome_foglio_colore


def popola(factory):
    barcode={}
    for codice in ['RAL9010','RAL7016','RAL9010']:
        with factory() as s:
            p=crea_pezzi_unitari(s,codice='AB12',colore=codice,lunghezza_mm=6000,
                quantita=1,numero_vassoio='4',utente='test',causale='Prova export')[0]
            barcode.setdefault(codice,set()).add(p.barcode)
    # Nomi visualizzati uguali non devono fondere due codici distinti.
    with factory() as s,s.begin():
        for c in s.scalars(select(Colore)):c.nome_visualizzato='Colore di prova'
    return barcode


def test_excel_un_foglio_per_codice_senza_perdere_o_duplicare_pezzi(factory,tmp_path):
    attesi=popola(factory)
    with factory() as s:esporta_inventario_excel(s,tmp_path/'colori.xlsx')
    wb=load_workbook(tmp_path/'colori.xlsx')
    try:
        assert set(wb.sheetnames)==set(attesi)
        for codice,barcode in attesi.items():
            ws=wb[codice]
            assert 'Descrizione' not in [c.value for c in ws[1]]
            assert not any('peso' in str(c.value).lower() for c in ws[1])
            assert ws.freeze_panes=='A2'
            assert {r[-1] for r in ws.iter_rows(min_row=2,values_only=True)}==barcode
    finally:wb.close()


def test_ods_fogli_colore_reimporta_tutti_i_pezzi_senza_nuovi_movimenti(factory,tmp_path):
    attesi=popola(factory)
    with factory() as s:esporta_inventario_ods_v2(s,tmp_path/'colori.ods')
    doc=load(str(tmp_path/'colori.ods'))
    assert {f.getAttribute('name') for f in doc.spreadsheet.getElementsByType(Table)}==set(attesi)
    risultato=valida_ods_v2(tmp_path/'colori.ods')
    assert risultato.valido,risultato.errori
    assert len(risultato.righe)==3
    for codice,barcode in attesi.items():assert {r.barcode for r in risultato.righe if r.colore==codice}==barcode
    with factory() as s:assert importa_inventario_v2(s,risultato,'test')==3
    with factory() as s:assert s.scalar(select(func.count()).select_from(Movimento))==3


def test_export_vuoti_apribili_con_intestazioni(factory,tmp_path):
    with factory() as s:esporta_inventario_excel(s,tmp_path/'vuoto.xlsx')
    with factory() as s:esporta_inventario_ods_v2(s,tmp_path/'vuoto.ods')
    wb=load_workbook(tmp_path/'vuoto.xlsx')
    try:assert wb.sheetnames==['Inventario'] and wb.active.max_row==1
    finally:wb.close()
    risultato=valida_ods_v2(tmp_path/'vuoto.ods')
    assert risultato.valido and not risultato.righe


def test_nomi_fogli_validi_univoci_anche_dopo_pulizia_e_troncamento():
    occupati=set()
    nomi=[nome_foglio_colore(c,occupati) for c in ['A/B','A:B','a-b',"'",'X'*50,'X'*50+'1']]
    assert len({n.casefold() for n in nomi})==6
    assert all(0<len(n)<=31 and not set(n)&set('[]:*?/\\') for n in nomi)
