"""Etichette PDF per i pezzi, generate con reportlab.

Le dimensioni dell'etichetta sono configurabili in ``config.toml``
(sezione ``[etichette]``), così l'etichetta si adatta a qualsiasi
stampante di etichette.

Il barcode viene generato "al volo" come immagine PNG
(:mod:`barcode.generazione`) in un file temporaneo che viene eliminato
appena salvato il PDF: non restano file intermedi permanenti.
"""

from __future__ import annotations

import os
import tempfile
import tomllib
from pathlib import Path

from PIL import Image
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from ..domain import Pezzo
from .generazione import genera_immagine_barcode

# config.toml alla radice del progetto.
PERCORSO_CONFIG_PREDEFINITO = Path(__file__).resolve().parents[2] / "config.toml"

# Dimensioni di fallback se config.toml è assente o non le specifica.
LARGHEZZA_MM_PREDEFINITA = 60.0
ALTEZZA_MM_PREDEFINITA = 30.0


def leggi_dimensioni_etichetta(
    percorso_config: str | Path | None = None,
) -> tuple[float, float]:
    """Legge da ``config.toml`` le dimensioni dell'etichetta in mm.

    Restituisce ``(larghezza_mm, altezza_mm)``; se il file o la sezione
    non sono presenti usa i valori predefiniti (60 x 30 mm).
    """
    larghezza = LARGHEZZA_MM_PREDEFINITA
    altezza = ALTEZZA_MM_PREDEFINITA
    percorso = Path(percorso_config) if percorso_config else PERCORSO_CONFIG_PREDEFINITO
    if percorso.is_file():
        with open(percorso, "rb") as file:
            dati = tomllib.load(file)
        sezione = dati.get("etichette", {})
        larghezza = float(sezione.get("larghezza_mm", larghezza))
        altezza = float(sezione.get("altura_mm", altezza))
    return larghezza, altezza


def _disegna_etichetta(
    pdf: canvas.Canvas,
    pezzo: Pezzo,
    larghezza_pt: float,
    altezza_pt: float,
) -> None:
    """Disegna il contenuto dell'etichetta sulla pagina corrente.

    Nell'ordine: codice profilo, descrizione, colore, lunghezza (mm),
    il valore del barcode come testo e infine l'immagine Code 128
    generata al volo (file temporaneo, eliminato alla fine).
    """
    margine = 3 * mm
    x = margine
    y = altezza_pt - margine

    # --- Testo: profilo, colore, lunghezza -------------------------------
    pdf.setFont("Helvetica", 11)
    pdf.drawString(
        x,
        y,
        f"Profilo: {pezzo.profilo.codice}  {pezzo.profilo.descrizione}",
    )
    y -= 5 * mm
    pdf.setFont("Helvetica", 9)
    pdf.drawString(x, y, f"Colore: {pezzo.colore.nome_visualizzato}")
    y -= 4.5 * mm
    pdf.drawString(x, y, f"Lunghezza: {pezzo.lunghezza_mm} mm")
    y -= 4.5 * mm

    # Il valore del barcode come testo PDF (estratto, stampato, leggibile
    # anche senza decodificare l'immagine).
    pdf.setFont("Courier", 8)
    pdf.drawString(x, y, pezzo.barcode)
    y -= 2.5 * mm

    # --- Immagine Code 128 (PNG generato al volo) ------------------------
    altezza_disponibile = max(2 * mm, y - margine)
    larghezza_disponibile = larghezza_pt - 2 * margine

    # File temporaneo per l'immagine intermedia: viene sempre eliminato,
    # anche in caso di errore durante la generazione del PDF.
    descrittore, nome_temp = tempfile.mkstemp(suffix=".png")
    os.close(descrittore)
    try:
        genera_immagine_barcode(pezzo.barcode, nome_temp)
        with Image.open(nome_temp) as immagine:
            larghezza_px, altezza_px = immagine.size
        # Scala proporzionale: le barre restano scansionabili.
        scala = min(larghezza_disponibile / larghezza_px, altezza_disponibile / altezza_px)
        pdf.drawImage(
            nome_temp,
            x,
            margine,
            width=larghezza_px * scala,
            height=altezza_px * scala,
            preserveAspectRatio=True,
            anchor="c",
        )
    finally:
        Path(nome_temp).unlink(missing_ok=True)


def genera_etichetta_pdf(
    pezzo: Pezzo,
    percorso_output: str | Path,
    larghezza_mm: float | None = None,
    altezza_mm: float | None = None,
) -> str:
    """Genera l'etichetta PDF del pezzo indicato, su una sola pagina.

    Contenuto: codice profilo, descrizione, colore, lunghezza e
    immagine Code 128 del campo ``barcode``. Se le dimensioni non sono
    indicate, sono lette da ``config.toml``.

    :return: il percorso (come ``str``) del PDF creato.
    :raises ValueError: se il barcode del pezzo è vuoto o le dimensioni
        non sono strettamente positive.
    """
    if not getattr(pezzo, "barcode", ""):
        raise ValueError("Il pezzo non ha un barcode: impossibile generare l'etichetta")

    if larghezza_mm is None or altezza_mm is None:
        larghezza_cfg, altezza_cfg = leggi_dimensioni_etichetta()
        larghezza_mm = larghezza_mm if larghezza_mm is not None else larghezza_cfg
        altezza_mm = altezza_mm if altezza_mm is not None else altezza_cfg

    if larghezza_mm <= 0 or altezza_mm <= 0:
        raise ValueError("Le dimensioni dell'etichetta devono essere strettamente positive")

    percorso = Path(percorso_output)
    percorso.parent.mkdir(parents=True, exist_ok=True)

    larghezza = larghezza_mm * mm
    altezza = altezza_mm * mm

    pdf = canvas.Canvas(str(percorso), pagesize=(larghezza, altezza))
    _disegna_etichetta(pdf, pezzo, larghezza, altezza)
    pdf.showPage()
    pdf.save()

    return str(percorso)


def genera_sheet_etichette_pdf(
    pezzi: list[Pezzo],
    percorso_output: str | Path,
    larghezza_mm: float | None = None,
    altezza_mm: float | None = None,
) -> Path:
    """Stampa più etichette: una pagina per pezzo in un unico PDF.

    Ogni pagina ha le dimensioni dell'etichetta (da argomenti o da
    ``config.toml``) e contiene i dati e il barcode Code 128 del pezzo.
    Solleva :class:`ValueError` se la lista dei pezzi è vuota.
    """
    if not pezzi:
        raise ValueError("Nessun pezzo da etichettare")

    if larghezza_mm is None or altezza_mm is None:
        larghezza_cfg, altezza_cfg = leggi_dimensioni_etichetta()
        larghezza_mm = larghezza_mm if larghezza_mm is not None else larghezza_cfg
        altezza_mm = altezza_mm if altezza_mm is not None else altezza_cfg

    if larghezza_mm <= 0 or altezza_mm <= 0:
        raise ValueError("Le dimensioni dell'etichetta devono essere strettamente positive")

    percorso = Path(percorso_output)
    percorso.parent.mkdir(parents=True, exist_ok=True)

    larghezza = larghezza_mm * mm
    altezza = altezza_mm * mm

    pdf = canvas.Canvas(str(percorso), pagesize=(larghezza, altezza))
    for pezzo in pezzi:
        _disegna_etichetta(pdf, pezzo, larghezza, altezza)
        pdf.showPage()
    pdf.save()

    return percorso
