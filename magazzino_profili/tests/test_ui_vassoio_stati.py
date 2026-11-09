"""Test UI offscreen Fasi 7-8: richiamo vassoio e azioni laterali.

Stile di ``test_ui_smoke.py``: QApplication offscreen, SQLite in memoria,
``QMessageBox`` sostituito con uno stub (niente dialoghi modali).
"""

import pytest

from magazzino_profili.domain import Pezzo

from magazzino_profili.services import carica

_RICHIAMO = 7


@pytest.fixture()
def factory():
    from sqlalchemy import create_engine

    from magazzino_profili.db import crea_session_factory
    from magazzino_profili.domain import Base

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return crea_session_factory(engine)


@pytest.fixture()
def dati(factory):
    from magazzino_profili.domain import Colore, Pezzo, Profilo

    sessione = factory()
    profilo = Profilo(
        codice="AB12", descrizione="Profilo di prova",
        peso_kg_per_metro=1.25, lunghezza_standard_mm=6000,
    )
    antracite = Colore(codice_normalizzato="AN007", nome_visualizzato="Antracite")
    sessione.add_all([profilo, antracite])
    sessione.flush()
    pezzo = Pezzo(
        profilo=profilo, colore=antracite, lunghezza_mm=6000,
        quantita=10, barcode="AB12-AN007-6000",
    )
    sessione.add(pezzo)
    sessione.commit()
    sessione.close()
    return {"profilo": profilo.id, "pezzo": pezzo.id, "barcode": "AB12-AN007-6000"}


def _scheda(factory):
    from magazzino_profili.ui.tabella_pezzi import TabellaPezzi

    return TabellaPezzi(factory)


def _seleziona(scheda, barcode: str) -> None:
    """Simula la selezione della riga con il barcode indicato."""
    tabella = scheda._tabella
    for riga in range(tabella.rowCount()):
        if (tabella.item(riga, 0).text() or "") == barcode:
            tabella.selectRow(riga)
            break
    else:
        raise AssertionError(f"riga con barcode {barcode} non trovata")
    scheda._su_selezione()


def test_colonna_richiamo_usa_il_pezzo_della_riga(qapp, factory, dati) -> None:
    scheda = _scheda(factory)
    tabella = scheda._tabella
    assert tabella.columnCount() == 8
    assert tabella.horizontalHeaderItem(0).text() == "BARCODE"
    assert tabella.horizontalHeaderItem(2).text() == "COLORE"
    assert tabella.horizontalHeaderItem(_RICHIAMO).text() == "RICHIAMO VASSOIO"
    chiamate = []
    scheda.richiamo_richiesto.connect(lambda barcode, ident: chiamate.append((barcode, ident)))
    tabella.cellWidget(0, _RICHIAMO).click()
    assert chiamate == [(dati["barcode"], dati["pezzo"])]


def test_imposta_stato_dallazione_laterale(qapp, factory, dati) -> None:
    scheda = _scheda(factory)
    _seleziona(scheda, dati["barcode"])
    scheda._imposta_stato("Scaricato")
    with factory() as sessione:
        assert sessione.get(Pezzo, dati["pezzo"]).stato == "Scaricato"
    scheda._imposta_stato("Caricato")
    with factory() as sessione:
        assert sessione.get(Pezzo, dati["pezzo"]).stato == "Caricato"


def test_stato_non_valido_da_errore_e_ui_invariata(qapp, factory, dati, monkeypatch) -> None:
    scheda = _scheda(factory)
    _seleziona(scheda, dati["barcode"])
    avvisi: list[tuple] = []

    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(
        "magazzino_profili.ui.tabella_pezzi.QMessageBox",
        type("Stub", (), {
            "StandardButton": QMessageBox.StandardButton,
            "warning": classmethod(lambda cls, *a, **k: avvisi.append(a)),
            "question": classmethod(lambda cls, *a, **k: QMessageBox.StandardButton.No),
        }),
    )
    scheda._imposta_stato("Rotto")
    assert avvisi, "l'errore deve essere mostrato all'utente"
    with factory() as sessione:
        assert sessione.get(Pezzo, dati["pezzo"]).stato is None


def test_elimina_barcode_rifiutata_il_recordResta(qapp, factory, dati, monkeypatch) -> None:
    scheda = _scheda(factory)
    _seleziona(scheda, dati["barcode"])

    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(
        "magazzino_profili.ui.tabella_pezzi.QMessageBox",
        type("Stub", (), {
            "StandardButton": QMessageBox.StandardButton,
            "warning": classmethod(lambda cls, *a, **k: None),
            "question": classmethod(lambda cls, *a, **k: QMessageBox.StandardButton.No),
        }),
    )
    scheda._elimina_barcode()
    assert scheda._tabella.rowCount() == 1  # il record resta
    assert scheda._barcode_selezionato == dati["barcode"]

    from magazzino_profili.domain import Pezzo

    sessione = factory()
    try:
        riga = sessione.get(Pezzo, dati["pezzo"])
        assert riga.eliminato_il is None  # nessuna sessione di scrittura: nessun effetto
    finally:
        sessione.close()


def test_elimina_barcode_confermata_il_record_diventa_invisibile(qapp, factory, dati, monkeypatch) -> None:
    scheda = _scheda(factory)
    _seleziona(scheda, dati["barcode"])

    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(
        "magazzino_profili.ui.tabella_pezzi.QMessageBox",
        type("Stub", (), {
            "StandardButton": QMessageBox.StandardButton,
            "warning": classmethod(lambda cls, *a, **k: None),
            "question": classmethod(lambda cls, *a, **k: QMessageBox.StandardButton.Yes),
        }),
    )
    scheda._elimina_barcode()
    assert scheda._tabella.rowCount() == 0  # nascosto dalla consultazione
    assert scheda._barcode_selezionato is None  # il pannello laterale si svuota

    from magazzino_profili.domain import Pezzo

    sessione = factory()
    try:
        riga = sessione.get(Pezzo, dati["pezzo"])
        assert riga.eliminato_il is not None  # eliminazione LOGICA: la riga esiste ancora
        assert riga.quantita == 10
    finally:
        sessione.close()
