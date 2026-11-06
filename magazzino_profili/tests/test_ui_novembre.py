"""Regressioni richieste UI: solo SQLite in memoria e risorse temporanee."""
import csv
from decimal import Decimal

import pytest
from PIL import Image
from sqlalchemy import create_engine, select
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QLineEdit

from magazzino_profili.db import crea_session_factory
from magazzino_profili.domain import Base, Profilo, Colore, Pezzo
from magazzino_profili.ui import tema


@pytest.fixture
def factory_ui():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = crea_session_factory(engine)
    with factory() as s:
        p = Profilo(codice="AZ2001", descrizione="Telaio finestra", peso_kg_per_metro=Decimal("2.5000"), lunghezza_standard_mm=6000)
        q = Profilo(codice="AB12", descrizione="Angolo", lunghezza_standard_mm=5000)
        c = Colore(codice_normalizzato="BIANCO", nome_visualizzato="Bianco")
        s.add_all([p, q, c]); s.flush()
        s.add_all([Pezzo(profilo_id=p.id, colore_id=c.id, lunghezza_mm=3200, quantita=1,
            barcode="AZ2001-BIANCO-3200-P1", unitario=True, stato="Caricato", numero_vassoio="7"),
            Pezzo(profilo_id=q.id, colore_id=c.id, lunghezza_mm=2100, quantita=1,
            barcode="AB12-BIANCO-2100-P2", unitario=True, stato="Caricato", numero_vassoio="9")])
        s.commit()
    yield factory
    engine.dispose()


@pytest.fixture(params=[tema.CHIARO, tema.SCURO], ids=["chiaro", "scuro"])
def tema_ui(request, qapp):
    prima = tema.ATTUALE
    tema.ATTUALE = request.param
    qapp.setPalette(tema.palette_tema(request.param))
    qapp.setStyleSheet(tema.qss_globale(request.param))
    yield request.param
    tema.ATTUALE = prima
    qapp.setPalette(tema.palette_tema(prima))
    qapp.setStyleSheet(tema.qss_globale(prima))


def test_navigazione_senza_profili_editor_conservato(tema_ui, qtbot, factory_ui):
    from magazzino_profili.ui.finestra_principale import FinestraPrincipale
    from magazzino_profili.sicurezza import Ruolo
    w = FinestraPrincipale(factory_ui, Ruolo.AMMINISTRATORE, "test")
    qtbot.addWidget(w)
    assert [w._tab.tabText(i) for i in range(w._tab.count())] == ["Inventario", "Carico", "Scarico", "Avvisi", "Commesse"]
    assert w.scheda_inventario.gestisci_profili.isEnabled()
    assert w.scheda_profilo is not None  # API interna conservata, nessuna voce di navigazione.


def test_editor_senza_peso_conserva_dato_storico(tema_ui, qtbot, factory_ui):
    from magazzino_profili.ui.scheda_profilo import SchedaProfilo
    w = SchedaProfilo(factory_ui); qtbot.addWidget(w)
    assert not hasattr(w, "peso")
    assert all("PESO" not in w._tabella.horizontalHeaderItem(c).text() for c in range(w._tabella.columnCount()))
    riga = next(i for i in range(w._tabella.rowCount()) if w._tabella.item(i, 0).text() == "AZ2001")
    w._tabella.selectRow(riga)
    w.descrizione.setText("Telaio aggiornato")
    w.salva_profilo()
    with factory_ui() as s:
        p = s.scalar(select(Profilo).where(Profilo.codice == "AZ2001"))
        assert p.peso_kg_per_metro == Decimal("2.5000")
        assert p.descrizione == "Telaio aggiornato"
    w._nuovo(); w.codice.setText("NUOVO"); w.descrizione.setText("Nuovo telaio"); w.lunghezza.setText("6000")
    w.salva_profilo()
    with factory_ui() as s:
        assert s.scalar(select(Profilo).where(Profilo.codice == "NUOVO")) is not None


def test_inventario_immagine_e_segnaposto(tema_ui, qtbot, factory_ui, catalogo_isolato, monkeypatch):
    from magazzino_profili.ui.tabella_pezzi import TabellaPezzi
    Image.new("RGB", (120, 120), "white").save(catalogo_isolato / "AZ2001.png")
    (catalogo_isolato / "Indice_profili_aggiornato.csv").write_text("Codice;Stato immagine\nAZ2001;presente\nAB12;manca\n", encoding="utf-8")
    w = TabellaPezzi(factory_ui); qtbot.addWidget(w); w.show()
    for i in range(w._tabella.rowCount()):
        if w._tabella.item(i, 0).text().startswith("AZ2001-"):
            w._tabella.selectRow(i)
    assert w.anteprima_sezione.percorso is not None
    assert w.anteprima_sezione.apri.isEnabled()
    aperte = []
    monkeypatch.setattr("magazzino_profili.ui.visualizzatore_immagine.apri_immagine", lambda percorso, parent: aperte.append(percorso))
    qtbot.mouseClick(w.anteprima_sezione.immagine, Qt.LeftButton)
    assert aperte == [catalogo_isolato / "AZ2001.png"]
    w._tabella.selectRow(1)
    # L'ordinamento del servizio può differire da quello dei profili.
    for i in range(w._tabella.rowCount()):
        if w._tabella.item(i, 0).text().startswith("AB12-"):
            w._tabella.selectRow(i)
    assert w.anteprima_sezione.percorso is None
    assert "indice" in w.anteprima_sezione.nota.text()
    assert not w.anteprima_sezione.apri.isEnabled()
    assert all("peso" not in x.text().lower() for x in w.findChildren(QLabel))
    assert all("peso" not in w._tabella.horizontalHeaderItem(c).text().lower() for c in range(w._tabella.columnCount()))


def test_png_non_indicizzato_resta_associato(factory_ui, catalogo_isolato):
    from magazzino_profili.services.immagini import dettaglio_immagine
    Image.new("RGB", (8, 8)).save(catalogo_isolato / "AB12.png")
    (catalogo_isolato / "Indice_profili_aggiornato.csv").write_text("Codice\nAZ2001\n", encoding="utf-8")
    with factory_ui() as s:
        p = s.scalar(select(Profilo).where(Profilo.codice == "AB12"))
        immagine, nota = dettaglio_immagine(p)
        assert immagine == catalogo_isolato / "AB12.png"
        assert "non presente" in nota


@pytest.mark.parametrize("scarico", [False, True])
def test_ricerca_locale_selezione_e_filtro(tema_ui, qtbot, factory_ui, scarico):
    from magazzino_profili.ui.scheda_carico import SchedaCarico
    from magazzino_profili.ui.scheda_scarico import SchedaScarico
    w = (SchedaScarico if scarico else SchedaCarico)(factory_ui)
    qtbot.addWidget(w)
    ricerca = w.ricerca_profili
    ricerca.cerca.setText("aZ2001"); ricerca._filtra()
    assert ricerca.tabella.rowCount() == 1
    ricerca.tabella.selectRow(0)
    assert (w.barcode.text().startswith("AZ2001-") if scarico else w.codice.text() == "AZ2001")
    ricerca.cerca.setText("NON-ESISTE"); ricerca._filtra()
    assert ricerca.tabella.rowCount() == 0
    assert "Nessun risultato" in ricerca.esito.text()
    assert not w.barcode.text()
    if not scarico: assert not w.codice.text()
    ricerca.cerca.setText("angolo"); ricerca._filtra()
    assert ricerca.tabella.rowCount() == 1
    ricerca.cerca.clear(); ricerca._filtra()
    assert ricerca.tabella.rowCount() == 2
    ricerca.cerca.setText("%_"); ricerca._filtra()
    assert ricerca.tabella.rowCount() == 0  # i metacaratteri non sono wildcard.


def test_ricerca_paginata(qtbot, factory_ui):
    from magazzino_profili.ui.ricerca_profili import RicercaProfili
    with factory_ui() as s:
        s.add_all(Profilo(codice=f"P{n:04}", descrizione="Profilo", lunghezza_standard_mm=6000) for n in range(105))
        s.commit()
    w = RicercaProfili(factory_ui); qtbot.addWidget(w)
    assert w.tabella.rowCount() == 50 and w.successiva.isEnabled()
    w._cambia_pagina(1)
    assert w.tabella.rowCount() == 50 and w.precedente.isEnabled()


@pytest.mark.parametrize("scarico", [False, True])
def test_riclic_sulla_stessa_riga_ricompila_il_form(tema_ui, qtbot, factory_ui, scarico):
    from magazzino_profili.ui.scheda_carico import SchedaCarico
    from magazzino_profili.ui.scheda_scarico import SchedaScarico
    w = (SchedaScarico if scarico else SchedaCarico)(factory_ui)
    qtbot.addWidget(w); w.resize(1366, 768); w.show()
    ricerca = w.ricerca_profili
    ricerca.tabella.selectRow(0)
    codice = ricerca._righe[0].barcode if scarico else ricerca._righe[0].codice
    w._azzera_form()
    campo = w.barcode if scarico else w.codice
    assert campo.text() == ""
    rettangolo = ricerca.tabella.visualItemRect(ricerca.tabella.item(0, 0))
    qtbot.mouseClick(ricerca.tabella.viewport(), Qt.LeftButton, pos=rettangolo.center())
    assert campo.text() == codice


def test_ricerca_isolata_e_db_non_disponibile(tema_ui, qtbot, factory_ui):
    from magazzino_profili.ui.scheda_carico import SchedaCarico
    from magazzino_profili.ui.scheda_scarico import SchedaScarico
    from magazzino_profili.ui.tabella_pezzi import TabellaPezzi
    from sqlalchemy.exc import SQLAlchemyError
    carico, scarico, inventario = SchedaCarico(factory_ui), SchedaScarico(factory_ui), TabellaPezzi(factory_ui)
    for w in (carico, scarico, inventario): qtbot.addWidget(w)
    prima = inventario._tabella.rowCount()
    ricerca = carico.ricerca_profili
    ricerca.cerca.setText("AZ2001"); ricerca._filtra(); ricerca.tabella.selectRow(0)
    assert inventario._tabella.rowCount() == prima
    assert scarico.ricerca_profili.cerca.text() == "" and scarico.ricerca_profili.tabella.rowCount() == 2
    def non_disponibile(): raise SQLAlchemyError("Database sintetico non disponibile")
    ricerca._factory = non_disponibile
    ricerca.aggiorna()
    assert ricerca.tabella.rowCount() == 0 and "Database non disponibile" in ricerca.esito.text()
    assert carico.codice.text() == ""


def test_cambio_tema_aggiorna_anteprima_senza_perdere_campi(qtbot, factory_ui, qapp):
    from magazzino_profili.ui.scheda_scarico import SchedaScarico
    w = SchedaScarico(factory_ui); qtbot.addWidget(w)
    w.barcode.setText("AZ2001-BIANCO-3200-P1"); w.causale.setText("Lavorazione")
    precedente = tema.ATTUALE
    try:
        for t in (tema.CHIARO, tema.SCURO):
            tema.ATTUALE = t
            w.aggiorna_tema()
            assert t.testo_dim in w.anteprima.text()
            assert w.causale.text() == "Lavorazione"
            assert w.barcode.text() == "AZ2001-BIANCO-3200-P1"
    finally:
        tema.ATTUALE = precedente


@pytest.mark.parametrize("t", [tema.CHIARO, tema.SCURO], ids=["chiaro", "scuro"])
def test_contrasti_palette(t):
    for testo in (t.testo, t.testo_dim, t.testo_debole, t.accento, t.ok, t.avviso, t.pericolo):
        for sfondo in (t.sfondo, t.superficie, t.carta, t.carta2):
            assert tema.rapporto_contrasto(testo, sfondo) >= 4.5, (testo, sfondo)
    for base in ("accento", "ok", "pericolo"):
        testo, sfondo = getattr(t, base + "_inchiostro"), getattr(t, base)
        assert tema.rapporto_contrasto(testo, sfondo) >= 4.5
        assert tema.rapporto_contrasto(testo, tema.hover_pieno(sfondo, t)) >= 4.5
    assert tema.rapporto_contrasto(tema.inchiostro_contrasto(t.pericolo, t), t.pericolo) >= 4.5
    from PySide6.QtGui import QColor
    for nome in ("accento", "ok", "avviso", "pericolo"):
        velo = tema.colore_da_css(getattr(t, nome + "_vel"))
        assert velo.isValid()  # QColor('rgba(...)') diretto era invalido nei delegati.
        carta = QColor(t.carta)
        a = velo.alphaF()
        composito = QColor(*[round(a*x+(1-a)*y) for x,y in zip(
            (velo.red(),velo.green(),velo.blue()),(carta.red(),carta.green(),carta.blue()))]).name()
        for testo in (t.testo, t.testo_dim, getattr(t, nome)):
            assert tema.rapporto_contrasto(testo, composito) >= 4.5, (nome,testo,composito)


def test_pillole_leggibili_anche_sulla_selezione(tema_ui, qtbot):
    from magazzino_profili.ui.componenti import Pillola
    for variante in ("ok", "avviso", "pericolo", "neutro"):
        w = Pillola("Stato", variante); qtbot.addWidget(w)
        testo, fondo = w._colori()
        assert fondo.alpha() == 255
        assert tema.rapporto_contrasto(testo.name(), fondo.name()) >= 4.5


def test_import_v2_ignora_peso_csv_ods(factory_ui, tmp_path):
    from magazzino_profili.reports.formato_v2 import INTESTAZIONI_V2, riga_v2_da_pezzo, valida_csv_v2
    from magazzino_profili.reports.ods_v2 import valida_ods_v2
    from odf.opendocument import OpenDocumentSpreadsheet
    from odf.table import Table, TableRow, TableCell
    from odf.text import P
    with factory_ui() as s:
        z = s.scalar(select(Pezzo))
        riga = riga_v2_da_pezzo(z)
    intestazione = list(INTESTAZIONI_V2) + ["Peso kg/m"]
    righe = [intestazione, riga + ["dato storico non numerico ignorato"]]
    csv_file = tmp_path / "vecchio.csv"
    with csv_file.open("w", encoding="utf-8-sig", newline="") as f: csv.writer(f, delimiter=";").writerows(righe)
    assert valida_csv_v2(csv_file).valido
    doc = OpenDocumentSpreadsheet(); foglio = Table(name="Bianco")
    for valori in righe:
        tr = TableRow()
        for v in valori:
            c = TableCell(valuetype="string"); c.addElement(P(text=v)); tr.addElement(c)
        foglio.addElement(tr)
    doc.spreadsheet.addElement(foglio)
    file = tmp_path / "vecchio.ods"; doc.save(str(file))
    assert valida_ods_v2(file).valido


def test_excel_senza_peso_e_compatibilita_storica(factory_ui, tmp_path):
    from magazzino_profili.reports import backup_excel as b
    from openpyxl import load_workbook
    file = tmp_path / "nuovo.xlsx"
    with factory_ui() as s: b.esporta_backup_logico_excel(s, file)
    wb = load_workbook(file)
    assert "peso_kg_per_metro" not in [c.value for c in wb["Profili"][1]]
    assert b.valida_backup_logico_excel(file).versione == 5
    with factory_ui() as s: assert s.scalar(select(Profilo).where(Profilo.codice == "AZ2001")).peso_kg_per_metro == Decimal("2.5000")
    # Simula un backup formato 4, senza usare alcun file di dati dell'utente.
    ws = wb["Profili"]; ws.insert_cols(5); ws.cell(1, 5, "peso_kg_per_metro")
    for r in range(2, ws.max_row + 1): ws.cell(r, 5, 2.5)
    for row in wb["Metadati"]:
        if row[0].value == "versione_formato": row[1].value = 4
    old = tmp_path / "storico.xlsx"; wb.save(old); wb.close()
    storico = b.valida_backup_logico_excel(old)
    assert storico.tabelle["Profili"][0]["peso_kg_per_metro"] == Decimal("2.5")


@pytest.mark.parametrize("storico", [False, True])
def test_handler_mobile_crea_profilo_senza_peso(factory_ui, storico):
    """Handler e DTO sullo stesso thread; non sostituisce il test HTTP completo."""
    from magazzino_profili.web.routes_barcode import crea_router, RichiestaNuovoPezzo
    from magazzino_profili.web.accesso_libero import Operatore
    nuovo = dict(descrizione="Telaio nuovo", lunghezza_standard_mm=6000)
    if storico:
        nuovo["peso_kg_per_metro"] = "colonna obsoleta ignorata"
    richiesta = RichiestaNuovoPezzo(richiesta_id="nuovo-test", codice_profilo="ZZ99",
        colore="BIANCO", lunghezza_mm=3000, quantita=1, numero_vassoio="4",
        causale="Test", nuovo_profilo=nuovo)
    router = crea_router(factory_ui, b"", 3600)
    crea = next(r.endpoint for r in router.routes if r.path == "/api/pezzi" and "POST" in r.methods)
    lista = next(r.endpoint for r in router.routes if r.path == "/api/profili")
    risposta = crea(richiesta, Operatore())
    assert len(risposta["pezzi"]) == 1
    profili = lista(cerca="ZZ99")
    assert len(profili) == 1 and "peso_kg_per_metro" not in profili[0]
