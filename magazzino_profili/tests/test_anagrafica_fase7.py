"""Fase 7 — anagrafica.associa_immagine_sezione: conflitti di destinazione.

Aggiunte alla suite esistente (test_anagrafica.py non è modificato).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine

from magazzino_profili.db import crea_session_factory
from magazzino_profili.domain import Base, Profilo
from magazzino_profili.services import anagrafica

def png(colore="red"):
    from PIL import Image
    from io import BytesIO
    dati = BytesIO()
    Image.new("RGB", (8, 8), colore).save(dati, format="PNG")
    return dati.getvalue()



@pytest.fixture()
def factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return crea_session_factory(engine)


def _nuovo_profilo(factory) -> int:
    s = factory()
    p = anagrafica.crea_profilo(s, "AB12", "Profilo", 1.25, 6000, "t")
    s.close()
    return p.id


def test_origine_nella_cartella_di_destinazione(factory, tmp_path):
    """Catalogo = cartella di destinazione: nessun SameFileError, nessun duplicato."""
    cartella = tmp_path / "imm"
    cartella.mkdir()
    origine = cartella / "ab12.png"
    origine.write_bytes(png())

    prof = _nuovo_profilo(factory)
    destinazione = anagrafica.associa_immagine_sezione(
        factory(), prof, origine, cartella
    )
    assert destinazione == str(origine.resolve())
    assert list(cartella.glob("*.png")) == [origine]  # nessun duplicato
    assert factory().get(Profilo, prof).immagine_sezione == str(origine.resolve())


def test_destinazione_identica_riusata(factory, tmp_path):
    """Destinazione occupata da un file identico per contenuto: riusato, non duplicato."""
    cartella = tmp_path / "imm"
    cartella.mkdir()
    occupante = cartella / "ab12.png"
    contenuto = png()
    occupante.write_bytes(contenuto)
    origine = tmp_path / "ab12.png"  # stesso nome, stessi byte (copia dell'utente)
    origine.write_bytes(contenuto)

    prof = _nuovo_profilo(factory)
    destinazione = anagrafica.associa_immagine_sezione(factory(), prof, origine, cartella)
    assert destinazione == str(occupante.resolve())
    assert list(cartella.glob("*.png")) == [occupante]


def test_destinazione_differente_suffissata(factory, tmp_path):
    """File diverso per contenuto: nome -<profilo_id>, l'originale non è toccato."""
    cartella = tmp_path / "imm"
    cartella.mkdir()
    occupante = cartella / "ab12.png"
    occupante.write_bytes(png("blue"))
    origine = tmp_path / "ab12.png"
    origine.write_bytes(png())

    prof = _nuovo_profilo(factory)
    destinazione = anagrafica.associa_immagine_sezione(factory(), prof, origine, cartella)
    assert Path(destinazione).name .startswith(f"ab12-{prof}-")
    assert Path(destinazione).read_bytes() == origine.read_bytes()
    assert occupante.read_bytes() == png("blue")  # intatto
    assert factory().get(Profilo, prof).immagine_sezione == str(Path(destinazione).resolve())


def test_percorso_troppo_lungo_valueerror(factory, tmp_path):
    """Il percorso salvato non può superare i 512 caratteri del modello."""
    # 4 livelli annidati da 130 caratteri: sempre > 512 totali, componenti entro il limite NTFS.
    cartella = tmp_path
    for _ in range(4):
        cartella = cartella / ("l" * 130)
    cartella.mkdir(parents=True)
    origine = tmp_path / "ab12.png"
    origine.write_bytes(png())

    prof = _nuovo_profilo(factory)
    with pytest.raises(ValueError, match="troppo lungo"):
        anagrafica.associa_immagine_sezione(factory(), prof, origine, cartella)
    assert factory().get(Profilo, prof).immagine_sezione is None
