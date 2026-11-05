"""Fase 9 — wrapper pytest per le prove JavaScript del client del telefono.

Esegue ``tests/js/scansione.test.mjs`` con ``node --test``. Senza Node
il test si salta (le prove JS restano eseguibili a mano).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def test_client_telefono_javascript() -> None:
    node = shutil.which("node")
    if node is None:
        import pytest

        pytest.skip("node non disponibile")
    radice = Path(__file__).resolve().parents[2]
    test_file = radice / "magazzino_profili" / "tests" / "js" / "scansione.test.mjs"
    risultato = subprocess.run(
        [node, "--test", str(test_file)],
        capture_output=True,
        text=True,
        cwd=str(radice),
        timeout=120,
    )
    assert risultato.returncode == 0, risultato.stderr + risultato.stdout
