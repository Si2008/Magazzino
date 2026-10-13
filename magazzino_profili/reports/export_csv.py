"""Esportazione e importazione dell'inventario in CSV.

Il CSV ha le stesse colonne dell'export Excel (:data:`INTESTAZIONI`):
è il formato per scambiare l'inventario con altri programmi.

L'import legge e valida TUTTE le righe prima di scrivere qualsiasi
dato: se una riga è non valida o un profilo non esiste in anagrafica,
nulla viene importato. Ogni riga valida viene poi caricata con il
servizio ``carica``, quindi le regole di business restano nel dominio.
"""

from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.normalizzazione import normalizza_codice
from ..domain import Profilo
from ..services.carico import carica
from ..services.consultazione import lista_pezzi
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
    """Esporta l'inventario completo in un file CSV (UTF-8, ``;``, intestazione).

    Una riga per pezzo, con le stesse colonne dell'export Excel.
    Restituisce il percorso del file creato.
    """
    percorso = Path(percorso_output)
    percorso.parent.mkdir(parents=True, exist_ok=True)

    with open(percorso, "w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, delimiter=";")
        writer.writerow(INTESTAZIONI)
        for pezzo in lista_pezzi(session):
            writer.writerow(
                (
                    pezzo.profilo.codice,
                    pezzo.profilo.descrizione,
                    pezzo.colore.nome_visualizzato,
                    pezzo.lunghezza_mm,
                    pezzo.quantita,
                    pezzo.ubicazione or "",
                    pezzo.barcode,
                )
            )
    return percorso


def _leggi_righe(percorso: Path) -> list[tuple[int, str, str, int, int, str | None]]:
    """Legge e valida il CSV. Solleva ``ValueError`` indicando la riga errata."""
    with open(percorso, encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file, delimiter=";")
        if reader.fieldnames is None:
            raise ValueError("Intestazione del CSV vuota")
        header = {nome.strip(): nome for nome in reader.fieldnames}
        for obbligatoria in ("Codice profil", "Colore", "Lunghezza (mm)", "Quantita"):
            if obbligatoria not in header:
                raise ValueError(f"Intestazione CSV mancante: '{obbligatoria}'")

        righe = []
        for numero_riga, riga in enumerate(reader, start=2):
            codice = (riga.get(header["Codice profil"]) or "").strip()
            colore = (riga.get(header["Colore"]) or "").strip()
            if not codice or not colore:
                continue
            lunghezza_testo = (riga.get(header["Lunghezza (mm)"]) or "").strip()
            quantita_testo = (riga.get(header["Quantita"]) or "").strip()
            try:
                lunghezza = int(lunghezza_testo)
                quantita = int(quantita_testo)
            except ValueError as errore:
                raise ValueError(
                    f"Errore alla riga {numero_riga} del CSV: lunghezza e quantità "
                    f"devono essere numeri interi (trovato '{lunghezza_testo}' / "
                    f"'{quantita_testo}')."
                ) from errore
            if lunghezza <= 0 or quantita <= 0:
                raise ValueError(
                    f"Errore alla riga {numero_riga} del CSV: lunghezza e quantità "
                    "devono essere maggiori di zero."
                )
            ubicazione = None
            if "Ubicazione" in header:
                ubicazione = (riga.get(header["Ubicazione"]) or "").strip() or None
            righe.append((numero_riga, codice, colore, lunghezza, quantita, ubicazione))
    return righe


def importa_peczi_csv(
    session: Session,
    percorso_input: str | Path,
    utente: str = "",
    causale: str = "Importazione csv",
) -> int:
    """Importa un inventario CSV: ogni riga è un ``carica``.

    Prima della scrittura si verificano tutte le righe: formato dei numeri,
    valori positivi, e presenza di ogni profilo in anagrafica. Se una
    verifica fallisce, nulla viene importato e l'errore indica la riga.

    Restituisce il numero di righe importate.
    """
    percorso = Path(percorso_input)
    if not percorso.is_file():
        raise FileNotFoundError(f"File CSV non trovato: {percorso}")

    righe = _leggi_righe(percorso)

    # Lettura su una sessione separata: la sessione del chiamante non viene
    # toccata e ``carica`` può aprire le sue transazioni.
    with Session(bind=session.get_bind()) as lettura:
        codici_noti = set(lettura.scalars(select(Profilo.codice)))
    mancanti = sorted({normalizza_codice(r[1]) for r in righe} - codici_noti)
    if mancanti:
        raise ProfiloNonTrovatoError(", ".join(mancanti))

    importate = 0
    for numero_riga, codice, colore, lunghezza, quantita, ubicazione in righe:
        try:
            carica(session, codice, colore, lunghezza, quantita, utente, causale, ubicazione)
        except Exception as errore:
            # Errore imprevisto del database: le righe precedenti restano salvate.
            raise RuntimeError(
                f"Importazione interrotta alla riga {numero_riga} del CSV: {errore}. "
                f"Le prime {importate} righe risultano già salvate."
            ) from errore
        importate += 1
    return importate
