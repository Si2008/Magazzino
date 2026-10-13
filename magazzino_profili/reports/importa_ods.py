"""Importazione dell'inventario da un file ODS (LibreOffice Calc).

Il file deve contenere fogli dati con una riga di intestazione che
include almeno le colonne: ``Profilo``, ``Colore``, ``Vassoio``,
``Dimensione_mm``, ``Pezzi`` (opzionale: ``Da_Rivedere_Dato_Originale``,
``Nota``). I fogli senza intestazione (es. "Riepilogo") sono ignorati.

Per ogni riga valida (profilo + lunghezza + quantità non vuoti):
- se il Profilo non esiste viene creato con valori segnaposto
  (peso 1.0 kg/m, lunghezza standard 6000 mm: da correggere in
  anagrafica);
- se il Colore non esiste viene creato;
- se il Pezzo (profilo+colore+lunghezza) non esiste viene creato con
  giacenza 0 e barcode generato;
- la quantità viene applicata come Movimento di tipo CARICO con
  traccia contabile.

Le righe con lunghezza o quantità vuote/non positive sono saltate e
contate come "saltate".
"""

from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.normalizzazione import (
    genera_barcode,
    normalizza_codice,
    normalizza_colore,
)
from ..domain import (
    Colore,
    Pezzo,
    Profilo,
    TipoMovimento,
    registra_movimento,
)

NS = {
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
}

# Valori segnaposto per i profili creati automaticamente.
PESO_SEGNAPOSTO_KG_M = 1.0
LUNGHEZZA_STANDARD_MM = 6000
# Limite fisico della barra: 6,5 m.
LUNGHEZZA_MAX_MM = 6500


def _cell_text(cell: ET.Element) -> str:
    """Testo di una cella ODS (paragrafi uniti, altrimenti valore numerico)."""
    paragrafi = ["".join(p.itertext()) for p in cell.iter("{%s}p" % NS["text"])]
    testo = " ".join(s for s in paragrafi if s.strip())
    if testo.strip():
        return testo.strip()
    return cell.get("{%s}value" % NS["office"]) or ""


def _riga_valori(riga: ET.Element) -> list[str]:
    """Valori di una riga, espandendo i ripetuti di celle vuote."""
    valori: list[str] = []
    for cella in riga.findall("table:table-cell", NS):
        ripeti = int(cella.get("{%s}number-repeated" % NS["table"]) or 1)
        valori.extend([_cell_text(cella)] * ripeti)
    return valori


def _ubicazione_da_vassoio(valore: str) -> str | None:
    """Ubicazione dal valore della colonna Vassoio.

    Un numero (anche ``4.0`` da foglio di calcolo) diventa ``Vassoio 4``.
    Un testo diverso dal solo numero viene usato così com'è.
    """
    testo = (valore or "").strip()
    if not testo:
        return None
    corrispondenza = re.fullmatch(r"(\d+)(?:\.0+)?", testo)
    if corrispondenza:
        return f"Vassoio {int(corrispondenza.group(1))}"
    return testo


def _intero(testo: str) -> int | None:
    try:
        return int(float(testo.strip().replace(",", ".")))
    except (ValueError, AttributeError):
        return None


def leggi_foglio(tab: ET.Element) -> tuple[list[str], list[list[str]]]:
    """Ritorna (intestazione, righe dati) di un foglio ODS."""
    righe = tab.findall("table:table-row", NS)
    intestazione: list[str] | None = None
    indice_header = -1
    for i, r in enumerate(righe[:10]):
        vals = _riga_valori(r)
        if "Profilo" in vals:
            intestazione = vals
            indice_header = i
            break
    if intestazione is None:
        return [], []
    dati = []
    for r in righe[indice_header + 1 :]:
        vals = _riga_valori(r)
        if any(v.strip() for v in vals):
            dati.append(vals)
    return intestazione, dati


def importa_ods_file(
    sessione: Session, percorso: str | Path, utente: str = ""
) -> dict[str, int]:
    """Importa l'inventario da un file ODS; ritorna i contatori.

    Contatori: ``importate``, ``saltate``, ``da_rivedere``, ``errori``,
    ``profili_creati``, ``colori_creati``.
    """
    percorso = Path(percorso)
    if not percorso.is_file():
        raise FileNotFoundError(f"File ODS non trovato: {percorso}")

    statistiche = {
        "importate": 0,
        "saltate": 0,
        "da_rivedere": 0,
        "errori": 0,
        "profili_creati": 0,
        "colori_creati": 0,
    }

    with zipfile.ZipFile(percorso) as z:
        root = ET.fromstring(z.read("content.xml"))

    for tab in root.findall(".//table:table", NS):
        nome_foglio = tab.get("{%s}name" % NS["table"]) or ""
        if nome_foglio.lower() == "riepilogo":
            continue

        intestazione, dati = leggi_foglio(tab)
        if not intestazione:
            continue
        idx = {nome: i for i, nome in enumerate(intestazione) if nome}

        def campo(vals: list[str], nome: str) -> str:
            i = idx.get(nome)
            if i is None or i >= len(vals):
                return ""
            return vals[i].strip()

        for vals in dati:
            codice = campo(vals, "Profilo")
            colore_testo = campo(vals, "Colore")
            vassoio = campo(vals, "Vassoio")
            lunghezza = _intero(campo(vals, "Dimensione_mm"))
            quantita = _intero(campo(vals, "Pezzi"))
            flag_rivedere = campo(vals, "Da_Rivedere_Dato_Originale")
            nota = campo(vals, "Nota")

            if not codice or lunghezza is None or lunghezza <= 0:
                statistiche["saltate"] += 1
                continue
            if quantita is None or quantita <= 0:
                statistiche["saltate"] += 1
                continue
            if lunghezza > LUNGHEZZA_MAX_MM:
                statistiche["saltate"] += 1
                continue

            try:
                with sessione.begin():
                    # 1) Profilo: esiste o si crea (valori segnaposto).
                    codice_n = normalizza_codice(codice)
                    profilo = sessione.scalar(
                        select(Profilo).where(Profilo.codice == codice_n)
                    )
                    if profilo is None:
                        profilo = Profilo(
                            codice=codice_n,
                            descrizione=codice,
                            peso_kg_per_metro=PESO_SEGNAPOSTO_KG_M,
                            lunghezza_standard_mm=LUNGHEZZA_STANDARD_MM,
                        )
                        sessione.add(profilo)
                        statistiche["profili_creati"] += 1

                    # 2) Colore: esiste o si crea.
                    colore_n = normalizza_colore(colore_testo) or normalizza_colore(
                        nome_foglio
                    )
                    colore = sessione.scalar(
                        select(Colore).where(Colore.codice_normalizzato == colore_n)
                    )
                    if colore is None:
                        colore = Colore(
                            codice_normalizzato=colore_n,
                            nome_visualizzato=colore_testo or colore_n,
                        )
                        sessione.add(colore)
                        statistiche["colori_creati"] += 1

                    # 3) Pezzo: esiste o si crea (quantita 0 + barcode).
                    pezzo = sessione.scalar(
                        select(Pezzo).where(
                            Pezzo.profilo_id == profilo.id,
                            Pezzo.colore_id == colore.id,
                            Pezzo.lunghezza_mm == lunghezza,
                        )
                    )
                    if pezzo is None:
                        barcode = genera_barcode(profilo, colore, lunghezza)
                        pezzo = Pezzo(
                            profilo=profilo,
                            colore=colore,
                            lunghezza_mm=lunghezza,
                            quantita=0,
                            ubicazione=_ubicazione_da_vassoio(vassoio),
                            barcode=barcode,
                        )
                        sessione.add(pezzo)
                    elif _ubicazione_da_vassoio(vassoio) and not (pezzo.ubicazione or "").strip():
                        # Pezzo già esistente senza ubicazione: la riceve dal vassoio.
                        pezzo.ubicazione = _ubicazione_da_vassoio(vassoio)

                    # 4) CARICO con traccia contabile.
                    dettagli = []
                    if flag_rivedere:
                        dettagli.append(f"da rivedere: {flag_rivedere}")
                    if nota:
                        dettagli.append(f"nota: {nota}")
                    suffisso = f" ({'; '.join(dettagli)})" if dettagli else ""
                    if flag_rivedere or nota:
                        statistiche["da_rivedere"] += 1
                    registra_movimento(
                        sessione,
                        pezzo,
                        TipoMovimento.CARICO,
                        quantita,
                        causale=(
                            f"Importazione ODS (foglio {nome_foglio}){suffisso}"
                        ),
                        utente=utente,
                    )
                statistiche["importate"] += 1
            except Exception as errore:  # noqa: BLE001
                statistiche["errori"] += 1
                print(
                    f"  ERRORE foglio={nome_foglio} riga="
                    f"[{codice} | {colore_testo} | {vassoio} | {lunghezza} "
                    f"| {quantita}]: {errore}"
                )

    return statistiche
