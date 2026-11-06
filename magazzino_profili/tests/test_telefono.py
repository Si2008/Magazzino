"""Test del servizio telefono: coda scansioni, ping e lettura url_pubblico."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from magazzino_profili.db import crea_session_factory
from magazzino_profili.domain import Base, ScansioneTelefono
from magazzino_profili.services import telefono


@pytest.fixture()
def factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return crea_session_factory(engine)


# ----------------------------------------------------------------------
# registra_scansione
# ----------------------------------------------------------------------
def test_registra_scansione_normalizza_il_barcode(factory):
    sessione = factory()
    try:
        id_riga = telefono.registra_scansione(sessione, " ab12-an007-6000 ", "maria")
    finally:
        sessione.close()
    sessione = factory()
    try:
        riga = sessione.get(ScansioneTelefono, id_riga)
        assert riga.barcode == "AB12-AN007-6000"
        assert riga.letta is False
    finally:
        sessione.close()


def test_registra_scansione_barcode_vuoto_solleva_valueerror(factory):
    sessione = factory()
    try:
        with pytest.raises(ValueError):
            telefono.registra_scansione(sessione, "   ", "maria")
        with pytest.raises(ValueError):
            telefono.registra_scansione(sessione, None, "maria")
        assert sessione.scalars(select(ScansioneTelefono)).all() == []
    finally:
        sessione.close()


# ----------------------------------------------------------------------
# preleva_scansioni
# ----------------------------------------------------------------------
def test_preleva_scansioni_ordine_e_una_sola_volta(factory):
    s1 = factory()
    try:
        telefono.registra_scansione(s1, "PRIMO-1", "maria")
    finally:
        s1.close()
    s2 = factory()
    try:
        telefono.registra_scansione(s2, "SECONDO-2", "maria")
    finally:
        s2.close()
    s = factory()
    try:
        assert telefono.preleva_scansioni(s) == ["PRIMO-1", "SECONDO-2"]
    finally:
        s.close()
    s = factory()
    try:
        assert telefono.preleva_scansioni(s) == []
    finally:
        s.close()


def test_preleva_scansioni_scorre_quella_vecchia_ma_la_segna_letta(factory):
    """Scansione di 5 minuti fa: NON restituita, ma segnata letta."""
    sessione = factory()
    try:
        riga = ScansioneTelefono(
            barcode="VECCHIO-1",
            utente="maria",
            creata_il=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        sessione.add(riga)
        sessione.commit()
    finally:
        sessione.close()
    s2 = factory()
    try:
        assert telefono.preleva_scansioni(s2) == []
    finally:
        s2.close()
    s3 = factory()
    try:
        assert sessione_get(s3, 1).letta is True
    finally:
        s3.close()


def sessione_get(sessione: Session, id_riga: int) -> ScansioneTelefono:
    return sessione.get(ScansioneTelefono, id_riga)


# ----------------------------------------------------------------------
# scarta_arretrate
# ----------------------------------------------------------------------
def test_scarta_arretrate_segna_lette_e_cancella_le_vecchie(factory):
    s1 = factory()
    s2 = factory()
    try:
        telefono.registra_scansione(s1, "A-1", "maria")
        telefono.registra_scansione(s2, "B-2", "maria")
    finally:
        s1.close()
        s2.close()
    # Una riga già letta con data di 2 giorni fa: va cancellata.
    sessione = factory()
    try:
        riga = ScansioneTelefono(
            barcode="VECCHIO-LETTA",
            utente="maria",
            letta=True,
            creata_il=datetime.now(timezone.utc) - timedelta(days=2),
        )
        sessione.add(riga)
        sessione.commit()
    finally:
        sessione.close()

    sessione = factory()
    try:
        assert telefono.scarta_arretrate(sessione) == 2
    finally:
        sessione.close()

    # Le due scansioni restano (letta=True, recenti); quella vecchia è cancellata.
    sessione = factory()
    try:
        righe = sessione.scalars(select(ScansioneTelefono)).all()
        assert [r.barcode for r in righe] == ["A-1", "B-2"]
        assert all(r.letta for r in righe)
    finally:
        sessione.close()

    sessione = factory()
    try:
        assert telefono.scarta_arretrate(sessione) == 0  # niente in coda, niente da cancellare
        assert [r.barcode for r in sessione.scalars(select(ScansioneTelefono)).all()] == ["A-1", "B-2"]
    finally:
        sessione.close()


# ----------------------------------------------------------------------
# telefono_collegato / registra_ping
# ----------------------------------------------------------------------
def test_telefono_collegato_finestra_di_tempo(factory):
    # Ogni chiamata al servizio usa una sessione nuova (regola transazionale).
    s = factory()
    try:
        assert telefono.telefono_collegato(s) is False  # nessun ping
    finally:
        s.close()

    momento = datetime.now(timezone.utc)
    s = factory()
    try:
        telefono.registra_ping(s, adesso=momento)
    finally:
        s.close()

    for offset, atteso in ((0, True), (29, True), (31, False)):
        s = factory()
        try:
            assert telefono.telefono_collegato(s, adesso=momento + timedelta(seconds=offset)) is atteso
        finally:
            s.close()


def test_telefono_collegato_valore_non_interpretabile(factory):
    from magazzino_profili.domain import Impostazione

    sessione = factory()
    try:
        sessione.add(Impostazione(chiave=telefono.CHIAVE_PING, valore="non-una-data"))
        sessione.commit()
        assert telefono.telefono_collegato(sessione) is False
    finally:
        sessione.close()


# ----------------------------------------------------------------------
# leggi_url_pubblico
# ----------------------------------------------------------------------
def test_leggi_url_pubblico_con_chiave(tmp_path):
    file = tmp_path / "config.toml"
    file.write_text('[web]\nurl_pubblico = "https://x.example/"\n', encoding="utf-8")
    assert telefono.leggi_url_pubblico(file) == "https://x.example/"


def test_leggi_url_pubblico_senza_chiave(tmp_path):
    file = tmp_path / "config.toml"
    file.write_text('[web]\nporta = 8443\n', encoding="utf-8")
    assert telefono.leggi_url_pubblico(file) is None


def test_leggi_url_pubblico_file_inesistente(tmp_path):
    assert telefono.leggi_url_pubblico(tmp_path / "config.toml") is None
