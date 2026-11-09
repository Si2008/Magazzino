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

import logging
import re
import shutil
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
from ..services.anagrafica import _destinazione_senza_conflitti, _stesso_file
from ..services.catalogo_immagini import CatalogoImmagini, png_valido

logger = logging.getLogger(__name__)

# Un solo catalogo per modulo: la creazione è economica e non apre file.
_catalogo_instance: CatalogoImmagini | None = None


def _catalogo() -> CatalogoImmagini:
    global _catalogo_instance
    if _catalogo_instance is None:
        _catalogo_instance = CatalogoImmagini()
    return _catalogo_instance


def _immagine_da_catalogo(codice: str) -> str | None:
    """Copia (o riusa) il PNG del catalogo per ``codice``; ``None`` se non c'è.

    Nessuna eccezione esce da qui: un catalogo assente, un file illeggibile o un
    conflitto di percorso non devono mai bloccare l'importazione.
    """
    try:
        catalogo = _catalogo()
        origine = catalogo.trova(codice)
        if origine is None:
            return None
        from PIL import Image
        with Image.open(origine) as immagine:
            if immagine.format != "PNG":
                raise ValueError("L'immagine del catalogo deve essere PNG")
            immagine.verify()
        cartella = catalogo.cartella
        cartella.mkdir(parents=True, exist_ok=True)
        # Senza profilo_id: il profilo è nuovo e senza immagine, non c'è conflitto.
        destinazione = _destinazione_senza_conflitti(origine, cartella, 0)
        if not _stesso_file(origine, destinazione):
            shutil.copy2(origine, destinazione)
        return str(destinazione.resolve())
    except Exception as errore:  # noqa: BLE001 — l'immagine è opzionale
        logger.warning("Immagine catalogo non associata al codice %s: %s", codice, errore)
        return None

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
    """Testo di una cella ODS (valore numerico esatto, altrimenti paragrafi uniti)."""
    tipo = cell.get("{%s}value-type" % NS["office"])
    if tipo in ("float", "percentage", "currency"):
        valore = cell.get("{%s}value" % NS["office"])
        if valore not in (None, ""):
            return valore  # il testo mostrato può essere formattato ('1.234,00')
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
        valori.extend([_cell_text(cella)] * min(ripeti, 64 - len(valori)))
        if len(valori) >= 64:
            break
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
    """Intero esatto o None: '3.0' e '3,0' valgono 3, '3.7' NON è un intero."""
    try:
        valore = float(testo.strip().replace(",", "."))
    except (ValueError, AttributeError):
        return None
    return int(valore) if valore.is_integer() else None


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


def leggi_importazione_ods(percorso: str | Path):
    """Prevalida tutti i fogli senza scrivere; errori con foglio/riga."""
    percorso = Path(percorso)
    if not percorso.is_file():
        raise FileNotFoundError(f"File ODS non trovato: {percorso}")
    with zipfile.ZipFile(percorso) as archivio:
        info = archivio.getinfo("content.xml")
        if info.file_size > 64 * 1024 * 1024:
            raise ValueError("ODS troppo grande: content.xml supera 64 MB")
        root = ET.fromstring(archivio.read(info))
    righe, errori = [], []
    for tab in root.findall(".//table:table", NS):
        nome = tab.get("{%s}name" % NS["table"]) or ""
        if nome.lower() == "riepilogo":
            continue
        header, dati = leggi_foglio(tab)
        if not header:
            continue
        mancanti = {"Profilo", "Dimensione_mm", "Pezzi"} - set(header)
        if mancanti:
            errori.append(f"{nome}: colonne mancanti: {', '.join(sorted(mancanti))}")
            continue
        indici = {h: i for i, h in enumerate(header)}
        for numero, vals in enumerate(dati, 2):
            def campo(chiave):
                i = indici.get(chiave)
                return vals[i].strip() if i is not None and i < len(vals) else ""
            codice = normalizza_codice(campo("Profilo"))
            colore = normalizza_colore(campo("Colore") or nome)
            lunghezza, quantita = _intero(campo("Dimensione_mm")), _intero(campo("Pezzi"))
            if not codice or not colore or lunghezza is None or not 1 <= lunghezza <= LUNGHEZZA_MAX_MM or quantita is None or quantita <= 0:
                errori.append(f"{nome}, riga dati {numero}: profilo, colore, lunghezza 1..6500 e quantità positiva obbligatori")
                continue
            righe.append((nome, numero, codice, colore, lunghezza, quantita,
                          campo("Vassoio"), campo("Da_Rivedere_Dato_Originale"), campo("Nota")))
    if not righe and not errori:
        raise ValueError("Nessun foglio dati ODS riconosciuto")
    return righe, errori


def importa_ods_file(sessione: Session, percorso: str | Path, utente: str = "", *, rigoroso: bool = True,
                     unitari: bool = False, vassoio_predefinito: str | None = None) -> dict[str, int]:
    """Import additivo esplicito, transazionale; default: rifiuta tutti gli errori.

    Il reimport rappresenta un altro carico: non è una fotografia sostitutiva.
    ``rigoroso=False`` richiede una scelta esplicita per saltare righe invalide.
    """
    from ..services.carico import _carica_in_transazione
    righe, errori = leggi_importazione_ods(percorso)
    if errori and rigoroso:
        raise ValueError("ODS non valido, nessuna riga importata:\n" + "\n".join(errori[:50]))
    if unitari:
        viste = set()
        for riga in righe:
            chiave = riga[2:7]
            if chiave in viste:
                raise ValueError(f"ODS, {riga[0]} riga {riga[1]}: riga duplicata; nessun pezzo importato")
            viste.add(chiave)
    statistiche = dict(importate=0, saltate=len(errori), da_rivedere=0,
                      errori=len(errori), profili_creati=0, colori_creati=0)
    with sessione.begin():
        profili = {p.codice: p for p in sessione.scalars(select(Profilo))}
        if unitari:
            sconosciuti = sorted({riga[2] for riga in righe} - profili.keys())
            if sconosciuti:
                raise ValueError(
                    "Profili non presenti: " + ", ".join(sconosciuti) +
                    ". Creare prima le anagrafiche con lunghezza standard in Inventario → Gestisci profili; "
                    "il file storico non contiene questi dati. Nessun pezzo importato."
                )
        colori = set(sessione.scalars(select(Colore.codice_normalizzato)))
        for nome, numero, codice, colore, lunghezza, quantita, vassoio, flag, nota in righe:
            if codice not in profili:
                profilo = Profilo(codice=codice, descrizione=codice,
                                 peso_kg_per_metro=PESO_SEGNAPOSTO_KG_M,
                                 lunghezza_standard_mm=LUNGHEZZA_STANDARD_MM,
                                 immagine_sezione=_immagine_da_catalogo(codice))
                sessione.add(profilo)
                sessione.flush()
                profili[codice] = profilo
                statistiche["profili_creati"] += 1
            causale = f"Importazione ODS (foglio {nome}, riga dati {numero})"
            if flag or nota:
                causale += f" — da rivedere: {flag}; nota: {nota}"
                statistiche["da_rivedere"] += 1
            if unitari:
                from ..services.pezzi_unitari import _crea_in_transazione
                rimanenti = quantita
                while rimanenti:
                    lotto = min(rimanenti, 1000)
                    _crea_in_transazione(sessione, codice, colore, lunghezza, lotto, utente, causale,
                        _ubicazione_da_vassoio(vassoio), vassoio or vassoio_predefinito)
                    rimanenti -= lotto
                pezzo = None
            else:
                pezzo = _carica_in_transazione(sessione, codice, colore, lunghezza,
                        quantita, utente, causale, _ubicazione_da_vassoio(vassoio))
            if vassoio and pezzo is not None:
                if pezzo.numero_vassoio and pezzo.numero_vassoio != vassoio:
                    raise ValueError(f"{nome}, riga dati {numero}: stessa combinazione in vassoi differenti; nessun dato importato")
                pezzo.numero_vassoio = vassoio
            if colore not in colori:
                colori.add(colore)
                statistiche["colori_creati"] += 1
            statistiche["importate"] += 1
    return statistiche
