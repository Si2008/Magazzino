"""Launcher del executable: used by PyInstaller (see the build script).

Esecuzione from source:: ``python -m magazzino_profili.launch_app``.
"""

from __future__ import annotations

import sys

from .main import main

if __name__ == "__main__":
    sys.exit(main())
