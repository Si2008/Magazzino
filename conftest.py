"""Conftest radice: assicura che la radice del progetto sia in sys.path
per l'import del pacchetto ``magazzino_profili`` dai test.

Fissa anche la piattaforma Qt in modalità headless PRIMA che i test
importino PySide6 (i test dei widget non devono richiedere uno
schermo)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# ---------------------------------------------------------------------------
# Fase 7: il catalogo immagini nei test punta SEMPRE a una cartella isolata,
# mai alla ``catalogo_immagini/`` reale del progetto.
# ---------------------------------------------------------------------------
import os
import sys
from pathlib import Path

import pytest


def pytest_configure(config):
    """Mai consentire test distruttivi PostgreSQL su un database operativo."""
    from sqlalchemy.engine import make_url
    for chiave in ("MAGAZZINO_TEST_DB_URL", "MAGAZZINO_PG_URL"):
        valore = os.environ.get(chiave)
        if valore:
            nome = make_url(valore).database or ""
            if not (nome.endswith("_test") or nome.startswith("test_")):
                raise pytest.UsageError(f"{chiave}: è obbligatorio un database dedicato test_* o *_test")
    # QSettings su Windows usa altrimenti il registro dell'utente reale,
    # anche quando il codice è eseguito da una copia temporanea.
    import tempfile
    from PySide6.QtCore import QSettings
    cartella = tempfile.mkdtemp(prefix="magazzino-preferenze-test-")
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, cartella)

sys.path.insert(0, str(Path(__file__).resolve().parents[0]))


@pytest.fixture(autouse=True)
def catalogo_isolato(tmp_path_factory, monkeypatch):
    # Fuori dal tmp_path del singolo test: alcuni test preesistenti
    # verificano il contenuto esatto del proprio tmp_path.
    cartella = tmp_path_factory.mktemp("catalogo_fase7")
    monkeypatch.setenv("MAGAZZINO_CATALOGO_IMMAGINI", str(cartella))
    return cartella
