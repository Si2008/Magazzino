"""Test del esport and import of the inventory in CSV.

Uses an SQLite database in memory: the business rules (normalization,
automatic creation of colour and piece) are the ones of the service.
"""

import csv
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from magazzino_profili.db import crea_session_factory
from magazzino_profili.domain import Base, Profilo
from magazzino_profili.reports import esporta_inventario_csv, importa_peczi_csv
from magazzino_profili.reports.export_csv import INTESTAZIONI
from magazzino_profili.services import ProfiloNonTrovatoError, carica


@pytest.fixture()
def factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return crea_session_factory(engine)


def _fields(cls: type) -> list[str]:
    return [c.key for c in cls.__dict__.values() if hasattr(c, "key") and c.key != "id"]


def _add_two_pozzi(factory) -> None:
    """Adds a Profilo and two pieces in the inventory."""
    s = factory()
    prof = Profilo()
    for nome, value in zip(_fields(Profilo), ("AB12", "Profilo test", None, 1.25, 6000)):
        setattr(prof, nome, value)
    s.add(prof)
    s.commit()

    carica(s, "ab 12", "an 007", 6000, 5, "operator", "Arrival")
    carica(s, "AB12", "an 007", 3000, 1, "operator", "Arrival")


def test_csv_has_a_row_per_piece(factory, tmp_path) -> None:
    """The CSV has the header and one row per piece."""
    _add_two_pozzi(factory)

    out = esporta_inventario_csv(factory(), tmp_path / "inv.csv")
    assert out.exists()

    with open(out, encoding="utf-8", newline="") as handle:
        righe = list(csv.reader(handle, delimiter=";"))

    assert tuple(righe[0]) == INTESTAZIONI
    assert len(righe) == 3
    assert {row[3] for row in righe[1:]} == {"6000", "3000"}
    assert {row[6] for row in righe[1:]} == {"AB12-AN007-6000", "AB12-AN007-3000"}


def test_csv_import_is_a_carico(factory, tmp_path) -> None:
    """Importing the exported CSV doubles the quantity, without duplicates."""
    _add_two_pozzi(factory)
    out = esporta_inventario_csv(factory(), tmp_path / "inv.csv")

    imported = importa_peczi_csv(factory(), out, "tester", "Reimport")
    assert imported == 2

    again = esporta_inventario_csv(factory(), tmp_path / "inv2.csv")
    with open(again, encoding="utf-8", newline="") as handle:
        righe = list(csv.reader(handle, delimiter=";"))

    assert len(righe) == 3  # still one row per combination
    assert {row[4] for row in righe[1:]} == {"10", "2"}


def test_csv_import_unknown_profile_raises(factory, tmp_path) -> None:
    """A row with an unknown profile in anagrafica is refused."""
    path = tmp_path / "unknown.csv"
    path.write_text(
        ";".join(INTESTAZIONI) + "\n"
        + "ZZ99;no;Antracite;6000;3;loc;ZZ99-AN007-6000\n",
        encoding="utf-8",
    )
    with pytest.raises(ProfiloNonTrovatoError):
        importa_peczi_csv(factory(), path)


def test_csv_import_bad_header(factory, tmp_path) -> None:
    """A CSV without the mandatory columns raises ValueError."""
    path = tmp_path / "bad.csv"
    path.write_text("Codice profil;Colore\nAB12;AN007\n", encoding="utf-8")
    with pytest.raises(ValueError):
        importa_peczi_csv(factory(), path)
