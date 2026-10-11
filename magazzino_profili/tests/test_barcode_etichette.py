"""Test della generazione dell'etichetta PDF.

Usano un database SQLite in memoria: l'etichetta è generata da un
pezzo reale creato col servizio ``carica``, così il test copre anche
il collegamento con il campo ``barcode`` del dominio.
"""

from decimal import Decimal
from pathlib import Path

import pytest
from pypdf import PdfReader
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from magazzino_profili.barcode import genera_etichetta_pdf
from magazzino_profili.db import crea_session_factory
from magazzino_profili.domain import Base, Pezzo, Profilo
from magazzino_profili.services import carica

PT_PER_MM = 72 / 25.4


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
    """Nomi delle colonne dichiarate (senza l'id autoincremento)."""
    return [c.key for c in cls.__dict__.values() if hasattr(c, "key") and c.key != "id"]


def _aggiungi_pezzo(session: Session) -> Pezzo:
    """Inserisce un Profilo e restituisce il pezzo creato da ``carica``."""
    prof = Profilo()
    for nome, value in zip(_fields(Profilo), ("AB12", "Profilo test", None, Decimal("1.2500"), 6000)):
        setattr(prof, nome, value)
    session.add(prof)
    session.commit()
    return carica(session, "ab 12", "an 007", 6000, 5, "operatore", "Arrivo")


def test_etichetta_crea_pdf_con_dimensioni_corrette(tmp_path, session):
    """L'etichetta è un PDF esistente, non vuoto, con la pagina delle
    dimensioni richieste (mm) e il contenuto del pezzo."""
    pezzo = _aggiungi_pezzo(session)

    out = genera_etichetta_pdf(pezzo, tmp_path / "etichetta.pdf", 60.0, 30.0)
    file = Path(out)
    assert file.exists()
    assert file.stat().st_size > 0

    pagina = PdfReader(str(file)).pages[0]
    assert float(pagina.mediabox.width) == pytest.approx(60 * PT_PER_MM, abs=0.01)
    assert float(pagina.mediabox.height) == pytest.approx(30 * PT_PER_MM, abs=0.01)

    testo = pagina.extract_text() or ""
    assert pezzo.barcode in testo
    assert "Profilo test" in testo
    assert "6000 mm" in testo


def test_etichetta_non_lascia_file_png_intermedi(tmp_path, session):
    """L'immagine barcode intermedia è temporanea: nella cartella di
    destinazione resta solo il PDF, nessun PNG permanente."""
    pezzo = _aggiungi_pezzo(session)

    out = genera_etichetta_pdf(pezzo, tmp_path / "etichetta.pdf", 60.0, 30.0)
    assert Path(out).exists()

    png = [p for p in Path(tmp_path).iterdir() if p.suffix.lower() == ".png"]
    assert png == []


def test_etichetta_rifiuta_pezzo_senza_barcode(tmp_path, session):
    """Un pezzo senza barcode non può avere un'etichetta."""
    pezzo = _aggiungi_pezzo(session)
    pezzo.barcode = ""
    with pytest.raises(ValueError):
        genera_etichetta_pdf(pezzo, tmp_path / "vuoto.pdf", 60.0, 30.0)
