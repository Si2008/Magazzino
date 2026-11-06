"""Test UI offscreen Fasi 7-8: colonne Vassoio/Stato barcode, filtri, azioni laterali.

Stile di ``test_ui_smoke.py``: QApplication offscreen, SQLite in memoria,
``QMessageBox`` sostituito con uno stub (niente dialoghi modali).
"""

import pytest

from magazzino_profili.services import carica, imposta_numero_vassoio, imposta_stato

_VASSOIO = 7
_STATO_BARCODE = 8


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


def test_colonne_vassoio_e_stato_barcode(qapp, factory, dati) -> None:
    scheda = _scheda(factory)
    tabella = scheda._tabella
    assert tabella.columnCount() == 9
    assert tabella.horizontalHeaderItem(0).text() == "BARCODE"  # contratto
    assert tabella.horizontalHeaderItem(2).text() == "COLORE"  # contratto
    assert tabella.horizontalHeaderItem(_VASSOIO).text() == "VASSOIO"
    assert tabella.horizontalHeaderItem(_STATO_BARCODE).text() == "STATO BARCODE"
    # record storico: vassoio e stato vuoti → "—"
    assert tabella.item(0, _VASSOIO).text() == "—"
    assert tabella.item(0, _STATO_BARCODE).text() == "—"


def test_vassoio_in_tabella_e_aggiornato_dallazione(qapp, factory, dati) -> None:
    scheda = _scheda(factory)
    sessione = factory()
    try:
        imposta_numero_vassoio(sessione, dati["pezzo"], "Vassoio 4")
    finally:
        sessione.close()
    scheda.aggiorna()
    assert scheda._tabella.item(0, _VASSOIO).text() == "Vassoio 4"

    # azione laterale (senza dialogo: il metodo di servizio è lo stesso usato dal pulsante)
    sessione = factory()
    try:
        imposta_numero_vassoio(sessione, dati["pezzo"], None)  # cancella
    finally:
        sessione.close()
    scheda.aggiorna()
    assert scheda._tabella.item(0, _VASSOIO).text() == "—"


def test_filtro_stato_barcode(qapp, factory, dati) -> None:
    scheda = _scheda(factory)
    sessione = factory()
    try:
        imposta_stato(sessione, dati["pezzo"], "Scaricato")
    finally:
        sessione.close()
    scheda.aggiorna()
    assert scheda._tabella.item(0, _STATO_BARCODE).text() == "Scaricato"

    i = scheda.combo_stato_barcode.findData("Scaricato")
    scheda.combo_stato_barcode.setCurrentIndex(i)
    assert scheda._tabella.rowCount() == 1
    i = scheda.combo_stato_barcode.findData("Caricato")
    scheda.combo_stato_barcode.setCurrentIndex(i)
    assert scheda._tabella.rowCount() == 0
    scheda.azzera.clicked.emit()
    assert scheda._tabella.rowCount() == 1


def test_imposta_stato_dallazione_laterale(qapp, factory, dati) -> None:
    scheda = _scheda(factory)
    _seleziona(scheda, dati["barcode"])
    scheda._imposta_stato("Scaricato")
    assert scheda._tabella.item(0, _STATO_BARCODE).text() == "Scaricato"
    scheda._imposta_stato("Caricato")
    assert scheda._tabella.item(0, _STATO_BARCODE).text() == "Caricato"


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
    assert scheda._tabella.item(0, _STATO_BARCODE).text() == "—"  # UI non aggiornata


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
