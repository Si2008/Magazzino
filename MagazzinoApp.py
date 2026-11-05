"""Entry point of the executable: imports the package and calls :func:`main`."""

import sys

if __name__ == "__main__":
    if "--server-telefono" in sys.argv:
        # PyInstaller windowed imposta stdout/stderr a None anche con pipe.
        if sys.stdout is None or sys.stderr is None:
            import os
            from pathlib import Path
            cartella = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "magazzino_profili"
            cartella.mkdir(parents=True, exist_ok=True)
            registro = (cartella / "telefono-server.log").open("a", encoding="utf-8", buffering=1)
            sys.stdout = sys.stderr = registro
        from magazzino_profili.web.app import main
    else:
        from magazzino_profili.services.aggiornamenti import avvia_versione_attiva
        if avvia_versione_attiva():
            sys.exit(0)
        from magazzino_profili.main import main
    sys.exit(main())
