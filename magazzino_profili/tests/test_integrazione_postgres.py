"""Test di integrazione su un database PostgreSQL reale.

Si eseguono SOLO se la variabile d'ambiente ``MAGAZZINO_TEST_DB_URL``
è impostata (es. ``postgresql://utente:password@host:5432/magazzino_test``);
in caso contrario i test vengono saltati con ``pytest.skip``.

Le tabelle vengono create all'inizio e eliminate alla fine.
"""

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from magazzino_profili.domain import (
    Base,
    Colore,
    Pezzo,
    Profilo,
    QuantitaInsufficienteError,
    TipoMovimento,
    registra_movimento,
)

NOME_VAR_URL = "MAGAZZINO_TEST_DB_URL"

pytestmark = pytest.mark.skipif(
    os.environ.get(NOME_VAR_URL) is None,
    reason=f"variabile d'ambiente {NOME_VAR_URL} non impostata",
)


def _crea_engine() -> object:
    """Engine dal URL nell'ambiente; accetta anche lo schema nudo
    ``postgresql://`` mappandolo sul driver psycopg v3."""
    url = os.environ[NOME_VAR_URL]
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return create_engine(url)


@pytest.fixture()
def session() -> Session:
    """Sessione su PostgreSQL reale: tabelle create prima, eliminate dopo."""
    engine = _crea_engine()
    Base.metadata.create_all(engine)
    with Session(engine) as sessione:
        yield sessione
    sessione.rollback()  # nessun residuo aperto prima di eliminare le tabelle
    Base.metadata.drop_all(engine)


def test_unicita_combinazione_pezzo(session: Session) -> None:
    """Su PostgreSQL reale: UNIQUE su (profilo_id, colore_id, lunghezza_mm)."""
    profilo = Profilo(
        codice="PG01",
        descrizione="Profilo test",
        peso_kg_per_metro=1.0,
        lunghezza_standard_mm=6000,
    )
    colore = Colore(codice_normalizzato="BIANCO", nome_visualizzato="Bianco")
    session.add_all([profilo, colore])
    session.flush()

    session.add(
        Pezzo(profilo=profilo, colore=colore, lunghezza_mm=6000,
              quantita=1, barcode="PG01-BIANCO-6000")
    )
    session.flush()

    session.add(
        Pezzo(profilo=profilo, colore=colore, lunghezza_mm=6000,
              quantita=2, barcode="PG01-BIANCO-6000-BIS")
    )
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_check_quantita_non_negativa(session: Session) -> None:
    """Su PostgreSQL reale: il vincolo CHECK ``quantita >= 0`` è del DB."""
    profilo = Profilo(
        codice="PG02",
        descrizione="Profilo test",
        peso_kg_per_metro=1.0,
        lunghezza_standard_mm=6000,
    )
    colore = Colore(codice_normalizzato="GRIGIO", nome_visualizzato="Grigio")
    session.add_all([profilo, colore])
    session.flush()

    # Inserimento diretto SQL (bypassa il servizio) per provare il vincolo DB.
    with pytest.raises(IntegrityError):
        session.execute(
            text(
                "INSERT INTO pezzi (profilo_id, colore_id, lunghezza_mm, "
                "quantita, barcode) VALUES (:p, :c, 1000, -1, 'PG02-GRIGIO-1000')"
            ),
            {"p": profilo.id, "c": colore.id},
        )
    session.rollback()


def test_scarico_oltre_giacenza(session: Session) -> None:
    """Su PostgreSQL reale: SCARICO oltre la giacenza solleva
    QuantitaInsufficienteError; è il chiamante a decidere su rollback."""
    profilo = Profilo(
        codice="PG03",
        descrizione="Profilo test",
        peso_kg_per_metro=1.0,
        lunghezza_standard_mm=6000,
    )
    colore = Colore(codice_normalizzato="NOCE", nome_visualizzato="Noce")
    session.add_all([profilo, colore])
    session.flush()

    pezzo = Pezzo(profilo=profilo, colore=colore, lunghezza_mm=6000,
                  quantita=1, barcode="PG03-NOCE-6000")
    session.add(pezzo)
    # commit (non solo flush): dopo il rollback di prova l'istanza deve
    # restare persistente nella sessione.
    session.commit()

    with pytest.raises(QuantitaInsufficienteError):
        registra_movimento(
            session, pezzo, TipoMovimento.SCARICO, 2,
            causale="Scarico eccessivo", utente="test",
        )

    # Il chiamante annulla la transazione: la giacenza resta invariata.
    session.rollback()
    assert sessione_dopo_rollback(session, pezzo) == 1


def sessione_dopo_rollback(session: Session, pezzo: Pezzo) -> int:
    """Rilegge la quantità del pezzo dopo il rollback."""
    session.refresh(pezzo, attribute_names=["quantita"])
    return pezzo.quantita
