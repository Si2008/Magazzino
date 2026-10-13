"""Fase 4: test di interfaccia per la revisione grafica e i messaggi."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtTest import QTest
from sqlalchemy import select

from magazzino_profili.db import crea_engine, crea_session_factory, crea_tabelle
from magazzino_profili.domain import Pezzo, QuantitaInsufficienteError
from magazzino_profili.services import carica, scarica
from magazzino_profili.services.anagrafica import crea_profilo
from magazzino_profili.ui import messaggi
from magazzino_profili.ui.scheda_carico import SchedaCarico
from magazzino_profili.ui.scheda_scarico import SchedaScarico
from magazzino_profili.ui.tabella_pezzi import TabellaPezzi


@pytest.fixture()
def factory(tmp_path: Path):
    eng = crea_engine(url=f"sqlite:///{tmp_path / 'fase4.db'}")
    crea_tabelle(eng)
    fabbrica = crea_session_factory(eng)
    s = fabbrica()
    crea_profilo(s, "AB12", "Angolo 120 mm", 1.25, 6000, "test")
    s.close()
    return fabbrica


def _pezzi(F) -> dict[str, int]:
    s = F()
    risultato = {p.barcode: p.quantita for p in s.scalars(select(Pezzo))}
    s.close()
    return risultato


# ---------------------------------------------------------------- regressione: segnaposto ubicazione
def test_ubicazione_non_scelta_non_salva_il_segnaposto(qtbot, factory) -> None:
    s = factory()
    carica(s, "AB12", "AN007", 6000, 2, "test", "init", "Vassoio 1")
    s.close()
    w = SchedaCarico(factory, "test")
    qtbot.addWidget(w)
    assert w.ubicazione.currentText() == "", "il campo ubicazione deve partire vuoto"
    w.codice.setText("AB12")
    w.colore.setText("ROSSO")
    w.lunghezza.setText("3000")
    w.quantita.setText("1")
    w.salva_carico()
    s = factory()
    pz = s.scalar(select(Pezzo).where(Pezzo.barcode == "AB12-ROSSO-3000"))
    s.close()
    assert pz is not None and pz.ubicazione is None


# ---------------------------------------------------------------- KPI: stile isolato
def test_card_kpi_non_trasmette_stile_alle_etichette(qtbot, factory) -> None:
    scheda = TabellaPezzi(factory)
    qtbot.addWidget(scheda)
    card = scheda.kpi_pezzi
    assert card.objectName() == "CardKPI"
    assert "border" not in card._valore.styleSheet()
    assert "background" not in card._etichetta.styleSheet()


# ---------------------------------------------------------------- Caricato / Scaricato
def test_movimenti_distinguono_caricato_e_scaricato(qtbot, factory) -> None:
    s = factory()
    carica(s, "AB12", "AN007", 6000, 10, "test", "Arrivo fornitore", None)
    s.close()
    s = factory()
    scarica(s, "AB12-AN007-6000", 3, "test", "Vendita")
    s.close()
    w = SchedaCarico(factory, "test")
    qtbot.addWidget(w)
    testo = w.movimenti.toPlainText()
    assert "CARICATO" in testo and "SCARICATO" in testo
    assert "+ 10" in testo and "− 3" in testo


# ---------------------------------------------------------------- scarico: anteprima
def test_scarico_anteprima_mostra_il_pezzo_e_la_giacenza(qtbot, factory) -> None:
    s = factory()
    carica(s, "AB12", "AN007", 6000, 12, "test", "init", "Vassoio 1")
    s.close()
    w = SchedaScarico(factory, "test")
    qtbot.addWidget(w)
    QTest.keyClicks(w.barcode, "AB12-AN007-6000")
    assert "giacenza: 12 pz" in w.anteprima.text()
    assert "Vassoio 1" in w.anteprima.text()


def test_scarico_anteprima_segnala_barcode_inesistente(qtbot, factory) -> None:
    w = SchedaScarico(factory, "test")
    qtbot.addWidget(w)
    QTest.keyClicks(w.barcode, "XX99-NERO-1000")
    assert "Nessun pezzo" in w.anteprima.text()


# ---------------------------------------------------------------- scarico totale: conferma
def test_scarico_totale_richiede_conferma_e_puo_essere_annullato(qtbot, factory, monkeypatch) -> None:
    s = factory()
    carica(s, "AB12", "AN007", 6000, 12, "test", "init", None)
    s.close()
    chiamate = []

    def no(*args, **kwargs):
        chiamate.append(args)
        return False

    monkeypatch.setattr("magazzino_profili.ui.scheda_scarico.chiedi_conferma", no)
    w = SchedaScarico(factory, "test")
    qtbot.addWidget(w)
    w.barcode.setText("AB12-AN007-6000")
    w.quantita.clear()
    QTest.keyClicks(w.quantita, "12")
    w.causale.setText("Vendita")
    w.salva_scarico()
    assert len(chiamate) == 1, "lo scarico totale deve chiedere conferma"
    assert _pezzi(factory)["AB12-AN007-6000"] == 12, "annullando non deve cambiare la giacenza"


def test_scarico_totale_confermato_azzera_la_giacenza(qtbot, factory, monkeypatch) -> None:
    s = factory()
    carica(s, "AB12", "AN007", 6000, 12, "test", "init", None)
    s.close()
    monkeypatch.setattr("magazzino_profili.ui.scheda_scarico.chiedi_conferma", lambda *a, **k: True)
    w = SchedaScarico(factory, "test")
    qtbot.addWidget(w)
    w.barcode.setText("AB12-AN007-6000")
    w.quantita.clear()
    QTest.keyClicks(w.quantita, "12")
    w.causale.setText("Vendita")
    w.salva_scarico()
    assert _pezzi(factory)["AB12-AN007-6000"] == 0


def test_scarico_parziale_non_chiede_conferma(qtbot, factory, monkeypatch) -> None:
    s = factory()
    carica(s, "AB12", "AN007", 6000, 12, "test", "init", None)
    s.close()

    def non_deve_essere_chiamata(*a, **k):
        raise AssertionError("conferma non richiesta per uno scarico parziale")

    monkeypatch.setattr("magazzino_profili.ui.scheda_scarico.chiedi_conferma", non_deve_essere_chiamata)
    w = SchedaScarico(factory, "test")
    qtbot.addWidget(w)
    w.barcode.setText("AB12-AN007-6000")
    w.quantita.clear()
    QTest.keyClicks(w.quantita, "5")
    w.causale.setText("Vendita")
    w.salva_scarico()
    assert _pezzi(factory)["AB12-AN007-6000"] == 7


# ---------------------------------------------------------------- messaggi comprensibili
def test_errore_giacenza_spiegato_in_italiano() -> None:
    testo = messaggi.testo_per_utente(QuantitaInsufficienteError(4, 9), "Lo scarico")
    assert "Giacenza insufficiente" in testo and "4" in testo and "9" in testo
    assert "Traceback" not in testo and "Error" not in testo


def test_errore_imprevisto_non_mostra_dettagli_tecnici() -> None:
    testo = messaggi.testo_per_utente(RuntimeError("segreto: colonna xyz"), "Il carico")
    assert "segreto" not in testo
    assert "app.log" in testo


def test_errore_database_indica_postgres() -> None:
    from sqlalchemy.exc import OperationalError

    testo = messaggi.testo_per_utente(OperationalError("SELECT", {}, Exception("refused")), "Il carico")
    assert "PostgreSQL" in testo
