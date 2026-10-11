"""Conftest radice: assicura che la radice del progetto sia in sys.path
per l'import del pacchetto ``magazzino_profili`` dai test.

Fissa anche la piattaforma Qt in modalità headless PRIMA che i test
importino PySide6 (i test dei widget non devono richiedere uno
schermo)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
