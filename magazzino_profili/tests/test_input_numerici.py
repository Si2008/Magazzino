"""Regressione P2: i campi numerici accettano valori a più cifre."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtTest import QTest
from sqlalchemy import select

from magazzino_profili.db import crea_engine, crea_session_factory, crea_tabelle
from magazzino_profili.domain import Pezzo
from magazzino_profili.services import carica
from magazzino_profili.services.anagrafica import crea_profilo
from magazzino_profili.ui.scheda_carico import SchedaCarico
from magazzino_profili.ui.scheda_scarico import SchedaScarico


@pytest.fixture()
def factory(tmp_path: Path):
    eng = crea_engine(url=f"sqlite:///{tmp_path / 'input.db'}")
    crea_tabelle(eng)
    fabbrica = crea_session_factory(eng)
    s = fabbrica()
    crea_profilo(s, "AB12", "Profilo test", 1.0, 6000, "test")
    s.close()
    return fabbrica


def test_lunghezza_accetta_piu_cifre(qtbot, factory) -> None:
    w = SchedaCarico(factory, "test")
    qtbot.addWidget(w)
    QTest.keyClicks(w.lunghezza, "6000")
    assert w.lunghezza.text() == "6000"


def test_quantita_carico_accetta_piu_cifre(qtbot, factory) -> None:
    w = SchedaCarico(factory, "test")
    qtbot.addWidget(w)
    w.quantita.clear()  # il campo parte con "1"
    QTest.keyClicks(w.quantita, "12")
    assert w.quantita.text() == "12"


def test_quantita_scarico_accetta_piu_cifre(qtbot, factory) -> None:
    w = SchedaScarico(factory, "test")
    qtbot.addWidget(w)
    w.quantita.clear()  # il campo parte con "1"
    QTest.keyClicks(w.quantita, "15")
    assert w.quantita.text() == "15"


def test_validatore_rifiuta_lettere(qtbot, factory) -> None:
    w = SchedaCarico(factory, "test")
    qtbot.addWidget(w)
    QTest.keyClicks(w.lunghezza, "6a0")
    assert w.lunghezza.text() == "60"


def test_scansione_barcode_esistente_non_crea_pezzi_nuovi(qtbot, factory) -> None:
    s = factory()
    carica(s, "AB12", "NERO", 6000, 4, "test", "init", None)
    s.close()

    w = SchedaCarico(factory, "test")
    qtbot.addWidget(w)
    QTest.keyClicks(w.barcode, "AB12-NERO-6000")
    w.barcode.returnPressed.emit()

    s = factory()
    pezzi = {p.barcode: p.quantita for p in s.scalars(select(Pezzo))}
    s.close()
    assert pezzi == {"AB12-NERO-6000": 5}, f"pezzi inattesi: {pezzi}"


def test_salvataggio_carico_con_lunghezza_multi_cifra(qtbot, factory) -> None:
    w = SchedaCarico(factory, "test")
    qtbot.addWidget(w)
    w.codice.setText("AB12")
    w.colore.setText("BIANCO")
    QTest.keyClicks(w.lunghezza, "3000")
    w.quantita.clear()  # il campo parte con "1"
    QTest.keyClicks(w.quantita, "7")
    w.salva_carico()

    s = factory()
    pz = s.scalar(select(Pezzo).where(Pezzo.barcode == "AB12-BIANCO-3000"))
    s.close()
    assert pz is not None and pz.quantita == 7
