"""Pacchetto barcode: generazione Code 128, etichette PDF e scanner.

API pubblica::

    valida_per_barcode(valore) -> bool
    genera_immagine_barcode(valore, percorso) -> str
    genera_etichetta_pdf(pezzo, percorso, larghezza_mm, altezza_mm) -> str
    genera_sheet_etichette_pdf(pezzi, percorso, ...) -> Path
    leggi_dimensioni_etichetta(percorso_config=None) -> (larghezza_mm, altezza_mm)
    salva_barcode_png(valore, percorso) -> Path    # compatibilità API precedente
    CampoScanner                              # QLineEdit con segnale barcode_scansionato
"""

from .etichette import (
    genera_etichetta_pdf,
    genera_sheet_etichette_pdf,
    leggi_dimensioni_etichetta,
)
from .generazione import genera_immagine_barcode, salva_barcode_png, valida_per_barcode
from .scanner import CampoScanner

__all__ = [
    "CampoScanner",
    "genera_etichetta_pdf",
    "genera_immagine_barcode",
    "genera_sheet_etichette_pdf",
    "leggi_dimensioni_etichetta",
    "salva_barcode_png",
    "valida_per_barcode",
]
