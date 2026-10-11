"""Esport and import of the inventory in CSV.

The CSV has the same columns as the Excel export (:data:`INTESTAZIONI`):
it is the format to exchange the inventory with external software.
The import reads the CSV row by row and calls the service
``carica``, so the business rules (normalization, automatic creation of
colour and piece, Movement) remain in the domain.
"""

from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy.orm import Session

from ..services.carico import carica
from ..services.consultazione import lista_pezzi
from ..domain import Profilo
from ..services.eccezioni import ProfiloNonTrovatoError

INTESTAZIONI = (
    "Codice profil",
    "Descrizione",
    "Colore",
    "Lunghezza (mm)",
    "Quantita",
    "Ubicazione",
    "Barcode",
)


def esporta_inventario_csv(session: Session, percorso_output: str | Path) -> Path:
    """Esport the complete inventory in a CSV file (UTF-8, header).

    One row per piece, with the same columns as the Excel export.
    Returns the path of the created file.
    """
    percorso = Path(percorso_output)
    percorso.parent.mkdir(parents=True, exist_ok=True)

    with open(percorso, "w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, delimiter=";")
        writer.writerow(INTESTAZIONI)
        for pieza in lista_pezzi(session):
            writer.writerow(
                (
                    pieza.profilo.codice,
                    pieza.profilo.descrizione,
                    pieza.colore.nome_visualizzato,
                    pieza.lunghezza_mm,
                    pieza.quantita,
                    pieza.ubicazione or "",
                    pieza.barcode,
                )
            )
    return percorso


def importa_peczi_csv(
    session: Session,
    percorso_input: str | Path,
    utente: str = "",
    causale: str = "Importazione csv",
) -> int:
    """Import a CSV inventory: every row is a ``carica``.

    The header must contain :data:`INTESTAZIONI` (the order of the
    columns is not important). Every row calls :func:`carica` with the
    profile code, the colour, the length and the quantity: the rules of
    the business remain in the service, so a row with an unknown profile
    raises :class:`ProfiloNonTrovatoError` and nothing is saved.

    Returns the number of imported rows.
    """
    percorso = Path(percorso_input)
    if not percorso.is_file():
        raise FileNotFoundError(f"Csv not found: {percorso}")

    with open(percorso, encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file, delimiter=";")
        if reader.fieldnames is None:
            raise ValueError("Csv header vuoto")
        header = {nome.strip(): nome for nome in reader.fieldnames}
        for intestazione in ("Codice profil", "Colore", "Lunghezza (mm)", "Quantita"):
            if intestazione not in header:
                raise ValueError(f"Csv header without {intestazione}")

        imported = 0
        for row in reader:
            codice = (row.get(header["Codice profil"]) or "").strip()
            colore = (row.get(header["Colore"]) or "").strip()
            if not codice or not colore:
                continue
            carica(
                session,
                codice,
                colore,
                int(row[header["Lunghezza (mm)"]]),
                int(row[header["Quantita"]]),
                utente,
                causale,
            )
            imported += 1

    return imported
