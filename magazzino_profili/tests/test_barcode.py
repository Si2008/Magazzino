"""Test del barcode: Code 128, PNG and PDF label.

Usano un database SQLite in memoria: the label is generated from a real
piece (created by the service ``carica``), so the test also checks that
the ``barcode`` field corresponds to the piece.
"""

from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from magazzino_profili import barcode as pkg_barcode
from magazzino_profili.db import crea_session_factory
from magazzino_profili.domain import Base, Pezzo, Profilo
from magazzino_profili.services import carica

from PIL import Image
from pypdf import PdfReader


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = crea_session_factory(engine)
    s = factory()
    try:
        yield s
    finally:
        s.rollback()
        s.close()



def _fields(cls: type) -> list[str]:
    # Names of the declared columns (without the autoincrement id).
    return [c.key for c in cls.__dict__.values() if hasattr(c, "key") and c.key != "id"]


def _add_pozione(session: Session) -> Pezzo:
    # Insert a Profilo and return the piece created by carica.
    prof = Profilo()
    for nome, value in zip(_fields(Profilo), ("AB12", "Profilo test", None, Decimal("1.2500"), 6000)):
        setattr(prof, nome, value)
    session.add(prof)
    session.commit()
    return carica(session, "ab 12", "an 007", 6000, 5, "operator", "Arrival")


def test_code128_correspondence_with_the_value(tmp_path):
    """The barcode image must be generated for the value of the field
    ``barcode`` (a real, non-empty PNG)."""
    out = pkg_barcode.genera_immagine_barcode("AB12-AN007-6000", tmp_path / "bc.png")
    assert Path(out).stat().st_size > 0


def test_valore_vuoto_solleva_value_error(tmp_path):
    """An empty value must raise an error (not a barcode unreadable)."""
    with pytest.raises(ValueError):
        pkg_barcode.genera_immagine_barcode("   ", tmp_path / "vuoto.png")


def test_barcode_png_is_a_real_png(tmp_path):
    """The PNG must be a real image readable by Pillow."""
    out = pkg_barcode.salva_barcode_png("AB12-AN007-6000", tmp_path / "bc.png")
    assert out.exists()
    with Image.open(out) as img:
        assert img.format == "PNG"
        assert img.size[0] > 0 and img.size[1] > 0


def test_etichetta_pdf(tmp_path, session):
    """The PDF must be the size of the label and contain the barcode."""
    piece = _add_pozione(session)
    out = Path(pkg_barcode.genera_etichetta_pdf(piece, tmp_path / "et.pdf", 50.0, 25.0))
    assert out.exists()

    page = PdfReader(str(out)).pages[0]
    # 50 mm = 141.73 pt, 25 mm = 70.87 pt (tolerance for float rounding)
    assert float(page.mediabox.width) == pytest.approx(50 * 72 / 25.4, abs=0.01)
    assert float(page.mediabox.height) == pytest.approx(25 * 72 / 25.4, abs=0.01)

    text = page.extract_text()
    assert piece.barcode in text
    assert "AN007" in text
    assert "6000 mm" in text
    assert "Profilo test" in text


def test_label_reads_dimensions_from_config(tmp_path, session):
    """Without dimensions it reads them from ``config.toml``."""
    cfg = tmp_path / "config.toml"
    cfg.write_text('[etichette]\nlarghezza_mm = 40\naltura_mm = 20\n', encoding="utf-8")
    dims = pkg_barcode.leggi_dimensioni_etichetta(cfg)
    assert dims == (40.0, 20.0)

    # Without dimensions it uses the default config (the one of the project).
    default = pkg_barcode.leggi_dimensioni_etichetta()
    piece = _add_pozione(session)
    out = Path(pkg_barcode.genera_etichetta_pdf(piece, tmp_path / "et2.pdf"))
    page = PdfReader(str(out)).pages[0]
    assert float(page.mediabox.width) == pytest.approx(default[0] * 72 / 25.4, abs=0.01)
    assert float(page.mediabox.height) == pytest.approx(default[1] * 72 / 25.4, abs=0.01)
