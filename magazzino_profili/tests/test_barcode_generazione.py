"""Test della generazione dell'immagine barcode Code 128 (PNG)."""

from pathlib import Path

import pytest
from PIL import Image

from magazzino_profili.barcode import genera_immagine_barcode


def test_immagine_creata_per_valore_noto(tmp_path):
    """Un valore noto genera un PNG esistente, non vuoto e leggibile."""
    out = genera_immagine_barcode("AB12-AN007-6000", tmp_path / "barcode.png")
    assert isinstance(out, str)
    file = Path(out)
    assert file.exists()
    assert file.stat().st_size > 0

    with Image.open(file) as img:
        assert img.format == "PNG"
        assert img.size[0] > 0 and img.size[1] > 0


def test_valore_non_valido_solleva_value_error_senza_file(tmp_path):
    """Un valore non valido solleva ValueError e non crea alcun file."""
    destinazione = tmp_path / "non_deve_esistere.png"
    with pytest.raises(ValueError):
        genera_immagine_barcode("ab 12", destinazione)

    assert not destinazione.exists()
    assert list(tmp_path.iterdir()) == []


def test_valore_vuoto_solleva_value_error(tmp_path):
    """Il valore vuoto (o solo spazi) è rifiutato senza creare file."""
    destinazione = tmp_path / "vuoto.png"
    with pytest.raises(ValueError):
        genera_immagine_barcode("   ", destinazione)
    assert not destinazione.exists()
