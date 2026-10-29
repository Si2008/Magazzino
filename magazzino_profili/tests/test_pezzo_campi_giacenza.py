"""Fase 6: campi giacenza sul modello e migrazioni 004/005.

Verifica (su SQLite, come gli altri test) che il modello esporti i
quattro nuovi campi, che il vincolo ``stato_valido`` rifiuti stati
esterni a Caricato/Scaricato (NULL consentito) e che, applicando le
nuove colonne a un'installazione esistente, i record storici restino
invariati (campi NULL). Le migrazioni 004/005 in sé sono per
PostgreSQL: i test reali vivono in ``test_migrazioni_postgres.py``
(skip senza ``MAGAZZINO_PG_URL``).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from magazzino_profili.domain import Base, Colore, Pezzo, Profilo

CARTELLA_MIGRAZIONI = Path(__file__).resolve().parents[2] / "migrations"


@pytest.fixture()
def engine():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    yield e
    e.dispose()


@pytest.fixture()
def sessione(engine):
    with Session(engine, expire_on_commit=False) as s:
        yield s


def _popola(sessione) -> Pezzo:
    profilo = Profilo(
        codice="PRF6", descrizione="Test Fase 6",
        peso_kg_per_metro=1.0, lunghezza_standard_mm=6000,
    )
    sessione.add(profilo)
    sessione.flush()
    colore = Colore(codice_normalizzato="AL", nome_visualizzato="Aluminium")
    sessione.add(colore)
    sessione.flush()
    pezzo = Pezzo(
        profilo_id=profilo.id,
        colore_id=colore.id,
        lunghezza_mm=1000,
        quantita=4,
        barcode="PRF6-AL-1000",
    )
    sessione.add(pezzo)
    sessione.flush()
    return pezzo


def test_modello_espone_campi_giacenza(sessione):
    nomi = [c.name for c in inspect(Pezzo.__table__).columns]
    for campo in ("numero_vassoio", "stato", "data_ultimo_cambio_stato", "eliminato_il"):
        assert campo in nomi, f"manca la colonna {campo}"
    assert Pezzo.numero_vassoio.property.columns[0].nullable
    assert Pezzo.stato.property.columns[0].nullable
    assert Pezzo.data_ultimo_cambio_stato.property.columns[0].nullable
    assert Pezzo.eliminato_il.property.columns[0].nullable
    # l'indice richiesto dalla Fase 6 (stesso nome del modello)
    assert "ix_pezzi_eliminato_il" in {
        i.name for i in inspect(Pezzo.__table__).indexes
    }


def test_vincolo_stato_rifiuta_valore_esterno(sessione):
    pezzo = _popola(sessione)
    pezzo.stato = "C"
    with pytest.raises(IntegrityError):
        sessione.flush()


def test_vincolo_stato_accetta_caricato_scaricato_null(sessione):
    pezzo = _popola(sessione)
    assert pezzo.stato is None  # record storico: NULL è ammesso
    ora = datetime.now(UTC)
    for stato in ("Caricato", "Scaricato", None):
        pezzo.stato = stato
        if stato is not None:
            pezzo.data_ultimo_cambio_stato = ora
        assert sessione.flush() is None
    assert pezzo.stato is None


def test_eliminazione_logica_preserva_record(sessione):
    """eliminato_il valorizzato: il record esiste ancora ma non è più attivo."""
    pezzo = _popola(sessione)
    assert pezzo.eliminato_il is None
    ora = datetime.now(UTC)
    pezzo.eliminato_il = ora
    sessione.flush()
    assert pezzo.eliminato_il == ora
    # cancellazione logica: la riga non è rimossa dalla tabella
    sessione.expire_all()
    assert sessione.get(Pezzo, pezzo.id) is not None


def test_applicazione_esistente_registra_null():
    """Nuove colonne su un'installazione esistente: i dati storici restano NULL.

    Su SQLite si emula la migrazione additiva con ``ADD COLUMN``
    (stessa semantica di ``004_campi_giacenza.sql``); le prime tre
    migrazioni non vengono modificate.
    """
    engine = create_engine("sqlite://")
    # 1) installazione "esistente": schema senza i quattro campi nuovi
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE profili (id INTEGER PRIMARY KEY, codice TEXT, "
            "descrizione TEXT, peso_kg_per_metro NUMERIC, lunghezza_standard_mm INTEGER)"
        ))
        conn.execute(text(
            "CREATE TABLE colori (id INTEGER PRIMARY KEY, "
            "codice_normalizzato TEXT, nome_visualizzato TEXT)"
        ))
        conn.execute(text(
            "CREATE TABLE pezzi (id INTEGER PRIMARY KEY, profilo_id INTEGER, "
            "colore_id INTEGER, lunghezza_mm INTEGER, quantita INTEGER, "
            "barcode TEXT, ubicazione TEXT, scorta_minima INTEGER)"
        ))
        conn.execute(text(
            "INSERT INTO pezzi (profilo_id, colore_id, lunghezza_mm, quantita, barcode) "
            "VALUES (1, 1, 1000, 4, 'PRF6-AL-1000')"
        ))
    # 2) aggiornamento: colonne aggiuntive (equivalente di 004, semantica additiva)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE pezzi ADD COLUMN numero_vassoio VARCHAR(128)"))
        conn.execute(text("ALTER TABLE pezzi ADD COLUMN stato VARCHAR(16)"))
        conn.execute(text("ALTER TABLE pezzi ADD COLUMN data_ultimo_cambio_stato TIMESTAMP"))
        conn.execute(text("ALTER TABLE pezzi ADD COLUMN eliminato_il TIMESTAMP"))
        conn.execute(text("CREATE INDEX ix_pezzi_eliminato_il ON pezzi (eliminato_il)"))
    # 3) i record storici restano invariati (campi NULL)
    with engine.connect() as conn:
        riga = conn.execute(text("SELECT * FROM pezzi")).mappings().one()
    assert riga["quantita"] == 4 and riga["barcode"] == "PRF6-AL-1000"
    assert riga["numero_vassoio"] is None
    assert riga["stato"] is None
    assert riga["data_ultimo_cambio_stato"] is None
    assert riga["eliminato_il"] is None
    engine.dispose()


def test_file_migrazioni_presenza_e_additivita():
    """001-003 restano originali; 004/005 esistono e sono solo additivi."""
    nomi = sorted(f.name for f in CARTELLA_MIGRAZIONI.glob("*.sql"))
    for obbligatorio in (
        "001_scorta_minima.sql", "002_impostazioni.sql", "003_scansioni_telefono.sql",
        "004_campi_giacenza.sql", "005_vincolo_stato.sql",
    ):
        assert obbligatorio in nomi
    mig04 = (CARTELLA_MIGRAZIONI / "004_campi_giacenza.sql").read_text(encoding="utf-8").upper()
    assert "DROP TABLE" not in mig04 and "DELETE" not in mig04 and "UPDATE PEZZI" not in mig04
    mig05 = (CARTELLA_MIGRAZIONI / "005_vincolo_stato.sql").read_text(encoding="utf-8").upper()
    assert "DROP TABLE" not in mig05 and "DELETE" not in mig05
    assert "CK_PEZZI_STATO_VALIDO" in mig05 and "'CARICATO'" in mig05 and "'SCARICATO'" in mig05
