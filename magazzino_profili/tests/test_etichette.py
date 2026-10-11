"""Test of the printable labels: one label per page of the PDF."""

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from magazzino_profili.db import crea_session_factory
from magazzino_profili.domain import Base, Pezzo, Profilo
from magazzino_profili.services import carica
from magazzino_profili.barcode import genera_sheet_etichette_pdf, genera_etichetta_pdf, leggi_dimensioni_etichetta
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


def _pieces(factory) -> list[Pezzo]:
    s = factory()
    return list(s.query(Pezzo).all())


def test_single_label(factory, tmp_path) -> None:
    """The label of a piece is a PDF with one page and the barcode."""
    barcodes = _add_two_pozzi(factory)
    piece = _pieces(factory)[0]

    out = Path(genera_etichetta_pdf(piece, tmp_path / "label.pdf"))
    assert out.exists()

    document = pypdf.PdfReader(str(out))
    assert len(document.pages) == 1
    text = document.pages[0].extract_text() or ""
    assert piece.barcode in text
    assert barcodes[0] in text or barcodes[1] in text


def test_sheet_one_page_per_piece(factory, tmp_path) -> None:
    """The sheet of labels has one page per selected piece."""
    _add_two_pozzi(factory)
    pieces = _pieces(factory)
    assert len(pieces) == 2

    out = genera_sheet_etichette_pdf(pieces, tmp_path / "labels.pdf")
    assert out.exists()

    document = pypdf.PdfReader(str(out))
    assert len(document.pages) == len(pieces)

    text = "\n".join(page.extract_text() or "" for page in document.pages)
    for piece in pieces:
        assert piece.barcode in text


def test_sheet_empty_raises(factory, tmp_path) -> None:
    """No piece selected: nothing is printed."""
    with pytest.raises(ValueError):
        genera_sheet_etichette_pdf([], tmp_path / "none.pdf")


def test_label_size_from_config() -> None:
    """The default label size comes from config.toml."""
    width_mm, height_mm = leggi_dimensioni_etichetta()
    assert (width_mm, height_mm) == (60.0, 30.0)
