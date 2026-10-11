"""Test del modulo di modello dati di "Magazzino Profili".

Le funzioni pure (normalizzazione, barcode) vengono testate senza
database. I test di vincolo (unicità, anti-sottozero) usano un
engine SQLite in memoria: il modello SQLAlchemy è indipendente dal
dialetto, quindi i vincoli dichiarati nel dominio restano validati
in modo identico su PostgreSQL.
"""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine, inspect
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
from magazzino_profili.domain.pezzo import nome_file_sezione
from magazzino_profili.db import genera_barcode, normalizza_codice, normalizza_colore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def session() -> Session:
    """Sessioni su un database SQLite in memoria, tabelle create."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as sessione:
        yield sessione


@pytest.fixture()
def profilo() -> Profilo:
    return Profilo(
        codice="AB 12",
        descrizione="Profilo di prova",
        peso_kg_per_metro=Decimal("1.2500"),
        lunghezza_standard_mm=6000,
    )


@pytest.fixture()
def colore() -> Colore:
    return Colore(
        codice_normalizzato="AN007",
        nome_visualizzato="Antracite",
    )


# ---------------------------------------------------------------------------
# Normalizzazione codici e colori
# ---------------------------------------------------------------------------


class TestNormalizzaCodice:
    def test_spazi_esterni_rimossi(self):
        assert normalizza_codice("  ab 12  ") == "AB12"

    def test_minuscole_diventano_maiuscole(self):
        assert normalizza_codice("abc") == "ABC"

    def test_spazi_interni_rimossi(self):
        assert normalizza_codice("a b c") == "ABC"

    def test_slash_diventa_trattino(self):
        assert normalizza_codice("a/b") == "A-B"

    def test_backslash_diventa_trattino(self):
        assert normalizza_codice("a\\b") == "A-B"

    def test_caso_complessivo(self):
        assert normalizza_codice(" ab/12  x\\y ") == "AB-12X-Y"

    def test_solleva_tipoerror_su_non_testo(self):
        with pytest.raises(TypeError):
            normalizza_codice(123)  # type: ignore[arg-type]


class TestNomeFileSezione:
    def test_codice_con_slash(self):
        assert nome_file_sezione("ab/12") == "AB-12.png"

    def test_spazi_e_minuscole(self):
        assert nome_file_sezione("  alu 40 ") == "ALU40.png"


class TestNormalizzaColore:
    def test_stessa_logica_del_codice(self):
        assert normalizza_colore(" an / 007 ") == "AN-007"

    def test_backslash(self):
        assert normalizza_colore("rosso\\scuro") == "ROSSO-SCURO"


# ---------------------------------------------------------------------------
# Generazione barcode
# ---------------------------------------------------------------------------


class TestGeneraBarcode:
    def test_combinazione_nota(self, profilo, colore):
        assert genera_barcode(profilo, colore, 6000) == "AB12-AN007-6000"

    def test_lunghezza_zero_rifiutata(self, profilo, colore):
        with pytest.raises(ValueError):
            genera_barcode(profilo, colore, 0)

    def test_lunghezza_non_intera_rifiutata(self, profilo, colore):
        with pytest.raises(TypeError):
            genera_barcode(profilo, colore, 6000.5)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Vincoli di database
# ---------------------------------------------------------------------------


class TestVincoli:
    def test_unicita_combinazione_pezzo(self, session: Session, profilo, colore):
        """Due righe con stessa (profilo, colore, lunghezza) sono vietate."""
        session.add(profilo)
        session.add(colore)
        session.flush()

        session.add(
            Pezzo(
                profilo=profilo,
                colore=colore,
                lunghezza_mm=6000,
                quantita=1,
                barcode="AB12-AN007-6000",
            )
        )
        session.flush()

        session.add(
            Pezzo(
                profilo=profilo,
                colore=colore,
                lunghezza_mm=6000,
                quantita=2,
                barcode="AB12-AN007-6000-BIS",
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()

    def test_sottozero_impossibile(self, session: Session, profilo, colore):
        """Uno scarico maggiore della giacenza solleva l'eccezione dedicata."""
        session.add(profilo)
        session.add(colore)
        session.flush()

        pezzo = Pezzo(
            profilo=profilo,
            colore=colore,
            lunghezza_mm=6000,
            quantita=1,
            barcode="AB12-AN007-6000",
        )
        session.add(pezzo)
        session.flush()

        with pytest.raises(QuantitaInsufficienteError):
            registra_movimento(
                session,
                pezzo,
                TipoMovimento.SCARICO,
                2,
                causale="Scarico eccessivo",
                utente="test",
            )

    def test_carico_aggiorna_quantita(self, session: Session, profilo, colore):
        """Un carico passa da Movimento e aumenta la giacenza."""
        session.add(profilo)
        session.add(colore)
        session.flush()

        pezzo = Pezzo(
            profilo=profilo,
            colore=colore,
            lunghezza_mm=6000,
            quantita=0,
            barcode="AB12-AN007-6000",
        )
        session.add(pezzo)
        session.flush()

        movimento = registra_movimento(
            session,
            pezzo,
            TipoMovimento.CARICO,
            5,
            causale="Arrivo fornitore",
            utente="test",
        )
        session.flush()
        assert movimento.quantita == 5
        assert pezzo.quantita == 5
