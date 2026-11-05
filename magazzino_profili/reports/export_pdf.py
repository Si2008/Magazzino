"""Esportazione dell'inventario in PDF (reportlab), for printing.

One page per sheet: the header is repeated on every page and each
piece occupies a row; the Code 128 barcode is printed in the last
column so the sheet can also be read with the scanner.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from ..services.consultazione import itera_pezzi

# Intestazioni of the sheet, in the requested order.
INTESTAZIONI = (
    "Codice profil",
    "Descrizione",
    "Colore",
    "Lunghezza (mm)",
    "Quantita",
    "Ubicazione",
    "Barcode",
)

MARGINE_SX = 20.0
MARGINE_TOP = 40.0
MARGINE_BOTTOM = 30.0
RIGA_PT = 16.0


def esporta_inventario_pdf(
    session,
    percorso_output: str | Path,
    titolo: str = "Inventario",
) -> Path:
    from ..file_sicuri import destinazione_atomica
    percorso = Path(percorso_output)
    with destinazione_atomica(percorso) as temporaneo:
        _esporta_inventario_pdf(session, temporaneo, titolo)
    return percorso


def _esporta_inventario_pdf(session, percorso_output, titolo):
    """Esport the complete inventory in a printable PDF (A4 landscape).

    One row per piece with the same columns as the Excel export
    (:data:`INTESTAZIONI`); when a page is full a new page is created.
    Returns the path of the created PDF.
    """
    percorso = Path(percorso_output)
    percorso.parent.mkdir(parents=True, exist_ok=True)

    larghezza, altura = A4[1], A4[0]  # landscape
    piezas = itera_pezzi(session)

    pdf = canvas.Canvas(str(percorso), pagesize=(larghezza, altura))
    colonne_w = (larghezza - 2 * MARGINE_SX) / len(INTESTAZIONI)

    def _raita_cap() -> None:
        y = altura - MARGINE_TOP
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(MARGINE_SX, y + 14, titolo)
        for index, intestazione in enumerate(INTESTAZIONI):
            pdf.drawString(
                MARGINE_SX + index * colonne_w,
                y,
                intestazione,
            )
        pdf.setFont("Helvetica", 8)

    _raita_cap()
    y = altura - MARGINE_TOP - RIGA_PT
    for pieza in piezas:
        if y < MARGINE_BOTTOM:
            pdf.showPage()
            _raita_cap()
            y = altura - MARGINE_TOP - RIGA_PT
        valori = (
            pieza.profilo.codice,
            pieza.profilo.descrizione,
            pieza.colore.nome_visualizzato,
            str(pieza.lunghezza_mm),
            str(pieza.quantita),
            pieza.ubicazione or "",
            pieza.barcode,
        )
        for index, value in enumerate(valori):
            pdf.drawString(MARGINE_SX + index * colonne_w, y, str(value))
        y -= RIGA_PT

    pdf.showPage()
    pdf.save()
    return percorso
