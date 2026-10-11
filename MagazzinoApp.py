"""Entry point of the executable: imports the package and calls :func:`main`."""

import sys

from magazzino_profili.main import main

if __name__ == "__main__":
    sys.exit(main())
