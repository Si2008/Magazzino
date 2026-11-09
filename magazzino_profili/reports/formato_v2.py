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
    "Scorta minima", "Barcode unitario",
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
    unitario: bool = False


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
        pezzo.colore.codice_normalizzato, str(pezzo.lunghezza_mm), str(pezzo.quantita),
        _testo(pezzo.ubicazione), _testo(getattr(pezzo, a["Numero vassoio"])), pezzo.barcode,
        _testo(getattr(pezzo, a["Stato barcode"])),
        _testo(getattr(pezzo, a["Data ultimo cambio stato UTC"])),
        _testo(getattr(pezzo, a["Eliminato il UTC"])),
        _testo(getattr(pezzo, a["Scorta minima"])),
        "1" if pezzo.unitario else "0",
    ]


def righe_v2_da_db(session: Session) -> list[list[str]]:
    """TUTTI i pezzi, eliminati compresi, per id (non usare ``lista_pezzi``)."""
    return list(itera_righe_v2(session))


def itera_righe_v2(session: Session):
    from ..services.consultazione import itera_pezzi
    for pezzo in itera_pezzi(session, includi_eliminati=True):
        yield riga_v2_da_pezzo(pezzo)


def esporta_inventario_csv_v2(session: Session, percorso_output: str | Path) -> Path:
    percorso = Path(percorso_output)
    percorso.parent.mkdir(parents=True, exist_ok=True)
    righe = itera_righe_v2(session)
    temporaneo = percorso.with_name(percorso.name + ".tmp")
    from ..file_sicuri import destinazione_atomica
    with destinazione_atomica(percorso) as temporaneo, open(temporaneo, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file, delimiter=";")
        writer.writerow(INTESTAZIONI_V2)
        writer.writerows(righe)
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


def colonna_peso(nome: str) -> bool:
    """Compatibilità degli scambi storici: la colonna viene ignorata, non validata."""
    return bool(re.match(r"^(?:peso|weight)(?:\b|_)", str(nome).strip(), re.IGNORECASE))


def valida_righe_v2(righe: Iterable[Sequence[str]]) -> RisultatoV2:
    """Valida righe testuali; la prima è l'intestazione. Nessun accesso al DB."""
    it = iter(righe)
    intestazione = next(it, None)
    if intestazione is None:
        return RisultatoV2((), (ErroreRiga(1, "", "file vuoto"),))
    larghezza_originale = len(intestazione)
    indici = [n for n, nome in enumerate(intestazione) if not colonna_peso(nome)]
    ignora_peso = len(indici) != larghezza_originale
    if ignora_peso:
        intestazione = [intestazione[n] for n in indici]
    if tuple(intestazione) == (*INTESTAZIONI_V2[:-1], ""):
        intestazione = intestazione[:-1]  # ODS storico con cella finale vuota
    if tuple(intestazione) not in (INTESTAZIONI_V2, INTESTAZIONI_V2[:-1]):
        return RisultatoV2((), (ErroreRiga(
            1, "", "intestazioni diverse dal formato V2 (testo e ordine esatti)"),))

    valide: list[RigaV2] = []
    errori: list[ErroreRiga] = []
    id_visti: dict[int, int] = {}
    barcode_visti: dict[str, int] = {}

    for numero, campi in enumerate(it, start=2):
        if ignora_peso:
            if len(campi) != larghezza_originale:
                errori.append(ErroreRiga(numero, "", f"attese {larghezza_originale} colonne, trovate {len(campi)}"))
                continue
            campi = [campi[n] for n in indici]
        if not any(c.strip() for c in campi):
            continue
        if len(intestazione) == len(INTESTAZIONI_V2) - 1 and len(campi) == len(INTESTAZIONI_V2) and not campi[-1]:
            campi = campi[:-1]
        if len(campi) != len(intestazione):
            errori.append(ErroreRiga(
                numero, "", f"attese {len(intestazione)} colonne, trovate {len(campi)}"))
            continue
        prima = len(errori)

        def err(colonna: str, motivo: str, _n: int = numero) -> None:
            errori.append(ErroreRiga(_n, colonna, motivo))

        c = dict(zip(INTESTAZIONI_V2, campi))
        unitario = c.get("Barcode unitario", "0").strip() or "0"
        if unitario not in ("0", "1"):
            err("Barcode unitario", "valori ammessi 0 oppure 1")
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
        if unitario == "1" and quantita not in (0, 1):
            err("Quantita", "il barcode unitario ammette solo 0 oppure 1")
        # ``numero_vassoio`` è testo libero nel modello: testo non vuoto, niente check numerico.
        vassoio = c["Numero vassoio"].strip() or None
        scorta = _intero(c["Scorta minima"], "Scorta minima", err, 0, False)
        barcode = c["Barcode"].strip().upper()
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
        for nome, massimo in (("Codice profilo", 64), ("Colore", 64), ("Numero vassoio", 128),
                               ("Ubicazione", 128), ("Barcode", 255)):
            if len(c[nome].strip()) > massimo:
                err(nome, f"massimo {massimo} caratteri")

        if len(errori) == prima:
            valide.append(RigaV2(
                numero, id_pezzo, codice, c["Descrizione"], colore, lunghezza, quantita,
                c["Ubicazione"].strip() or None, vassoio, barcode, stato, cambiato,
                eliminato, scorta, unitario == "1"))
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


def importa_inventario_v2(session: Session, risultato: RisultatoV2, utente: str = "") -> int:
    """Applica una fotografia V2 in una sola transazione, conservando ID e storico.

    Le quantità sono riconciliate con movimenti di differenza; ID/barcode e
    combinazioni in conflitto vengono rifiutati, mai fusi silenziosamente.
    """
    from sqlalchemy import or_, text
    from ..domain import Colore, Movimento, TipoMovimento, registra_movimento
    from ..services.carico import _colore_o_crea
    if not risultato.valido:
        raise ValueError("File V2 non valido:\n" + "\n".join(map(str, risultato.errori)))
    with session.begin():
        if session.get_bind().dialect.name == "postgresql":
            session.execute(text("LOCK TABLE profili, colori, pezzi, movimenti IN EXCLUSIVE MODE"))
        profili = {p.codice: p for p in session.scalars(select(Profilo))}
        for riga in risultato.righe:
            codice = normalizza_codice(riga.codice_profilo)
            if codice not in profili:
                raise ValueError(f"Riga {riga.riga}: profilo {codice} non in anagrafica")
            profilo = profili[codice]
            colore = _colore_o_crea(session, normalizza_colore(riga.colore))
            candidati = session.scalars(select(Pezzo).where(or_(
                Pezzo.id == riga.id_pezzo, Pezzo.barcode == riga.barcode,
                (Pezzo.profilo_id == profilo.id) & (Pezzo.colore_id == colore.id) &
                (Pezzo.lunghezza_mm == riga.lunghezza_mm) & Pezzo.unitario.is_(False) &
                (not riga.unitario))).with_for_update()).all()
            if len(candidati) > 1:
                raise ValueError(f"Riga {riga.riga}: conflitto fra ID, barcode e combinazione")
            if candidati:
                pezzo = candidati[0]
                if pezzo.id != riga.id_pezzo or (pezzo.profilo_id, pezzo.colore_id, pezzo.lunghezza_mm) != (
                        profilo.id, colore.id, riga.lunghezza_mm):
                    raise ValueError(f"Riga {riga.riga}: identità del pezzo differente")
                if pezzo.unitario != riga.unitario:
                    raise ValueError(f"Riga {riga.riga}: impossibile cambiare un barcode aggregato in unitario con l'import")
            else:
                pezzo = Pezzo(id=riga.id_pezzo, profilo_id=profilo.id, colore_id=colore.id,
                              lunghezza_mm=riga.lunghezza_mm, barcode=riga.barcode, quantita=0,
                              unitario=riga.unitario)
                session.add(pezzo)
                session.flush()
            delta = riga.quantita - pezzo.quantita
            if delta:
                registra_movimento(session, pezzo, TipoMovimento.CARICO if delta > 0 else TipoMovimento.SCARICO,
                                    abs(delta), "Riconciliazione inventario V2", utente)
            pezzo.barcode = riga.barcode
            pezzo.numero_vassoio = riga.numero_vassoio
            pezzo.ubicazione = riga.ubicazione
            pezzo.scorta_minima = riga.scorta_minima
            pezzo.stato = riga.stato_barcode
            pezzo.data_ultimo_cambio_stato = riga.stato_cambiato_il
            pezzo.eliminato_il = riga.eliminato_il
        session.flush()
        if session.get_bind().dialect.name == "postgresql":
            session.execute(text("SELECT setval(pg_get_serial_sequence('pezzi','id'), "
                                 "COALESCE((SELECT MAX(id) FROM pezzi),1), (SELECT MAX(id) IS NOT NULL FROM pezzi))"))
    return len(risultato.righe)
