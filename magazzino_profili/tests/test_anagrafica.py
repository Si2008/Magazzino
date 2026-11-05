"""Test of the anagrafica of the profiles: creation and image import.

Uses an SQLite database in memory.
"""

import hashlib
from PIL import Image
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from magazzino_profili.db import crea_session_factory
from magazzino_profili.domain import Base, Profilo
from magazzino_profili.services import anagrafica


@pytest.fixture()
def factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return crea_session_factory(engine)


def _fields(cls: type) -> list[str]:
    return [c.key for c in cls.__dict__.values() if hasattr(c, "key") and c.key != "id"]


def test_crea_profilo_normaliza(factory) -> None:
    """The code of the profile is stored normalized."""
    prof = anagrafica.crea_profilo(
        factory(),
        "ab 12",
        "Profilo test",
        1.25,
        6000,
        "operator",
    )
    assert prof.codice == "AB12"
    assert prof.lunghezza_standard_mm == 6000


def test_duplicate_profile_raises(factory) -> None:
    """The same code cannot be inserted twice."""
    sessione = factory()
    eccezione = [
        getattr(anagrafica, nome)
        for nome in dir(anagrafica)
        if nome.endswith("Error") and "rofilo" in nome
    ][0]
    anagrafica.crea_profilo(sessione, "AB12", "Profilo", 1.25, 6000, "operator")
    with pytest.raises(eccezione):
        anagrafica.crea_profilo(sessione, "ab 12", "Other", 1.25, 6000, "operator")


def test_image_is_copied(factory, tmp_path) -> None:
    """The import of the section copies the file and saves the path."""
    sessione = factory()
    prof = anagrafica.crea_profilo(sessione, "AB12", "Profilo", 1.25, 6000, "operator")
    sessione.commit()

    original = tmp_path / "original.png"
    Image.new("RGB", (8, 8), "red").save(original)

    destination = anagrafica.associa_immagine_sezione(
        factory(),
        prof.id,
        original,
        tmp_path / "images",
    )
    destination_path = __import__("pathlib").Path(destination)

    assert destination_path.is_file()
    assert destination_path.read_bytes() == original.read_bytes()
    assert destination_path != original

    # The path is saved in the profile (image field).
    stored = factory()
    saved = stored.query(Profilo).filter(Profilo.id == prof.id).one()
    values = [str(getattr(saved, nome, "") or "") for nome in _fields(Profilo)]
    assert any(str(destination_path) in value or destination_path.name in value for value in values)


def test_rimuovi_immagine_sezione(factory, tmp_path) -> None:
    """Rimuove il riferimento ma non tocca il file su disco."""
    sessione = factory()
    prof = anagrafica.crea_profilo(sessione, "AB12", "Profilo", 1.25, 6000, "operator")
    sessione.commit()

    original = tmp_path / "sezione.png"
    Image.new("RGB", (8, 8), "blue").save(original)
    percorso = anagrafica.associa_immagine_sezione(
        factory(), prof.id, original, tmp_path / "images",
    )
    assert factory().get(Profilo, prof.id).immagine_sezione == percorso

    anagrafica.rimuovi_immagine_sezione(factory(), prof.id)
    assert factory().get(Profilo, prof.id).immagine_sezione is None
    assert __import__("pathlib").Path(percorso).is_file()  # file intatto


def test_rimuovi_immagine_sezione_profilo_manca(factory) -> None:
    with pytest.raises(ValueError):
        anagrafica.rimuovi_immagine_sezione(factory(), 9999)
