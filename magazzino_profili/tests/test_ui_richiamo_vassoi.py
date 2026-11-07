"""Pulsanti di simulazione verificati con un inventario SQLite sintetico."""

import json
from unittest.mock import Mock

import pytest


@pytest.fixture
def inventario():
    from sqlalchemy import create_engine
    from magazzino_profili.db import crea_session_factory
    from magazzino_profili.domain import Base, Colore, Pezzo, Profilo

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = crea_session_factory(engine)
    with factory() as sessione:
        profilo = Profilo(
            codice="AB12", descrizione="Profilo prova",
            peso_kg_per_metro=1.25, lunghezza_standard_mm=6000,
        )
        colore = Colore(codice_normalizzato="NERO", nome_visualizzato="Nero")
        pezzo = Pezzo(profilo=profilo, colore=colore, barcode="AB12-NERO-6000",
                      lunghezza_mm=6000, quantita=1, numero_vassoio="Vassoio 7")
        sessione.add(pezzo)
        sessione.flush()
        identita = pezzo.id
        sessione.commit()
    yield factory, identita
    engine.dispose()


@pytest.fixture
def dialoghi(monkeypatch, tmp_path):
    from magazzino_profili.services import richiamo_vassoi as servizio
    from magazzino_profili.ui import richiamo_vassoi as dialogo

    conferma = Mock(return_value=True)
    messaggio = Mock()
    monkeypatch.setattr(dialogo, "chiedi_conferma", conferma)
    monkeypatch.setattr(dialogo.QMessageBox, "information", messaggio)
    monkeypatch.setattr(servizio, "dati_runtime", lambda: tmp_path)
    return conferma, messaggio, tmp_path / "log" / "richiami-vassoi.jsonl"


def test_scarico_conferma_barcode_e_registra_solo_la_simulazione(qtbot, inventario, dialoghi):
    from magazzino_profili.domain import Pezzo
    from magazzino_profili.ui.scheda_scarico import SchedaScarico

    factory, identita = inventario
    conferma, messaggio, registro = dialoghi
    scheda = SchedaScarico(factory)
    qtbot.addWidget(scheda)
    assert not scheda.simula_vassoio.isEnabled()
    scheda.barcode.setText("INESISTENTE")
    assert not scheda.simula_vassoio.isEnabled()
    scheda.barcode.setText("AB12-NERO-6000")
    assert scheda.simula_vassoio.isEnabled()

    conferma.return_value = False
    scheda.simula_vassoio.click()
    assert not registro.exists()
    messaggio.assert_not_called()
    conferma.return_value = True
    scheda.simula_vassoio.click()

    anteprima = conferma.call_args.args[2]
    assert all(testo in anteprima for testo in ("Profilo prova", "AB12-NERO-6000", "Vassoio: 7"))
    assert "simulato" in messaggio.call_args.args[2]
    assert json.loads(registro.read_text(encoding="utf-8"))["origine"] == "scarico"
    with factory() as sessione:
        assert sessione.get(Pezzo, identita).quantita == 1
    scheda.barcode.clear()
    assert not scheda.simula_vassoio.isEnabled()


def test_commesse_usa_solo_il_pezzo_selezionato(qtbot, inventario, dialoghi):
    from magazzino_profili.services.commesse import Materiale, PianoPrelievo, Prelievo
    from magazzino_profili.ui.scheda_commesse import SchedaCommesse

    factory, identita = inventario
    conferma, messaggio, registro = dialoghi
    scheda = SchedaCommesse(factory, Mock())
    qtbot.addWidget(scheda)
    valido = Materiale(f"pezzo:{identita}", "AB12", "NERO", 60000, "AB12-NERO-6000", "Vassoio 7", "")
    storico = Materiale("spezzone:1", "AB12", "NERO", 4000, "SPEZZONE #1", "7", "")
    scheda._ricevi_piano(PianoPrelievo([Prelievo(valido), Prelievo(storico)], [], []))

    assert not scheda.simula_vassoio.isEnabled()
    scheda.risultati.selectRow(1)
    assert not scheda.simula_vassoio.isEnabled()
    scheda.risultati.selectRow(0)
    assert scheda.simula_vassoio.isEnabled()
    scheda.simula_vassoio.click()
    conferma.assert_called_once()
    messaggio.assert_called_once()
    assert json.loads(registro.read_text(encoding="utf-8"))["origine"] == "commessa"

    scheda.vista.setCurrentIndex(1)
    assert not scheda.simula_vassoio.isEnabled()
    scheda.vista.setCurrentIndex(0)
    assert not scheda.simula_vassoio.isEnabled()
    scheda.risultati.selectRow(0)
    assert scheda.simula_vassoio.isEnabled()
    scheda.segnala_giacenza_cambiata()
    assert not scheda.simula_vassoio.isEnabled()
