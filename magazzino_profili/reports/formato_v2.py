"""Formato V2 dell'inventario: esportazione CSV e validazione (solo lettura).

Nessuna scrittura sul database: il restore/merge NON è implementato qui.
Le righe testuali (``valida_righe_v2``) sono condivise con l'ODS.

Adattamenti ai campi reali del modello (Fasi 7-8):
- ``numero_vassoio`` è TESTO libero (String(128), es. "4", "Vassoio 4"),
  non un intero: la validazione accetta testo non vuoto;
- ``stato`` è ``stato`` (String(16)) e i valori ammessi sono quelli del
  vincolo ``stato_valido``: ``Caricato`` / ``Scaricato`` (vedi
  ``services/stati.py``: ``STATI_BARCODE``);
- ``data_ultimo_cambio_stato`` (DateTime timezone, UTC).
"""

from __future__ import annotations

import csv
import enum
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db.normalizzazione import normalizza_codice, normalizza_colore
from ..domain import Pezzo, Profilo

VERSIONE_FORMATO = "2"

INTESTAZIONI_V2 = (
    "Versione formato", "ID pezzo", "Codice profilo", "Descrizione", "Colore",
    "Lunghezza (mm)", "Quantita", "Ubicazione", "Numero vassoio", "Barcode",
    "Stato barcode", "Data ultimo cambio stato UTC", "Eliminato il UTC",
    "Scorta minima",
)

# Intestazione V2 -> attributo REALE di Pezzo (nominativo confermato nel modello).
ATTRIBUTI_PEZZO = {
    "Numero vassoio": "numero_vassoio",
    "Stato barcode": "stato",
    "Data ultimo cambio stato UTC": "data_ultimo_cambio_stato",
    "Eliminato il UTC": "eliminato_il",
    "Scorta minima": "scorta_minima",
}

# Valori ammessi per "Stato barcode": quelli del vincolo ``stato_valido``
# (``services/stati.py``: ``STATI_BARCODE = frozenset({"Caricato", "Scaricato"})``).
STATI_VALIDI: frozenset[str] = frozenset({"Caricato", "Scaricato"})

_INTERO = re.compile(r"[0-9]+")


@dataclass(frozen=True)
class ErroreRiga:
    riga: int  # numero di riga nel file (intestazione = 1)
    colonna: str
    motivo: str

    def __str__(self) -> str:
        dove = f" [{self.colonna}]" if self.colonna else ""
        return f"riga {self.riga}{dove}: {self.motivo}"


@dataclass(frozen=True)
class RigaV2:
    riga: int
    id_pezzo: int
    codice_profilo: str
    descrizione: str
    colore: str
    lunghezza_mm: int
    quantita: int
    ubicazione: str | None
    numero_vassoio: str | None
    barcode: str
    stato_barcode: str | None
    stato_cambiato_il: datetime | None
    eliminato_il: datetime | None
    scorta_minima: int | None


@dataclass(frozen=True)
class RisultatoV2:
    righe: tuple[RigaV2, ...]
    errori: tuple[ErroreRiga, ...]

    @property
    def valido(self) -> bool:
        return not self.errori


# --------------------------------------------------------------- esportazione
def _iso_utc(valore: datetime | None) -> str:
    if valore is None:
        return ""
    if valore.tzinfo is None:  # SQLite restituisce datetime naive: sono UTC
        valore = valore.replace(tzinfo=timezone.utc)
    return valore.astimezone(timezone.utc).isoformat()


def _testo(valore: object) -> str:
    if valore is None:
        return ""
    if isinstance(valore, enum.Enum):
        valore = valore.value
    if isinstance(valore, datetime):
        return _iso_utc(valore)
    return str(valore)


def riga_v2_da_pezzo(pezzo: Pezzo) -> list[str]:
    """Una riga V2 come lista di testi (stessi valori per CSV e ODS)."""
    a = ATTRIBUTI_PEZZO
    return [
        VERSIONE_FORMATO, str(pezzo.id), pezzo.profilo.codice, pezzo.profilo.descrizione,
        pezzo.colore.nome_visualizzato, str(pezzo.lunghezza_mm), str(pezzo.quantita),
        _testo(pezzo.ubicazione), _testo(getattr(pezzo, a["Numero vassoio"])), pezzo.barcode,
        _testo(getattr(pezzo, a["Stato barcode"])),
        _testo(getattr(pezzo, a["Data ultimo cambio stato UTC"])),
        _testo(getattr(pezzo, a["Eliminato il UTC"])),
        _testo(getattr(pezzo, a["Scorta minima"])),
    ]


def righe_v2_da_db(session: Session) -> list[list[str]]:
    """TUTTI i pezzi, eliminati compresi, per id (non usare ``lista_pezzi``)."""
    pezzi = session.scalars(
        select(Pezzo)
        .options(selectinload(Pezzo.profilo), selectinload(Pezzo.colore))
        .order_by(Pezzo.id)
    ).all()
    return [riga_v2_da_pezzo(p) for p in pezzi]


def esporta_inventario_csv_v2(session: Session, percorso_output: str | Path) -> Path:
    percorso = Path(percorso_output)
    percorso.parent.mkdir(parents=True, exist_ok=True)
    righe = righe_v2_da_db(session)  # prima di toccare il disco
    temporaneo = percorso.with_name(percorso.name + ".tmp")
    with open(temporaneo, "w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, delimiter=";")
        writer.writerow(INTESTAZIONI_V2)
        writer.writerows(righe)
    os.replace(temporaneo, percorso)  # mai un file a metà
    return percorso


# ----------------------------------------------------------------- validazione
def _intero(testo: str, colonna: str, err: Callable[[str, str], None],
            minimo: int, obbligatorio: bool) -> int | None:
    t = testo.strip()
    if not t:
        if obbligatorio:
            err(colonna, "valore mancante")
        return None
    if not _INTERO.fullmatch(t):
        err(colonna, f"non è un intero (trovato '{t}')")
        return None
    valore = int(t)
    if valore < minimo:
        err(colonna, f"deve essere almeno {minimo}")
        return None
    return valore


def _data(testo: str, colonna: str, err: Callable[[str, str], None]) -> datetime | None:
    t = testo.strip()
    if not t:
        return None
    try:
        d = datetime.fromisoformat(t)
    except ValueError:
        err(colonna, f"data/ora non ISO 8601 (trovato '{t}')")
        return None
    if d.tzinfo is None:
        err(colonna, "manca il fuso orario (offset, es. +00:00)")
        return None
    return d.astimezone(timezone.utc)


def valida_righe_v2(righe: Iterable[Sequence[str]]) -> RisultatoV2:
    """Valida righe testuali; la prima è l'intestazione. Nessun accesso al DB."""
    it = iter(righe)
    intestazione = next(it, None)
    if intestazione is None:
        return RisultatoV2((), (ErroreRiga(1, "", "file vuoto"),))
    if tuple(intestazione) != INTESTAZIONI_V2:
        return RisultatoV2((), (ErroreRiga(
            1, "", "intestazioni diverse dal formato V2 (testo e ordine esatti)"),))

    valide: list[RigaV2] = []
    errori: list[ErroreRiga] = []
    id_visti: dict[int, int] = {}
    barcode_visti: dict[str, int] = {}

    for numero, campi in enumerate(it, start=2):
        if not any(c.strip() for c in campi):
            continue
        if len(campi) != len(INTESTAZIONI_V2):
            errori.append(ErroreRiga(
                numero, "", f"attese {len(INTESTAZIONI_V2)} colonne, trovate {len(campi)}"))
            continue
        prima = len(errori)

        def err(colonna: str, motivo: str, _n: int = numero) -> None:
            errori.append(ErroreRiga(_n, colonna, motivo))

        c = dict(zip(INTESTAZIONI_V2, campi))
        if c["Versione formato"].strip() != VERSIONE_FORMATO:
            err("Versione formato", f"deve essere {VERSIONE_FORMATO}")
        id_pezzo = _intero(c["ID pezzo"], "ID pezzo", err, 1, True)
        if id_pezzo is not None:
            if id_pezzo in id_visti:
                err("ID pezzo", f"duplicato (già alla riga {id_visti[id_pezzo]})")
            else:
                id_visti[id_pezzo] = numero
        codice = c["Codice profilo"].strip()
        if not codice or not normalizza_codice(codice):
            err("Codice profilo", "valore mancante")
        colore = c["Colore"].strip()
        if not colore or not normalizza_colore(colore):
            err("Colore", "valore mancante")
        lunghezza = _intero(c["Lunghezza (mm)"], "Lunghezza (mm)", err, 1, True)
        quantita = _intero(c["Quantita"], "Quantita", err, 0, True)
        # ``numero_vassoio`` è testo libero nel modello: testo non vuoto, niente check numerico.
        vassoio = c["Numero vassoio"].strip() or None
        scorta = _intero(c["Scorta minima"], "Scorta minima", err, 0, False)
        barcode = c["Barcode"].strip()
        if not barcode:
            err("Barcode", "valore mancante")
        elif barcode in barcode_visti:
            err("Barcode", f"duplicato (già alla riga {barcode_visti[barcode]})")
        else:
            barcode_visti[barcode] = numero
        stato = c["Stato barcode"].strip() or None
        if stato is not None and stato not in STATI_VALIDI:
            err("Stato barcode", f"stato non valido '{stato}'")
        cambiato = _data(c["Data ultimo cambio stato UTC"], "Data ultimo cambio stato UTC", err)
        eliminato = _data(c["Eliminato il UTC"], "Eliminato il UTC", err)

        if len(errori) == prima:
            valide.append(RigaV2(
                numero, id_pezzo, codice, c["Descrizione"], colore, lunghezza, quantita,
                c["Ubicazione"].strip() or None, vassoio, barcode, stato, cambiato,
                eliminato, scorta))
    return RisultatoV2(tuple(valide), tuple(errori))


def valida_csv_v2(percorso_input: str | Path) -> RisultatoV2:
    """Legge TUTTO il file senza scrivere nulla. Errori di file -> RisultatoV2."""
    percorso = Path(percorso_input)
    if not percorso.is_file():
        raise FileNotFoundError(f"File CSV non trovato: {percorso}")
    try:
        with open(percorso, encoding="utf-8-sig", newline="") as file:
            return valida_righe_v2(list(csv.reader(file, delimiter=";", strict=True)))
    except UnicodeDecodeError as e:
        return RisultatoV2((), (ErroreRiga(0, "", f"codifica non UTF-8 (byte {e.start})"),))
    except csv.Error as e:
        return RisultatoV2((), (ErroreRiga(0, "", f"CSV malformato: {e}"),))


def verifica_riferimenti_v2(session: Session, risultato: RisultatoV2) -> tuple[ErroreRiga, ...]:
    """Il profilo di ogni riga deve esistere in anagrafica (come per ``carica``)."""
    with Session(bind=session.get_bind()) as lettura:
        profili = set(lettura.scalars(select(Profilo.codice)))
    return tuple(
        ErroreRiga(r.riga, "Codice profilo", f"profilo '{r.codice_profilo}' non in anagrafica")
        for r in risultato.righe
        if normalizza_codice(r.codice_profilo) not in profili
    )
