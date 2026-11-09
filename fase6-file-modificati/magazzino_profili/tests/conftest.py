"""Le animazioni sono spente nei test: stato finale immediato, nessuna attesa asincrona."""

import os

os.environ.setdefault("MAGAZZINO_NO_ANIM", "1")
