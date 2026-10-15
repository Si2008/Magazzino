"""Screenshot di tutte le schede (scuro + chiaro) a 1700x1000.

Uso: ``python screenshot_fase5.py [prefisso]`` (prefisso di default "prima").
I file finiscono in ``fase5/``.
"""

import os
import sys
from decimal import Decimal
from pathlib import Path

# Default: piattaforma reale (windows), perché la piattaforma "offscreen"
# di PySide6 su questa macchina non carica NESSUNA famiglia di font (testi
# a quadretto). "offscreen" resta disponibile forzando QT_QPA_PLATFORM.
# La finestra NON viene mostrata: usiamo solo widget.grab().

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtWidgets import QApplication  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402

from magazzino_profili.db import crea_session_factory  # noqa: E402
from magazzino_profili.domain import Base, Colore, Pezzo, Profilo  # noqa: E402
from magazzino_profili.sicurezza import Ruolo  # noqa: E402


def _dati(factory) -> None:
    """Un profilo, tre colori (BIANCO senza pezzi) e due giacenze."""
    sessione = factory()
    profilo = Profilo(
        codice="AB12",
        descrizione="Angolare 12x12",
        peso_kg_per_metro=Decimal("1.2500"),
        lunghezza_standard_mm=6000,
    )
    antracite = Colore(codice_normalizzato="AN007", nome_visualizzato="Antracite")
    bianco = Colore(codice_normalizzato="BIANCO", nome_visualizzato="Bianco")
    ral = Colore(codice_normalizzato="RAL9010", nome_visualizzato="RAL 9010")
    sessione.add_all([profilo, antracite, bianco, ral])
    sessione.flush()
    sessione.add_all(
        [
            Pezzo(
                profilo=profilo,
                colore=antracite,
                lunghezza_mm=6000,
                quantita=10,
                barcode="AB12-AN007-6000",
                ubicazione="Vassoio 1",
                scorta_minima=2,
            ),
            Pezzo(
                profilo=profilo,
                colore=ral,
                lunghezza_mm=6000,
                quantita=5,
                barcode="AB12-RAL9010-6000",
                ubicazione="Vassoio 2",
                scorta_minima=20,  # sotto scorta → avviso
            ),
        ]
    )
    sessione.commit()
    sessione.close()


def main(prefisso: str) -> None:
    cartella = Path(__file__).resolve().parent / "fase5"
    cartella.mkdir(exist_ok=True)
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = crea_session_factory(engine)
    _dati(factory)

    from magazzino_profili.ui import FinestraPrincipale, tema  # noqa: E402

    app = QApplication([])
    finestra = FinestraPrincipale(factory, Ruolo.AMMINISTRATORE, "simone")
    nomi = {0: "inventario", 1: "carico", 2: "scarico", 3: "profili", 4: "avvisi"}
    for tema_nome in ("scuro", "chiaro"):
        scuro_ora = tema.tema_attivo().sfondo in ("#12141a", "#16181d")
        if (tema_nome == "scuro") != scuro_ora:
            tema.alterna_tema()
        for idx in range(min(5, finestra._tab.count())):
            finestra._tab.setCurrentIndex(idx)
            finestra.resize(1700, 1000)
            app.processEvents()
            app.processEvents()
            nome = nomi.get(idx, f"tab{idx}")
            file = cartella / f"{prefisso}_{tema_nome}_{nome}.png"
            finestra.grab().save(str(file))
            print(f"salvato {file}")
    finestra.close()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "prima")
