"""Test fumò dell'interfaccia (offscreen, con pytest-qt).

Verificano il layout "grande":

- 4 tab colori in Inventario ("Tutti" + 3 colori, uno senza pezzi);
- la tab del colore senza pezzi esiste comunque (sbiadita);
- selezione di un colore: filtra la tabella e nasconde la colonna
  "Colore"; tornando a "Tutti" la colonna riappare;
- dopo un carico la scheda selezionata non cambia e la tab del nuovo
  colore compare dinamicamente;
- ``vai_a_colore`` (collegamento Avvisi → Inventario);
- filtro ubicazione a UGUAGLIANZA esatta (non sottostringa);
- card KPI coerenti con i servizi;
- finestra principale con 5 schede per AMMINISTRATORE e il
  collegamento Avvisi "Dettagli" → Inventario.
"""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine

from magazzino_profili.db import crea_session_factory
from magazzino_profili.domain import Base, Colore, Pezzo, Profilo
from magazzino_profili.sicurezza import Ruolo
from magazzino_profili.services import carica


@pytest.fixture()
def factory():
    """Factory su SQLite in memoria (condivisione SingletonThreadPool)."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return crea_session_factory(engine)


@pytest.fixture()
def dati(factory):
    """Un profilo, tre colori (BIANCO senza pezzi) e due giacenze."""
    sessione = factory()
    profilo = Profilo(
        codice="AB12",
        descrizione="Profilo di prova",
        peso_kg_per_metro=Decimal("1.2500"),
        lunghezza_standard_mm=6000,
    )
    antracite = Colore(codice_normalizzato="AN007", nome_visualizzato="Antracite")
    bianco = Colore(codice_normalizzato="BIANCO", nome_visualizzato="Bianco")
    ral = Colore(codice_normalizzato="RAL9010", nome_visualizzato="RAL 9010")
    sessione.add_all([profilo, antracite, bianco, ral])
    sessione.flush()
    sessione.add_all(
        [
            Pezzo(
                profilo=profilo,
                colore=antracite,
                lunghezza_mm=6000,
                quantita=10,
                barcode="AB12-AN007-6000",
                ubicazione="Vassoio 1",
                scorta_minima=2,
            ),
            Pezzo(
                profilo=profilo,
                colore=ral,
                lunghezza_mm=6000,
                quantita=5,
                barcode="AB12-RAL9010-6000",
                ubicazione="Vassoio 2",
                scorta_minima=20,  # sotto scorta → avviso
            ),
        ]
    )
    sessione.commit()
    ids = {
        "profilo": profilo.id,
        "antracite": antracite.id,
        "bianco": bianco.id,
        "ral": ral.id,
    }
    sessione.close()
    return ids


def _tab(testo_parte: str, tabbar):
    """Indice della tab la cui etichetta contiene il testo."""
    for i in range(tabbar.count()):
        if testo_parte in tabbar.tabText(i):
            return i
    raise AssertionError(f"Tab con '{testo_parte}' non trovata")


# ---------------------------------------------------------------------------
# TabellaPezzi: tab colori
# ---------------------------------------------------------------------------
def test_inventario_quattro_tab(qapp, factory, dati) -> None:
    from magazzino_profili.ui.tabella_pezzi import TabellaPezzi

    scheda = TabellaPezzi(factory)
    bar = scheda._tabbar
    assert bar.count() == 4  # Tutti + AN007 + BIANCO + RAL9010
    assert bar.tabText(0) == "Tutti"
    assert "Antracite (1)" in bar.tabText(_tab("Antracite", bar))
    assert "Bianco (0)" in bar.tabText(_tab("Bianco", bar))


def test_tab_colore_zero_pezzi_esiste(qapp, factory, dati) -> None:
    from magazzino_profili.ui.tabella_pezzi import TabellaPezzi

    scheda = TabellaPezzi(factory)
    bar = scheda._tabbar
    i = _tab("Bianco", bar)
    assert bar.tabIcon(i) is not None  # pallino (sbiadito) presente
    assert not bar.tabIcon(i).isNull()
    bar.setCurrentIndex(i)
    assert scheda._tabella.rowCount() == 0  # nessuna riga
    assert "0 di 0" in scheda._footer.text()


def test_selezione_colore_filtra_e_nasconde_colonna(qapp, factory, dati) -> None:
    from magazzino_profili.ui.tabella_pezzi import TabellaPezzi

    scheda = TabellaPezzi(factory)
    bar = scheda._tabbar
    tabella = scheda._tabella

    # "Tutti": colonna Colore visibile, 2 righe
    assert not tabella.isColumnHidden(2)
    assert tabella.rowCount() == 2

    bar.setCurrentIndex(_tab("Antracite", bar))
    assert tabella.isColumnHidden(2)  # colonna Colore nascosta
    assert tabella.rowCount() == 1
    assert "AB12" in tabella.item(0, 1).text()

    # filtro testo libera: "RAL9010" corrisponde solo alla riga RAL
    scheda.cerca.setText("RAL9010")
    from PySide6.QtTest import QTest
    QTest.qWait(300)
    assert tabella.rowCount() == 0  # su questa scheda c'è solo AN007
    scheda.cerca.clear()
    from PySide6.QtTest import QTest
    QTest.qWait(300)
    assert tabella.rowCount() == 1

    bar.setCurrentIndex(0)  # "Tutti"
    assert not tabella.isColumnHidden(2)
    assert tabella.rowCount() == 2


def test_tab_dinamica_dopo_carico_e_selezione_stabile(qapp, factory, dati) -> None:
    from magazzino_profili.ui.tabella_pezzi import TabellaPezzi

    scheda = TabellaPezzi(factory)
    bar = scheda._tabbar
    prima = bar.count()
    bar.setCurrentIndex(_tab("Antracite", bar))
    indice_selezionato = bar.currentIndex()

    # carico di un colore nuovo (BLU) → la tab compare dinamicamente
    sessione = factory()
    try:
        carica(
            sessione,
            codice="AB12",
            colore="BLU",
            lunghezza_mm=6000,
            quantita=4,
            utente="test",
            causale="Test UI",
        )
    finally:
        sessione.close()

    scheda.aggiorna()
    assert bar.count() == prima + 1
    assert _tab("BLU", bar) >= 0
    assert bar.currentIndex() == indice_selezionato  # la selezione NON cambia
    assert "Antracite" in bar.tabText(bar.currentIndex())


def test_vai_a_colore_da_avvisi(qapp, factory, dati) -> None:
    from magazzino_profili.ui.tabella_pezzi import TabellaPezzi

    scheda = TabellaPezzi(factory)
    bar = scheda._tabbar
    scheda.vai_a_colore(dati["ral"])
    assert "RAL" in bar.tabText(bar.currentIndex())
    assert scheda._tabella.rowCount() == 1


def test_ubicazione_uguaglianza_esatta(qapp, factory, dati) -> None:
    from magazzino_profili.ui.tabella_pezzi import TabellaPezzi

    scheda = TabellaPezzi(factory)
    scheda.combo_ubicazione.setEditText("Vassoio 1")
    from PySide6.QtTest import QTest
    QTest.qWait(300)
    assert scheda._tabella.rowCount() == 1
    assert scheda._tabella.item(0, 2).text() == "Antracite"  # colonna Colore

    # "vassoio" da solo NON deve corrispondere (uguaglianza, non sottostringa)
    scheda.combo_ubicazione.setEditText("Vassoio")
    from PySide6.QtTest import QTest
    QTest.qWait(300)
    assert scheda._tabella.rowCount() == 0

    # maiuscole/minuscole non contano
    scheda.combo_ubicazione.setEditText("vassOIO 1")
    from PySide6.QtTest import QTest
    QTest.qWait(300)
    assert scheda._tabella.rowCount() == 1


def test_card_kpi_coerenti(qapp, factory, dati) -> None:
    from magazzino_profili.ui.tabella_pezzi import TabellaPezzi

    scheda = TabellaPezzi(factory)
    assert scheda.kpi_pezzi._valore.text() == "15"
    assert scheda.kpi_profili._valore.text() == "2"
    assert scheda.kpi_peso._valore.text() == "112,5 kg"  # (10+5) * 6 m * 1,25 kg/m (formato italiano)
    assert scheda.kpi_riordino._valore.text() == "1"  # RAL sotto scorta


# ---------------------------------------------------------------------------
# Finestra principale
# ---------------------------------------------------------------------------
def test_finestra_principale_cinque_schede_e_avvisi(qapp, factory, dati) -> None:
    from magazzino_profili.ui.finestra_principale import FinestraPrincipale

    finestra = FinestraPrincipale(factory, Ruolo.AMMINISTRATORE, "test")
    tab = finestra._tab
    nomi = [tab.tabText(i) for i in range(tab.count())]
    assert nomi[:4] == ["Inventario", "Carico", "Scarico", "Profili"]
    assert nomi[4].startswith("Avvisi")  # eventuale badge "(N)"

    # collegamento Avvisi → Inventario (seleziona la scheda colore)
    assert tab.currentWidget() is finestra.scheda_inventario
    finestra.scheda_avvisi.vai_a_colore.emit(dati["bianco"])
    assert tab.currentWidget() is finestra.scheda_inventario
    bar = finestra.scheda_inventario._tabbar
    assert "Bianco" in bar.tabText(bar.currentIndex())


def test_finestra_principale_ruolo_operatore(qapp, factory, dati) -> None:
    from magazzino_profili.ui.finestra_principale import FinestraPrincipale

    finestra = FinestraPrincipale(factory, Ruolo.OPERATORE, "test")
    nomi = [finestra._tab.tabText(i) for i in range(finestra._tab.count())]
    assert nomi == ["Inventario", "Carico", "Scarico", "Profili", "Avvisi", "Commesse"]
