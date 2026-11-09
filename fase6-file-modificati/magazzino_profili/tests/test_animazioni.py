"""Animazioni di transizione: stato finale corretto e nessun residuo (effetti grafici, overlay)."""

from decimal import Decimal

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel, QWidget
from sqlalchemy import create_engine

from magazzino_profili.db import crea_session_factory
from magazzino_profili.domain import Base, Colore, Pezzo, Profilo
from magazzino_profili.sicurezza import Ruolo
from magazzino_profili.ui import FinestraPrincipale, animazioni, tema


@pytest.fixture(autouse=True)
def animazioni_accese():
    animazioni.imposta_attive(True, salva=False)
    yield
    animazioni.imposta_attive(False, salva=False)


@pytest.fixture()
def factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    f = crea_session_factory(engine)
    s = f()
    p = Profilo(codice="AB12", descrizione="Prova", peso_kg_per_metro=Decimal("1.25"), lunghezza_standard_mm=6000)
    c = Colore(codice_normalizzato="RAL9010", nome_visualizzato="RAL 9010")
    s.add_all([p, c])
    s.flush()
    s.add(Pezzo(profilo=p, colore=c, lunghezza_mm=6000, quantita=5, barcode="AB12-RAL9010-6000",
                ubicazione="V1", scorta_minima=20))
    s.commit()
    s.close()
    return f


def test_spente_di_default_nei_test(monkeypatch):
    monkeypatch.setattr(animazioni, "_ATTIVE", None)
    assert animazioni.attive() is False  # conftest imposta MAGAZZINO_NO_ANIM=1


def test_dissolvenza_ripulisce_l_effetto(qtbot):
    w = QLabel("x")
    qtbot.addWidget(w)
    w.show()
    animazioni.dissolvenza(w, 80)
    assert isinstance(w.graphicsEffect(), QGraphicsOpacityEffect)
    QTest.qWait(250)
    assert w.graphicsEffect() is None


def test_conta_su_valori_crescenti_e_testo_finale_esatto():
    class Bersaglio:
        def __init__(self):
            self.testi = []

        def set_valore(self, t):
            self.testi.append(t)

    b = Bersaglio()
    animazioni.conta_su(b, 1234, lambda v: f"{int(v):,}", durata=120)
    QTest.qWait(300)
    numeri = [int(t.replace(",", "")) for t in b.testi]
    assert numeri == sorted(numeri)
    assert b.testi[-1] == "1,234"


def test_conta_su_senza_animazioni_e_immediato():
    animazioni.imposta_attive(False, salva=False)

    class B:
        t = None

        def set_valore(self, t):
            self.t = t

    b = B()
    animazioni.conta_su(b, 7, str)
    assert b.t == "7"


def test_scuoti_torna_alla_posizione_di_partenza(qtbot):
    genitore = QWidget()
    qtbot.addWidget(genitore)
    w = QLabel("err", genitore)
    w.move(40, 30)
    genitore.resize(300, 200)
    genitore.show()
    animazioni.scuoti(w, durata=100)
    QTest.qWait(300)
    assert w.pos() == QPoint(40, 30)


def test_cambio_tema_non_lascia_overlay(qtbot, factory):
    f = FinestraPrincipale(factory, Ruolo.AMMINISTRATORE, "t")
    qtbot.addWidget(f)
    f.resize(1200, 800)
    f.show()
    prima = tema.tema_attivo()
    f._cambia_tema()
    assert tema.tema_attivo() is not prima
    assert any(isinstance(c, QLabel) and c.pixmap() is not None and not c.pixmap().isNull()
               and c.parent() is f for c in f.findChildren(QLabel))  # velo presente durante la transizione
    QTest.qWait(600)
    assert [c for c in f.children() if isinstance(c, QLabel)] == []  # velo rimosso
    tema.alterna_tema() if tema.tema_attivo() is not prima else None


def test_toast_entra_e_si_chiude(qtbot, factory, monkeypatch):
    from magazzino_profili.ui.componenti import Toast

    monkeypatch.setattr(Toast, "DURATA_MS", 250)
    f = FinestraPrincipale(factory, Ruolo.AMMINISTRATORE, "t")
    qtbot.addWidget(f)
    f.resize(1200, 800)
    f.show()
    f.mostra_toast("Carico registrato", "ok")
    toast = f._toast[-1]
    assert toast.isVisible()
    QTest.qWait(200)
    assert toast.graphicsEffect() is None or toast.graphicsEffect().opacity() > 0
    QTest.qWait(700)
    assert not toast.isVisible()


def test_barra_avviso_arriva_alla_larghezza_finale(qtbot, factory):
    f = FinestraPrincipale(factory, Ruolo.AMMINISTRATORE, "t")
    qtbot.addWidget(f)
    f.resize(1400, 900)
    f.show()
    f._tab.setCurrentIndex(4)
    QTest.qWait(900)
    barre = f.scheda_avvisi.findChildren(type(f.scheda_avvisi.findChildren(QWidget, "MeterBarra")[0]))
    assert barre
    b = barre[0]
    assert b.width() == int(round(b.parent().width() * b._frazione_finale))
