"""Esportazione e validazione ODS del formato V2 (libreria: odfpy).

Il file è un archivio ODS vero (``mimetype`` per primo, non compresso).
I numeri sono celle ``float``; i timestamp restano testo ISO 8601 per
round-trip esatto. Il lettore espande le celle ripetute
(``table:number-columns-repeated``) usate da LibreOffice.
"""

from __future__ import annotations

import os
from pathlib import Path

from odf import teletype
from odf.opendocument import OpenDocumentSpreadsheet, load
from odf.table import Table, TableCell, TableRow
from odf.text import P
from sqlalchemy.orm import Session

from .formato_v2 import (
    INTESTAZIONI_V2,
    ErroreRiga,
    RisultatoV2,
    righe_v2_da_db,
    valida_righe_v2,
)

NOME_FOGLIO = "Inventario"
_NUMERICHE = {"ID pezzo", "Lunghezza (mm)", "Quantita", "Scorta minima"}
# NB: "Numero vassoio" NON è numerico: nel modello è testo libero.


def _cella(testo: str, numerica: bool) -> TableCell:
    if numerica and testo.isdigit():
        c = TableCell(valuetype="float", value=int(testo))
        c.addElement(P(text=testo))
        return c
    if testo == "":
        return TableCell()
    c = TableCell(valuetype="string")
    p = P()
    teletype.addTextToElement(p, testo)  # preserva spazi multipli, tab, a capo
    c.addElement(p)
    return c


def esporta_inventario_ods_v2(session: Session, percorso_output: str | Path) -> Path:
    percorso = Path(percorso_output)
    percorso.parent.mkdir(parents=True, exist_ok=True)
    righe = righe_v2_da_db(session)
    doc = OpenDocumentSpreadsheet()
    foglio = Table(name=NOME_FOGLIO)
    doc.spreadsheet.addElement(foglio)
    for valori in [list(INTESTAZIONI_V2), *righe]:
        tr = TableRow()
        for nome, testo in zip(INTESTAZIONI_V2, valori):
            tr.addElement(_cella(testo, nome in _NUMERICHE))
        foglio.addElement(tr)
    temporaneo = percorso.with_name(percorso.name + ".tmp")
    doc.save(str(temporaneo))
    os.replace(temporaneo, percorso)
    return percorso


def _testo_cella(c: TableCell) -> str:
    if c.getAttribute("valuetype") == "float":
        v = float(c.getAttribute("value"))
        return str(int(v)) if v.is_integer() else c.getAttribute("value")
    return teletype.extractText(c)


def leggi_righe_ods(percorso: Path) -> list[list[str]]:
    """Righe testuali del foglio ``Inventario`` (o del primo), allineate a 14 colonne."""
    doc = load(str(percorso))
    fogli = doc.spreadsheet.getElementsByType(Table)
    foglio = next((f for f in fogli if f.getAttribute("name") == NOME_FOGLIO), fogli[0])
    n = len(INTESTAZIONI_V2)
    risultato: list[list[str]] = []
    for tr in foglio.getElementsByType(TableRow):
        valori: list[str] = []
        for c in tr.getElementsByType(TableCell):
            # Espande i ripetuti di LibreOffice, senza esplodere le righe
            # di riempimento (``number-columns-repeated="16384"``).
            ripeti = int(c.getAttribute("numbercolumnsrepeated") or 1)
            valori.extend([_testo_cella(c)] * min(ripeti, n + 1))
        while valori and valori[-1] == "":
            valori.pop()
        if not valori:
            continue  # riga vuota (anche quelle "ripetute" di LibreOffice)
        risultato.append(valori + [""] * (n - len(valori)))
    return risultato


def valida_ods_v2(percorso_input: str | Path) -> RisultatoV2:
    percorso = Path(percorso_input)
    if not percorso.is_file():
        raise FileNotFoundError(f"File ODS non trovato: {percorso}")
    try:
        righe = leggi_righe_ods(percorso)
    except Exception as e:  # noqa: BLE001 - zip corrotto, XML non valido, ecc.
        return RisultatoV2((), (ErroreRiga(0, "", f"file ODS non valido: {e}"),))
    return valida_righe_v2(righe)
