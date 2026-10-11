"""Generazione dell'immagine barcode Code 128 da un valore.

Usa la libreria ``python-barcode`` con il writer di immagini (Pillow):
l'output è un PNG leggibile da qualsiasi stampante o lettore.

Questo modulo non tocca database né dominio: le funzioni sono pure
rispetto ai dati e quindi facilmente testabili.
"""

from __future__ import annotations

import re
from pathlib import Path

from barcode import Code128
from barcode.writer import ImageWriter

# Caratteri che possono comparire in un barcode generato da
# ``db.normalizzazione.genera_barcode``: maiuscole, cifre e trattino.
_CARATTERI_AMMESSI = re.compile(r"[A-Z0-9-]+")


def valida_per_barcode(valore: object) -> bool:
    """Restituisce ``True`` se ``valore`` è idoneo a un barcode.

    Sono ammessi solo maiuscole, cifre e trattino: la stessa classe di
    caratteri che può comparire nei codici prodotti da
    ``db.normalizzazione.genera_barcode``. I valori vuoti e quelli con
    minuscole, spazi o punteggiatura vengono rifiutati.
    """
    if not isinstance(valore, str):
        return False
    return bool(_CARATTERI_AMMESSI.fullmatch(valore))


def genera_immagine_barcode(valore: str, percorso_output: str | Path) -> str:
    """Genera un'immagine barcode Code 128 (PNG) e la salva su disco.

    :param valore: il valore del barcode (es. ``"AB12-AN007-6000"``).
    :param percorso_output: percorso completo del PNG da creare (la
        directory padre viene creata se assente).
    :return: il percorso (come ``str``) del file PNG creato.
    :raises ValueError: se il valore è vuoto o contiene caratteri non
        ammessi; in quel caso non viene creato alcun file.
    """
    if not valida_per_barcode(valore):
        raise ValueError(
            "Valore non ammesso per un barcode Code 128: sono consentite "
            "solo lettere maiuscole, cifre e trattino (es. 'AB12-AN007-6000')."
        )

    percorso = Path(percorso_output)
    percorso.parent.mkdir(parents=True, exist_ok=True)

    # Immagini "pure" (solo barre, senza testo umano leggibile): dove
    # serve il testo (etichette PDF) viene disegnato a parte come testo
    # vettoriale, più nitido e più facile da estrarre.
    ean = Code128(valore)
    ean.writer = ImageWriter()  # PNG a 300 dpi
    with open(percorso, "wb") as fp:
        ean.write(fp, options={"write_text": False})

    return str(percorso)


def salva_barcode_png(valore: str, percorso_output: str | Path) -> Path:
    """Compatibilità con l'API precedente: genera il PNG e restituisce
    il percorso come ``Path`` (anziché ``str``).

    .. note:: per il codice nuovo preferire :func:`genera_immagine_barcode`.
    """
    return Path(genera_immagine_barcode(valore, percorso_output))
