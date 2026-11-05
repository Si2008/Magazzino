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
from .fogli_colore import nome_foglio_colore

from .formato_v2 import (
    INTESTAZIONI_V2,
    ErroreRiga,
    RisultatoV2,
    itera_righe_v2,
    valida_righe_v2,
)

NOME_FOGLIO = "Inventario"
INTESTAZIONI_ODS = tuple(n for n in INTESTAZIONI_V2 if n != "Descrizione")
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
    righe = itera_righe_v2(session)
    doc = OpenDocumentSpreadsheet()
    fogli, occupati = {}, set()
    def aggiungi_riga(foglio, valori):
        tr = TableRow()
        for nome, testo in zip(INTESTAZIONI_ODS, valori):
            tr.addElement(_cella(testo, nome in _NUMERICHE))
        foglio.addElement(tr)
    def nuovo_foglio(codice):
        foglio = Table(name=nome_foglio_colore(codice, occupati))
        doc.spreadsheet.addElement(foglio)
        aggiungi_riga(foglio, INTESTAZIONI_ODS)
        return foglio
    for valori in righe:
        codice = valori[4]
        if codice not in fogli:
            fogli[codice] = nuovo_foglio(codice)
        aggiungi_riga(fogli[codice], valori[:3]+valori[4:])
    if not fogli:
        nuovo_foglio(NOME_FOGLIO)
    from ..file_sicuri import destinazione_atomica
    with destinazione_atomica(percorso) as temporaneo:
        doc.save(str(temporaneo))
    return percorso


def _testo_cella(c: TableCell) -> str:
    if c.getAttribute("valuetype") == "float":
        v = float(c.getAttribute("value"))
        return str(int(v)) if v.is_integer() else c.getAttribute("value")
    return teletype.extractText(c)


def leggi_righe_ods(percorso: Path) -> list[list[str]]:
    """Legge tutti i fogli colore V2, anche il vecchio foglio singolo Inventario."""
    doc = load(str(percorso))
    fogli = doc.spreadsheet.getElementsByType(Table)
    if not fogli:
        raise ValueError("Il documento ODS non contiene fogli")
    risultato = []
    for foglio in fogli:
        righe = _leggi_foglio(foglio)
        if not righe:
            raise ValueError(f"Foglio {foglio.getAttribute('name')}: intestazione mancante")
        if risultato and righe[0] != risultato[0]:
            raise ValueError(f"Foglio {foglio.getAttribute('name')}: intestazione diversa, nessuna importazione")
        risultato.extend(righe if not risultato else righe[1:])
    return risultato


def _leggi_foglio(foglio):
    n = len(INTESTAZIONI_V2)
    risultato: list[list[str]] = []
    senza_descrizione = False
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
        if not risultato:
            senza_descrizione = tuple(valori) == INTESTAZIONI_ODS
        if senza_descrizione:
            valori.insert(3, "Descrizione" if not risultato else "")
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
