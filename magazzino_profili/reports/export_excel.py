"""Esportazione dell'inventario completo in Excel (openpyxl)."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.cell import WriteOnlyCell
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session

from ..services.consultazione import itera_pezzi
from ..file_sicuri import destinazione_atomica
from .fogli_colore import nome_foglio_colore

# Intestazioni del foglio, nell'ordine richiesto.
INTESTAZIONI = (
    "Codice profilo",
    "Colore",
    "Lunghezza (mm)",
    "Quantità",
    "Ubicazione",
    "Barcode",
)


def esporta_inventario_excel(session: Session, percorso_output: str | Path) -> Path:
    """Esporta l'inventario completo in un file ``.xlsx``.

    Una riga per pezzo: codice profilo, descrizione, colore, lunghezza,
    quantità, ubicazione e barcode. Un foglio per codice colore.
    """
    percorso = Path(percorso_output)
    percorso.parent.mkdir(parents=True, exist_ok=True)

    pezzi = itera_pezzi(session)

    foglio = Workbook(write_only=True)
    fogli, occupati = {}, set()

    def nuovo_foglio(codice):
        ws = foglio.create_sheet(nome_foglio_colore(codice, occupati))
        ws.freeze_panes = "A2"
        for indice, larghezza in enumerate((22, 44, 26, 22, 16, 30, 50), 1):
            ws.column_dimensions[get_column_letter(indice)].width = larghezza
        header = []
        for nome in INTESTAZIONI:
            cella = WriteOnlyCell(ws, nome)
            cella.font = Font(bold=True)
            header.append(cella)
        ws.append(header)
        return ws

    for pezzo in pezzi:
        codice = pezzo.colore.codice_normalizzato
        if codice not in fogli:
            fogli[codice] = nuovo_foglio(codice)
        ws = fogli[codice]
        valori = [
            pezzo.profilo.codice,
            pezzo.colore.nome_visualizzato,
            pezzo.lunghezza_mm,
            pezzo.quantita,
            pezzo.ubicazione or "",
            pezzo.barcode,
        ]
        celle = []
        for valore in valori:
            cella = WriteOnlyCell(ws, valore)
            if isinstance(cella.value, str):
                cella.data_type = "s"
            celle.append(cella)
        ws.append(celle)

    if not fogli:
        nuovo_foglio("Inventario")
    with destinazione_atomica(percorso) as temporaneo:
        foglio.save(temporaneo)
    return percorso
