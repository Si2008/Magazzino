"""Script da riga di comando per l'importazione da ODS.

Usa il modulo applicativo ``magazzino_profili.reports.importa_ods_file``
(lo stesso che usa la voce di menu dell'interfaccia).

Uso::

    python importa_ods.py [percorso-ods] [utente]

Default: C:\\Users\\Simone\\Desktop\\SPEZZONI_pulito.ods, utente "simone".
"""

from __future__ import annotations

import sys
from pathlib import Path

from magazzino_profili.db import (
    crea_engine,
    crea_session_factory,
    leggi_config,
)
from magazzino_profili.reports import importa_ods_file


def main() -> int:
    percorso = Path(
        sys.argv[1]
        if len(sys.argv) > 1
        else r"C:\Users\Simone\Desktop\SPEZZONI_pulito.ods"
    )
    utente = sys.argv[2] if len(sys.argv) > 2 else "simone"

    config = leggi_config()
    engine = crea_engine(config=config)
    factory = crea_session_factory(engine)

    with factory() as sessione:
        statistiche = importa_ods_file(sessione, percorso, utente)

    print()
    print("=== Riepilogo importazione ODS ===")
    for chiave, valore in statistiche.items():
        print(f"  {chiave}: {valore}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
