"""Test del servizio ``services/pezzi.py`` (scorta minima).

Usano un database SQLite in memoria.
"""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from magazzino_profili.db import crea_session_factory
from magazzino_profili.domain import Base, Colore, Pezzo, Profilo
from magazzino_profili.services import imposta_scorta_minima


@pytest.fixture()
def factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return crea_session_factory(engine)


@pytest.fixture()
def pezzo(factory) -> int:
    """Crea un pezzo e ne restituisce l'id."""
    sessione: Session = factory()
    profilo = Profilo(
        codice="AB12",
        descrizione="Profilo di prova",
        peso_kg_per_metro=Decimal("1.0"),
        lunghezza_standard_mm=6000,
    )
    sessione.add(profilo)
    colore = Colore(codice_normalizzato="AN007", nome_visualizzato="Antracite")
    sessione.add(colore)
    sessione.flush()
    z = Pezzo(
        profilo=profilo,
        colore=colore,
        lunghezza_mm=6000,
        quantita=5,
        barcode="AB12-AN007-6000",
    )
    sessione.add(z)
    sessione.commit()
    id_pezzo = z.id
    sessione.close()
    return id_pezzo


def test_imposta_scorta_minima(factory, pezzo):
    sessione = factory()
    risultato = imposta_scorta_minima(sessione, pezzo, 10)
    assert risultato.scorta_minima == 10
    assert factory().get(Pezzo, pezzo).scorta_minima == 10
    sessione.close()


def test_imposta_scorta_minima_zero(factory, pezzo):
    """Zero è ammesso: soglia zero = nessun avviso."""
    sessione = factory()
    assert imposta_scorta_minima(sessione, pezzo, 0).scorta_minima == 0
    sessione.close()


def test_imposta_scorta_minima_none_cancella(factory, pezzo):
    """None cancella la soglia (campo NULL)."""
    s1 = factory()
    imposta_scorta_minima(s1, pezzo, 10)
    s1.close()
    s2 = factory()
    assert imposta_scorta_minima(s2, pezzo, None).scorta_minima is None
    assert factory().get(Pezzo, pezzo).scorta_minima is None
    s2.close()


def test_imposta_scorta_minima_negativa_solleva(factory, pezzo):
    sessione = factory()
    with pytest.raises(ValueError):
        imposta_scorta_minima(sessione, pezzo, -1)
    # Nessun dato modificato.
    assert sessione.get(Pezzo, pezzo).scorta_minima is None
    sessione.close()


def test_imposta_scorta_minima_pezzo_manca(factory):
    sessione = factory()
    with pytest.raises(ValueError):
        imposta_scorta_minima(sessione, 9999, 5)
    sessione.close()
