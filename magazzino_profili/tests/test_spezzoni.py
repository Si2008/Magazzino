"""Test del servizio spezzoni (scarti di taglio e riutilizzo)."""

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from magazzino_profili.db import crea_session_factory
from magazzino_profili.domain import Base, Colore, Pezzo, Profilo, Spezzone
from magazzino_profili.services import (
    SpezzoneNonTrovatoError,
    registra_spezzone,
    utilizza_spezzone,
)

SOGLIA_MINIMA_MM = 100


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    # expire_on_commit=False: dopo il commit gli attributi restano
    # caricati e non aprono transazioni implicithe di refresh.
    factory = crea_session_factory(engine)
    s = factory()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture()
def pezzo_origine(session: Session) -> Pezzo:
    """Pezzo di giacenza da cui derivare lo spezzone."""
    profilo = Profilo(
        codice="AB12",
        descrizione="Profilo di prova",
        peso_kg_per_metro=1.0,
        lunghezza_standard_mm=6000,
    )
    colore = Colore(codice_normalizzato="AN007", nome_visualizzato="Antracite")
    session.add_all([profilo, colore])
    session.flush()
    pezzo = Pezzo(
        profilo=profilo,
        colore=colore,
        lunghezza_mm=6000,
        quantita=1,
        barcode="AB12-AN007-6000",
    )
    session.add(pezzo)
    session.commit()
    return pezzo


def test_spezzone_sotto_soglia_non_creato(session: Session, pezzo_origine) -> None:
    """Sotto soglia minima: niente spezzone, restituisce None."""
    risultato = registra_spezzone(
        session,
        pezzo_origine_id=pezzo_origine.id,
        lunghezza_mm=50,
        soglia_minima_mm=SOGLIA_MINIMA_MM,
        utente="operatore",
    )

    assert risultato is None
    assert session.scalar(select(func.count(Spezzone.id))) == 0


def test_spezzone_sopra_soglia_creato(session: Session, pezzo_origine) -> None:
    """Sopra soglia minima: spezzone creato con utilizzato = False
e l'utente che lo ha registrato."""
    spezzone = registra_spezzone(
        session,
        pezzo_origine_id=pezzo_origine.id,
        lunghezza_mm=450,
        soglia_minima_mm=SOGLIA_MINIMA_MM,
        utente="operatore",
    )

    assert spezzone is not None
    assert spezzone.lunghezza_mm == 450
    assert spezzone.utilizzato is False
    assert spezzone.pezzo_origine_id == pezzo_origine.id
    # L'utente che ha registrato lo spezzone è valorizzato.
    assert spezzone.utente == "operatore"
    assert session.scalar(select(func.count(Spezzone.id))) == 1


def test_utilizza_spezzone(session: Session, pezzo_origine) -> None:
    """L'utilizzo segna lo spezzone e registra l'utente; la seconda
    volta è senza effetto."""
    spezzone = registra_spezzone(
        session,
        pezzo_origine_id=pezzo_origine.id,
        lunghezza_mm=450,
        soglia_minima_mm=SOGLIA_MINIMA_MM,
        utente="operatore",
    )

    aggiornato = utilizza_spezzone(session, spezzone.id, utente="operatore")
    assert aggiornato.utilizzato is True
    # L'utente che ha riutilizzato lo spezzone è valorizzato.
    assert aggiornato.utente == "operatore"

    # Idempotente: riusare non cambia nulla (nemmeno l'utente).
    ancora = utilizza_spezzone(session, spezzone.id, utente="altro_operatore")
    assert ancora.utilizzato is True
    assert ancora.utente == "operatore"


def test_utilizza_spezzone_inesistente(session: Session) -> None:
    """Spezzone inesistente: eccezione dedicata."""
    with pytest.raises(SpezzoneNonTrovatoError):
        utilizza_spezzone(session, 9999, utente="operatore")
