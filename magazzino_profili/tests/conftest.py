"""Le animazioni sono spente nei test: stato finale immediato, nessuna attesa asincrona."""

import os

os.environ.setdefault("MAGAZZINO_NO_ANIM", "1")


# ---------------------------------------------------------------------------
# Fase 7: il catalogo immagini nei test punta SEMPRE a una cartella isolata,
# mai alla ``catalogo_immagini/`` reale del progetto.
# ---------------------------------------------------------------------------
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


@pytest.fixture(autouse=True)
def registro_colori_isolato(monkeypatch):
    """Ogni DB sintetico ha registro e segnali propri; nessun listener di altri test."""
    from magazzino_profili.ui import registro_colori as registro
    monkeypatch.setattr(registro, "_REGISTRO", registro.RegistroColori())
    monkeypatch.setattr(registro, "SEGNALATORE", registro._Segnalatore())


@pytest.fixture(autouse=True)
def catalogo_isolato(tmp_path_factory, monkeypatch):
    # Fuori dal tmp_path del singolo test: alcuni test preesistenti
    # verificano il contenuto esatto del proprio tmp_path.
    cartella = tmp_path_factory.mktemp("catalogo_fase7")
    monkeypatch.setenv("MAGAZZINO_CATALOGO_IMMAGINI", str(cartella))
    return cartella
