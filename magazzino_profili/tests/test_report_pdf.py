"""Test del esportazione PDF stampabile.

Uses an SQLite database in memory: the report does not depend on the
dialect of the database.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from magazzino_profili.db import crea_session_factory
from magazzino_profili.domain import Base, Pezzo, Profilo
from magazzino_profili.reports import esporta_inventario_pdf
from magazzino_profili.reports.export_pdf import INTESTAZIONI
from magazzino_profili.services import carica
import pypdf


@pytest.fixture()
def factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return crea_session_factory(engine)


def _fields(cls: type) -> list[str]:
    return [c.key for c in cls.__dict__.values() if hasattr(c, "key") and c.key != "id"]


def _add_two_pozzi(factory) -> list[str]:
    """Adds a Profilo and two pieces, returning their barcodes."""
    s = factory()
    prof = Profilo()
    for nome, value in zip(_fields(Profilo), ("AB12", "Profilo test", None, 1.25, 6000)):
        setattr(prof, nome, value)
    s.add(prof)
    s.commit()

    first = carica(s, "ab 12", "an 007", 6000, 5, "operator", "Arrival")
    second = carica(s, "AB12", "an 007", 3000, 1, "operator", "Arrival")
    return [first.barcode, second.barcode]


def test_report_pdf_content(factory, tmp_path) -> None:
    """The PDF contains the header and a row per piece."""
    barcodes = _add_two_pozzi(factory)

    out = esporta_inventario_pdf(factory(), tmp_path / "inv.pdf")
    assert out.exists()
    assert out.stat().st_size > 500

    document = pypdf.PdfReader(str(out))
    assert len(document.pages) >= 1

    text = "\n".join(page.extract_text() or "" for page in document.pages)
    for intestazione in INTESTAZIONI:
        assert intestazione in text
    for barcode in barcodes:
        assert barcode in text


def test_report_pdf_empty_inventory(factory, tmp_path) -> None:
    """An inventory with no pieces still produces a valid PDF."""
    out = esporta_inventario_pdf(factory(), tmp_path / "empty.pdf")
    assert out.exists()

    document = pypdf.PdfReader(str(out))
    assert len(document.pages) == 1
    text = document.pages[0].extract_text() or ""
    assert INTESTAZIONI[-1] in text
