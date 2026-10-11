"""Test del servizio di carico (inserimento facilitato).

Usano un database SQLite in memoria: i servizi sono indipendenti dal
dialetto e i vincoli del dominio restano validati identicamente su
PostgreSQL.
"""

from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from magazzino_profili.db import crea_session_factory
from magazzino_profili.domain import Base, Colore, Movimento, Pezzo, Profilo
from magazzino_profili.services import ProfiloNonTrovatoError, carica


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
def profilo_anagrafica() -> Profilo:
    """Profilo già presente in anagrafica, come in un uso reale."""
    return Profilo(
        codice="AB12",
        descrizione="Profilo di prova",
        peso_kg_per_metro=Decimal("1.2500"),
        lunghezza_standard_mm=6000,
    )


def test_carico_combinazione_inesistente(session: Session, profilo_anagrafica) -> None:
    """Il carico su combinazione inesistente crea colore, pezzo e movimento."""
    session.add(profilo_anagrafica)
    session.commit()

    pezzo = carica(
        session,
        codice="ab 12",          # normalizzato: AB12
        colore="an 007",         # normalizzato: AN007
        lunghezza_mm=6000,
        quantita=3,
        utente="operatore",
        causale="Arrivo fornitore",
    )

    # Colore creato automaticamente: codice normalizzato, nome uguale al codice.
    colori = session.scalars(select(Colore)).all()
    assert len(colori) == 1
    assert colori[0].codice_normalizzato == "AN007"
    assert colori[0].nome_visualizzato == "AN007"

    # Pezzo creato con giacenza pari al carico e barcode generato.
    assert pezzo.quantita == 3
    assert pezzo.barcode == "AB12-AN007-6000"
    assert session.scalar(select(func.count(Pezzo.id))) == 1

    # Movimento CARICO creato nella stessa transazione.
    movimenti = session.scalars(select(Movimento)).all()
    assert len(movimenti) == 1
    assert movimenti[0].tipo.value == "CARICO"
    assert movimenti[0].quantita == 3
    assert movimenti[0].utente == "operatore"


def test_carico_combinazione_esistente_incrementa(session: Session, profilo_anagrafica) -> None:
    """Il carico su combinazione esistente incrementa senza duplicati."""
    session.add(profilo_anagrafica)
    colore = Colore(codice_normalizzato="AN007", nome_visualizzato="Antracite")
    session.add(colore)
    session.flush()
    pezzo = Pezzo(
        profilo=profilo_anagrafica,
        colore=colore,
        lunghezza_mm=6000,
        quantita=2,
        barcode="AB12-AN007-6000",
    )
    session.add(pezzo)
    session.commit()

    risultato = carica(
        session,
        codice="ab 12",
        colore="an 007",
        lunghezza_mm=6000,
        quantita=3,
        utente="operatore",
        causale="Secondo arrivo",
    )

    # Nessun duplicato: stessa riga di giacenza, quantità sommate.
    assert session.scalar(select(func.count(Pezzo.id))) == 1
    assert risultato.quantita == 5
    assert session.scalar(select(func.count(Movimento.id))) == 1


def test_carico_ubicazione_nuovo_pezzo(session: Session, profilo_anagrafica) -> None:
    """Ubicazione fornita: salvata sul pezzo appena creato (testo ripulito)."""
    session.add(profilo_anagrafica)
    session.commit()

    pezzo = carica(
        session,
        codice="AB12",
        colore="AN007",
        lunghezza_mm=6000,
        quantita=1,
        utente="operatore",
        causale="Test",
        ubicazione="  Vassoio 2  ",
    )
    assert pezzo.ubicazione == "Vassoio 2"


def test_carico_ubicazione_pezzo_esistente_vuota(session: Session, profilo_anagrafica) -> None:
    """Pezzo esistente con ubicazione vuota: la imposta."""
    session.add(profilo_anagrafica)
    colore = Colore(codice_normalizzato="AN007", nome_visualizzato="Antracite")
    session.add(colore)
    session.flush()
    pezzo = Pezzo(
        profilo=profilo_anagrafica,
        colore=colore,
        lunghezza_mm=6000,
        quantita=2,
        barcode="AB12-AN007-6000",
        ubicazione=None,
    )
    session.add(pezzo)
    session.commit()

    risultato = carica(
        session,
        codice="AB12",
        colore="AN007",
        lunghezza_mm=6000,
        quantita=1,
        utente="operatore",
        causale="Test",
        ubicazione="Vassoio 3",
    )
    assert risultato.ubicazione == "Vassoio 3"


def test_carico_ubicazione_non_sovrascrive(session: Session, profilo_anagrafica) -> None:
    """Pezzo esistente con ubicazione già presente: non la tocca."""
    session.add(profilo_anagrafica)
    colore = Colore(codice_normalizzato="AN007", nome_visualizzato="Antracite")
    session.add(colore)
    session.flush()
    pezzo = Pezzo(
        profilo=profilo_anagrafica,
        colore=colore,
        lunghezza_mm=6000,
        quantita=2,
        barcode="AB12-AN007-6000",
        ubicazione="Vassoio 1",
    )
    session.add(pezzo)
    session.commit()

    risultato = carica(
        session,
        codice="AB12",
        colore="AN007",
        lunghezza_mm=6000,
        quantita=1,
        utente="operatore",
        causale="Test",
        ubicazione="Vassoio 9",
    )
    assert risultato.ubicazione == "Vassoio 1"


def test_carico_senza_ubicazione_invariato(session: Session, profilo_anagrafica) -> None:
    """Senza il parametro il comportamento è identico al precedente."""
    session.add(profilo_anagrafica)
    session.commit()
    pezzo = carica(
        session,
        codice="AB12",
        colore="AN007",
        lunghezza_mm=6000,
        quantita=1,
        utente="operatore",
        causale="Test",
    )
    assert pezzo.ubicazione is None


def test_carico_profilo_ignoto_solleva(session: Session) -> None:
    """Se il profilo non è in anagrafica: eccezione e nessun dato creato."""
    with pytest.raises(ProfiloNonTrovatoError):
        carica(
            session,
            codice="ZZ99",
            colore="bianco",
            lunghezza_mm=6000,
            quantita=1,
            utente="operatore",
            causale="Test",
        )

    # Transazione annullata: né colore, né pezzo, né movimento.
    assert session.scalar(select(func.count(Colore.id))) == 0
    assert session.scalar(select(func.count(Pezzo.id))) == 0
    assert session.scalar(select(func.count(Movimento.id))) == 0
