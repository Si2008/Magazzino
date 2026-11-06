"""Test del servizio impostazioni (soglia globale di sotto scorta)."""

import pytest
from sqlalchemy import create_engine

from magazzino_profili.db import crea_session_factory
from magazzino_profili.domain import Base, Impostazione
from magazzino_profili.services import impostazioni


@pytest.fixture()
def factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return crea_session_factory(engine)


def test_leggi_soglia_default_su_db_vuoto(factory):
    s = factory()
    assert impostazioni.leggi_soglia(s) == impostazioni.SOGLIA_DEFAULT == 5
    s.close()


def test_leggi_soglia_valore_illeggibile(factory):
    s = factory()
    s.add(Impostazione(chiave=impostazioni.CHIAVE_SOGLIA, valore="abc"))
    s.commit()
    assert impostazioni.leggi_soglia(s) == 5
    s.close()


def test_imposta_soglia_limiti(factory):
    s = factory()
    # attenzione: una lettura (autobegin) sulla stessa sessione impedirebbe
    # il begin() di imposta_soglia: la lettura va fatta DOPO gli scritti.
    assert impostazioni.imposta_soglia(s, 0) == 1
    assert impostazioni.imposta_soglia(s, 500) == 99
    assert impostazioni.imposta_soglia(s, 7) == 7
    assert impostazioni.leggi_soglia(s) == 7
    s.close()


def test_imposta_soglia_rifiuta_bool(factory):
    s = factory()
    with pytest.raises(ValueError):
        impostazioni.imposta_soglia(s, True)
    s.close()


def test_soglia_esaurimento(factory):
    assert impostazioni.soglia_esaurimento(5) == 15
    assert impostazioni.soglia_esaurimento(6) == 18
