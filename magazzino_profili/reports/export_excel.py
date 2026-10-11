"""Esportazione dell'inventario completo in Excel (openpyxl)."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session

from ..services.consultazione import lista_pezzi

# Intestazioni del foglio, nell'ordine richiesto.
INTESTAZIONI = (
    "Codice profilo",
    "Descrizione",
    "Colore",
    "Lunghezza (mm)",
    "Quantità",
    "Ubicazione",
    "Barcode",
)


def esporta_inventario_excel(session: Session, percorso_output: str | Path) -> Path:
    """Esporta l'inventario completo in un file ``.xlsx``.

    Una riga per pezzo: codice profilo, descrizione, colore, lunghezza,
    quantità, ubicazione e barcode. Il foglio si intitola ``Inventario``.
    """
    percorso = Path(percorso_output)
    percorso.parent.mkdir(parents=True, exist_ok=True)

    pezzi = lista_pezzi(session)

    foglio = Workbook()
    ws = foglio.active
    ws.title = "Inventario"

    ws.append(list(INTESTAZIONI))
    for cella in ws[1]:
        cella.font = Font(bold=True)

    for pezzo in pezzi:
        ws.append([
            pezzo.profilo.codice,
            pezzo.profilo.descrizione,
            pezzo.colore.nome_visualizzato,
            pezzo.lunghezza_mm,
            pezzo.quantita,
            pezzo.ubicazione or "",
            pezzo.barcode,
        ])

    # Larghezza colonne automatica (basata sul contenuto massimo).
    for indice, intestazione in enumerate(INTESTAZIONI, start=1):
        colonna = get_column_letter(indice)
        lunghezza_max = max(
            [len(str(intestazione))]
            + [len(str(ws.cell(row=r, column=indice).value or "")) for r in range(2, ws.max_row + 1)]
        )
        ws.column_dimensions[colonna].width = min(60, lunghezza_max + 2)

    foglio.save(percorso)
    return percorso
