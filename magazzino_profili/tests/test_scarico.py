"""Test del servizio di scarico (uscita di un pezzo esistente)."""

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from magazzino_profili.db import crea_session_factory
from magazzino_profili.domain import (
    Base,
    Colore,
    Movimento,
    Pezzo,
    Profilo,
    QuantitaInsufficienteError,
)
from magazzino_profili.services import PezzoNonTrovatoError, scarica


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
def pezzo_con_giacenza(session: Session) -> Pezzo:
    """Pezzo già in giacenza (giacenza = 1), creato per il test."""
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


def test_scarico_oltre_giacenza_non_modifica(session: Session, pezzo_con_giacenza) -> None:
    """Scarico maggiore della giacenza: eccezione, niente movimento."""
    with pytest.raises(QuantitaInsufficienteError):
        scarica(
            session,
            barcode="AB12-AN007-6000",
            quantita=2,
            utente="operatore",
            causale="Scarico eccessivo",
        )

    session.refresh(pezzo_con_giacenza)
    assert pezzo_con_giacenza.quantita == 1  # giacenza invariata
    assert session.scalar(select(func.count(Movimento.id))) == 0  # nessun movimento


def test_scarico_barcode_inesistente(session: Session) -> None:
    """Barcode sconosciuto: eccezione dedicata, nessun movimento."""
    with pytest.raises(PezzoNonTrovatoError):
        scarica(
            session,
            barcode="XXXX-9999-1000",
            quantita=1,
            utente="operatore",
            causale="Test",
        )

    assert session.scalar(select(func.count(Movimento.id))) == 0


def test_scarico_riuscita_decrementa(session: Session, pezzo_con_giacenza) -> None:
    """Scarico entro la giacenza: decremento + movimento SCARICO."""
    movimento = scarica(
        session,
        barcode="AB12-AN007-6000",
        quantita=1,
        utente="operatore",
        causale="Uscita per lavorazione",
    )

    session.refresh(pezzo_con_giacenza)
    assert pezzo_con_giacenza.quantita == 0
    assert movimento.tipo.value == "SCARICO"
    assert movimento.quantita == 1
    assert session.scalar(select(func.count(Movimento.id))) == 1
