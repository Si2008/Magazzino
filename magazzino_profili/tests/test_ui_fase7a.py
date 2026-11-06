"""Fase 7A - soglia globale di sotto scorta: UI della scheda Avvisi.

Regole verificate:
- stepper "Soglia sotto scorta" con default 5 (DB vuoto);
- modifica dello stepper -> salvataggio in DB, sottotitolo aggiornato,
  segnale ``soglia_cambiata``;
- riga "Sotto scorta" (giacenza <= soglia) e "In esaurimento"
  (giacenza > soglia e <= 3*soglia), con gravita' diversa.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from PySide6.QtWidgets import QFrame, QLabel
from sqlalchemy import create_engine, select

from magazzino_profili.db import crea_session_factory
from magazzino_profili.domain import Base, Colore, Pezzo, Profilo
from magazzino_profili.services import impostazioni
from magazzino_profili.ui.avvisi import SchedaAvvisi


@pytest.fixture()
def factory():
    """Factory su SQLite in memoria (condivisione SingletonThreadPool)."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return crea_session_factory(engine)


def _prepara(factory, barcode: str, quantita: int):
    """Un profilo + colore + pezzo SENZA scorta_minima; restituisce il pezzo."""
    sessione = factory()
    profilo = sessione.scalars(select(Profilo).limit(1)).first()
    colore = sessione.scalars(select(Colore).limit(1)).first()
    if profilo is None:
        profilo = Profilo(
            codice="AB12",
            descrizione="Profilo di prova",
            peso_kg_per_metro=Decimal("1.0"),
            lunghezza_standard_mm=6000,
        )
        sessione.add(profilo)
    if colore is None:
        colore = Colore(codice_normalizzato="ROSSO", nome_visualizzato="Rosso")
        sessione.add(colore)
    sessione.flush()
    lunghezza = int(barcode.rsplit("-", 1)[1])
    z = Pezzo(profilo=profilo, colore=colore, lunghezza_mm=lunghezza, quantita=quantita, barcode=barcode)
    sessione.add(z)
    sessione.commit()
    sessione.close()
    return z


def _titoli(scheda: SchedaAvvisi) -> list[str]:
    riga = scheda._corpo.findChild(QFrame, "RigaAvviso")
    assert riga is not None, "attesa una riga di avviso"
    return [l.text() for l in riga.findChildren(QLabel) if l.objectName() == "AvvTitolo"]


def test_stepper_soglia_default_e_sottotitolo(qapp, factory) -> None:
    scheda = SchedaAvvisi(factory)
    assert scheda.stepper_soglia.campo.text() == "5"
    assert "Sotto scorta: fino a 5 pezzi" in scheda.contatore.text()
    assert "In esaurimento: fino a 15 pezzi" in scheda.contatore.text()


def test_cambio_soglia_salva_e_emette(qtbot, factory) -> None:
    scheda = SchedaAvvisi(factory)
    ricevuti: list[int] = []
    scheda.soglia_cambiata.connect(lambda v: ricevuti.append(v))

    scheda.stepper_soglia.piu.click()  # 5 -> 6
    scheda._salva_soglia()
    qtbot.wait(50)  # fa scattare il debounce (istantaneo nei test) ed elimina le righe vecchie

    sessione = factory()
    try:
        assert impostazioni.leggi_soglia(sessione) == 6
    finally:
        sessione.close()

    assert "fino a 6 pezzi" in scheda.contatore.text()
    assert "fino a 18 pezzi" in scheda.contatore.text()
    assert ricevuti == [6]


def test_riga_sotto_scorta_e_in_esaurimento(qtbot, factory) -> None:
    _prepara(factory, "AB12-ROSSO-6000", 3)  # 3 <= 5 -> sotto scorta
    scheda = SchedaAvvisi(factory)
    assert any("Sotto scorta" in t for t in _titoli(scheda))
    riga = scheda._corpo.findChild(QFrame, "RigaAvviso")
    assert riga.property("gravita") == "pericolo"

    def _aggiorna(qta: int) -> None:
        sessione = factory()
        try:
            z = sessione.scalar(select(Pezzo).where(Pezzo.barcode == "AB12-ROSSO-6000"))
            z.quantita = qta
            sessione.commit()
        finally:
            sessione.close()
        scheda.aggiorna()
        qtbot.wait(50)  # fa scattare i deleteLater delle righe precedenti

    # 12 pezzi: non sotto scorta (12 > 5) ma in esaurimento (12 <= 15).
    _aggiorna(12)
    assert any("In esaurimento" in t for t in _titoli(scheda))
    assert scheda._corpo.findChild(QFrame, "RigaAvviso").property("gravita") == "avviso"

    # 16 pezzi: oltre 3*soglia -> esce dagli avvisi.
    _aggiorna(16)
    assert scheda._corpo.findChild(QFrame, "RigaAvviso") is None
