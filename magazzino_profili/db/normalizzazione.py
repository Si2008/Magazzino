"""Funzioni pure di normalizzazione di codici e colori, e generazione
del barcode dei pezzi.

Le funzioni di questo modulo non toccano database né stato: sono
pure, deterministiche e quindi facilmente testabili.
"""

from __future__ import annotations

import re

_SPACI = re.compile(r"\s+")


def _normalizza(testo: str) -> str:
    """Logica comune: strip, maiuscole, niente spazi interni,
    '/' e '\\' sostituiti con '-'."""
    if not isinstance(testo, str):
        raise TypeError(f"Aspettato un testo, ricevuto {type(testo).__name__}")
    testo = testo.strip().upper()
    testo = _SPACI.sub("", testo)
    testo = testo.replace("/", "-").replace("\\", "-")
    return testo


def normalizza_codice(testo: str) -> str:
    """Normalizza un codice profilo.

    Regole: rimozione spazi agli estremi, conversione in maiuscolo,
    eliminazione degli spazi interni, ``/`` e ``\\`` diventano ``-``.

    Esempio: ``" ab/12  x "`` -> ``"AB-12X"``.
    """
    return _normalizza(testo)


def normalizza_colore(testo: str) -> str:
    """Normalizza un codice colore con la medesima logica di
    :func:`normalizza_codice`."""
    return _normalizza(testo)


def genera_barcode(profilo: object, colore: object, lunghezza_mm: int) -> str:
    """Costruisce il barcode di un pezzo.

    Formato: ``CODICE_NORMALIZZATO-COLORE_NORMALIZZATO-lunghezza_mm``.

    ``profilo`` deve avere un attributo ``codice``; ``colore`` deve
    avere un attributo ``codice_normalizzato`` (come le entità
    ``Profilo`` e ``Colore`` del dominio).
    """
    if not isinstance(lunghezza_mm, int) or isinstance(lunghezza_mm, bool):
        raise TypeError("lunghezza_mm deve essere un intero")
    if lunghezza_mm <= 0:
        raise ValueError("La lunghezza deve essere strettamente positiva")
    codice = normalizza_codice(getattr(profilo, "codice", ""))
    colore_n = normalizza_colore(getattr(colore, "codice_normalizzato", ""))
    if not codice or not colore_n:
        raise ValueError("Profilo e colore devono avere un codice non vuoto")
    return f"{codice}-{colore_n}-{lunghezza_mm}"
