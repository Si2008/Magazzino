"""Backup logico completo in XLSX (multi-foglio) e ripristino.

Non confondere con ``backup/backup_db.py`` (dump pg_dump del database).
Formato: sei fogli fissi, ID e FK conservati, timestamp in ISO 8601 UTC
(testo: Excel non supporta fusi orari e arrotonda i microsecondi).
I file PNG delle sezioni NON sono inclusi (solo il percorso ``immagine_sezione``).
La tabella ``utenti`` NON è inclusa (contiene hash di password).

Il foglio ``Pezzi`` include anche ``numero_vassoio``, ``stato``,
``data_ultimo_cambio_stato`` e ``eliminato_il`` (Fasi 7-8): il backup
preserva quindi vassoio, stato, timestamp e cancellazione logica.
"""

from __future__ import annotations

import enum
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, Mapping

from openpyxl import Workbook, load_workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font
from openpyxl.utils.exceptions import IllegalCharacterError
from sqlalchemy import Boolean, DateTime, Enum, Integer, Numeric, func, insert, select, text
from sqlalchemy.orm import Session

from ..domain import Colore, Movimento, Pezzo, Profilo, Spezzone, TipoMovimento
from ..domain import Commessa,RigaCommessa,AssegnazioneCommessa
from ..services.stati import STATI_BARCODE
INTESTAZIONI_REPORT_STORICO = ("Codice profilo", "Descrizione", "Colore", "Lunghezza (mm)",
                              "Quantità", "Ubicazione", "Barcode")

VERSIONE_FORMATO = 4
APPLICAZIONE = "Magazzino Profili"
MAX_CARATTERI_CELLA = 32767  # limite Excel: oltre, openpyxl tronca in silenzio
MAX_RIGHE = 1_048_575        # righe dati per foglio (1.048.576 meno l'intestazione)

# Foglio -> modello. L'ordine è quello dei fogli E dell'inserimento nel restore.
FOGLI: dict[str, type] = {
    "Commesse": Commessa,
    "Profili": Profilo, "Colori": Colore, "Pezzi": Pezzo,
    "Movimenti": Movimento, "Spezzoni": Spezzone,
    "RigheCommesse": RigaCommessa, "AssegnazioniCommesse": AssegnazioneCommessa,
}
FOGLI_STORICI = ("Profili","Colori","Pezzi","Movimenti","Spezzoni")
FOGLI_LEGGIBILI = ("Inventario", "Carico", "Scarico", "Avvisi")
NOMI_FOGLI = ("Metadati", *FOGLI, *FOGLI_LEGGIBILI)

# Contratto del formato: intestazioni ESPLICITE (nome colonna DB, nell'ordine).
# Se aggiungi una colonna a un modello devi aggiornare questa tupla E
# VERSIONE_FORMATO: lo impone test_intestazioni_coprono_lo_schema.
INTESTAZIONI: dict[str, tuple[str, ...]] = {
    "Commesse": ("id","identita","cognome","cognome_chiave","nome","creata_il"),
    "RigheCommesse": ("id","commessa_id","profilo","colore","lunghezza","quantita","riferimento","barra_intera"),
    "AssegnazioniCommesse": ("id","commessa_id","pezzo_id"),
    "Profili": ("id", "codice", "descrizione", "immagine_sezione",
                "peso_kg_per_metro", "lunghezza_standard_mm"),
    "Colori": ("id", "codice_normalizzato", "nome_visualizzato", "colore_hex"),
    "Pezzi": ("id", "profilo_id", "colore_id", "lunghezza_mm", "quantita",
              "ubicazione", "scorta_minima", "barcode",
              "numero_vassoio", "stato", "data_ultimo_cambio_stato",
              "eliminato_il", "unitario"),
    "Movimenti": ("id", "pezzo_id", "tipo", "quantita", "data_ora", "causale", "utente"),
    "Spezzoni": ("id", "pezzo_origine_id", "utente", "lunghezza_mm",
                 "data_creazione", "utilizzato"),
}
# Fase 8: colonne in CODO facoltative per i file vecchi (restano validi; colonna -> NULL).
COLONNE_FACOLTATIVE: dict[str, tuple[str, ...]] = {"Colori": ("colore_hex",), "Pezzi": ("unitario",)}
_HEX_VALIDO = re.compile(r"^#[0-9A-Fa-f]{6}$")

# (FK) foglio.colonna -> foglio referenziato
FK = {
    ("RigheCommesse","commessa_id"): "Commesse",
    ("AssegnazioniCommesse","commessa_id"): "Commesse",
    ("AssegnazioniCommesse","pezzo_id"): "Pezzi",
    ("Pezzi", "profilo_id"): "Profili", ("Pezzi", "colore_id"): "Colori",
    ("Movimenti", "pezzo_id"): "Pezzi", ("Spezzoni", "pezzo_origine_id"): "Pezzi",
}
UNIVOCHE = {
    "Commesse": (("identita",),), "AssegnazioniCommesse": (("pezzo_id",),),
    "Profili": (("codice",),), "Colori": (("codice_normalizzato",),),
    "Pezzi": (("barcode",), ("profilo_id", "colore_id", "lunghezza_mm")),
}
STATI_VALIDI: dict[str, frozenset[str]] = {   # colonna -> valori ammessi
    "tipo": frozenset(t.name for t in TipoMovimento),
    "stato": frozenset(STATI_BARCODE),         # "Caricato" / "Scaricato" (Fasi 7-8)
}


@dataclass(frozen=True)
class ErroreBackup:
    foglio: str
    riga: int | None
    colonna: str
    motivo: str

    def __str__(self) -> str:
        riga = f" riga {self.riga}" if self.riga else ""
        col = f" colonna '{self.colonna}'" if self.colonna else ""
        return f"[{self.foglio}{riga}{col}] {self.motivo}"


class BackupNonValidoError(Exception):
    """Backup illeggibile o incoerente. ``errori`` elenca foglio/riga/colonna."""

    def __init__(self, errori: tuple[ErroreBackup, ...], formato_storico: bool = False) -> None:
        self.errori = errori
        self.formato_storico = formato_storico
        mostrati = "\n".join(str(e) for e in errori[:20])
        extra = f"\n... e altri {len(errori) - 20}" if len(errori) > 20 else ""
        super().__init__(f"Backup non valido:\n{mostrati}{extra}")


class RipristinoRifiutatoError(Exception):
    """Il ripristino non è ammesso (DB non vuoto, collisioni, sessione già in transazione)."""


@dataclass(frozen=True)
class BackupValidato:
    versione: int
    esportato_il: datetime
    tabelle: Mapping[str, tuple[Mapping[str, Any], ...]]   # righe già tipizzate, per foglio
    soglia_scorta: int | None = None


# ------------------------------------------------------------------ conversioni
def _iso_utc(v: datetime) -> str:
    if v.tzinfo is None:          # SQLite restituisce datetime naive: sono UTC
        v = v.replace(tzinfo=timezone.utc)
    return v.astimezone(timezone.utc).isoformat()


def _in_cella(valore: Any, foglio: str, riga: int, colonna: str) -> Any:
    if valore is None:
        return None
    if isinstance(valore, datetime):
        return _iso_utc(valore)
    if isinstance(valore, Decimal):
        return float(valore)
    if isinstance(valore, enum.Enum):
        return valore.value                      # anche Enum 'str' (TipoMovimento)
    if isinstance(valore, str) and len(valore) > MAX_CARATTERI_CELLA:
        raise BackupNonValidoError((ErroreBackup(
            foglio, riga, colonna, f"testo di {len(valore)} caratteri: oltre il limite Excel"),))
    return valore


def _scrivi(ws, valori: list[Any]) -> None:
    celle = []
    for v in valori:
        c = WriteOnlyCell(ws, value=v)
        if isinstance(v, str):
            c.data_type = "s"        # niente formule da testo utente ('=1+1' resta testo)
        celle.append(c)
    ws.append(celle)


def esporta_backup_logico_excel(session: Session, percorso_output: str | Path) -> Path:
    from ..file_sicuri import destinazione_atomica
    from .snapshot import sessione_snapshot
    percorso = Path(percorso_output)
    with sessione_snapshot(session) as lettura, destinazione_atomica(percorso) as provvisorio:
        _esporta_backup_logico_excel(lettura, provvisorio)
    return percorso


def _esporta_backup_logico_excel(session: Session, percorso_output: str | Path) -> Path:
    """Crea il backup multi-foglio (scrittura atomica: ``.tmp`` + ``os.replace``)."""
    percorso = Path(percorso_output)
    percorso.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook(write_only=True)
    meta = wb.create_sheet("Metadati")
    fogli = {nome: wb.create_sheet(nome) for nome in FOGLI}
    conteggi: dict[str, int] = {}
    grassetto = Font(bold=True)

    def intestazione(ws, nomi):
        riga = []
        for n in nomi:
            c = WriteOnlyCell(ws, value=n)
            c.font = grassetto
            riga.append(c)
        ws.append(riga)

    temporaneo = percorso.with_name(percorso.name + ".tmp")
    try:
        for nome, modello in FOGLI.items():
            ws = fogli[nome]
            colonne = INTESTAZIONI[nome]
            intestazione(ws, colonne)
            n = 0
            for oggetto in session.scalars(select(modello).order_by(modello.id).execution_options(yield_per=500)):
                n += 1
                if n > MAX_RIGHE:
                    raise BackupNonValidoError((ErroreBackup(
                        nome, None, "", f"oltre {MAX_RIGHE} righe: limite di un foglio Excel"),))
                _scrivi(ws, [_in_cella(getattr(oggetto, c), nome, n + 1, c) for c in colonne])
            conteggi[nome] = n

        from ..services.impostazioni import leggi_soglia
        soglia = leggi_soglia(session)
        _scrivi_fogli_programma(session, wb, intestazione, soglia)

        intestazione(meta, ("chiave", "valore"))
        _scrivi(meta, ["versione_formato", VERSIONE_FORMATO])
        _scrivi(meta, ["esportato_il_utc", datetime.now(timezone.utc).isoformat()])
        _scrivi(meta, ["applicazione", APPLICAZIONE])
        _scrivi(meta, ["soglia_sotto_scorta", soglia])
        _scrivi(meta, ["fogli_per_ripristino", ", ".join(FOGLI)])
        _scrivi(meta, ["note", "Inventario, Carico, Scarico e Avvisi sono viste di consultazione; il ripristino usa i fogli tecnici."])
        for nome, n in conteggi.items():
            _scrivi(meta, [f"righe_{nome}", n])

        wb.save(temporaneo)
    except IllegalCharacterError as e:
        raise BackupNonValidoError((ErroreBackup(
            "", None, "", f"carattere di controllo non ammesso in Excel nei dati: {e}"),))
    except BaseException:
        temporaneo.unlink(missing_ok=True)    # mai un file .tmp a metà
        raise
    finally:
        _chiudi_fogli(wb)                     # chiude i generatori in sospeso: a GC non resta
    os.replace(temporaneo, percorso)          # mai un file a metà
    return percorso


def _scrivi_fogli_programma(session, wb, intestazione, soglia):
    """Viste leggibili come le schede; i fogli tecnici restano la fonte del restore."""
    from ..services import consultazione as c
    from sqlalchemy.orm import selectinload
    inventario = wb.create_sheet("Inventario")
    intestazione(inventario, ("Profilo", "Descrizione", "Colore", "Lunghezza mm", "Quantità",
        "Vassoio", "Ubicazione", "Barcode", "Stato", "Cambio stato UTC", "Pezzo singolo"))
    query = select(Pezzo).options(selectinload(Pezzo.profilo), selectinload(Pezzo.colore))
    for p in session.scalars(query.where(Pezzo.eliminato_il.is_(None)).order_by(Pezzo.id)
                             .execution_options(yield_per=500)):
        _scrivi(inventario, [p.profilo.codice, p.profilo.descrizione, p.colore.nome_visualizzato,
            p.lunghezza_mm, p.quantita, p.numero_vassoio, p.ubicazione, p.barcode, p.stato,
            _iso_utc(p.data_ultimo_cambio_stato) if p.data_ultimo_cambio_stato else None, p.unitario])
    for nome, tipi in (("Carico", (TipoMovimento.CARICO,)),
                       ("Scarico", (TipoMovimento.SCARICO, TipoMovimento.RETTIFICA))):
        ws = wb.create_sheet(nome)
        intestazione(ws, ("Data e ora UTC", "Profilo", "Colore", "Barcode", "Quantità", "Tipo", "Causale", "Operatore"))
        query = select(Movimento, Pezzo.barcode, Profilo.codice, Colore.nome_visualizzato).join(
            Pezzo, Movimento.pezzo_id == Pezzo.id).join(Profilo, Pezzo.profilo_id == Profilo.id).join(
            Colore, Pezzo.colore_id == Colore.id).where(Movimento.tipo.in_(tipi)).order_by(Movimento.id)
        for m, barcode, codice, colore in session.execute(query.execution_options(yield_per=500)):
            _scrivi(ws, [_iso_utc(m.data_ora), codice, colore, barcode, m.quantita, m.tipo.value, m.causale, m.utente])
    ws = wb.create_sheet("Avvisi")
    intestazione(ws, ("Profilo", "Colore", "Lunghezza mm", "Pezzi rimasti del materiale", "Scorta minima", "Livello"))
    gruppi, collegamento, _ = c._dati_scorta(soglia)
    riferimento = func.coalesce(gruppi.c.minima, soglia)
    from sqlalchemy import or_
    query = select(Pezzo, gruppi.c.totale, gruppi.c.minima).join(gruppi, collegamento).where(
        Pezzo.eliminato_il.is_(None), Pezzo.id == gruppi.c.rappresentante,
        or_(gruppi.c.totale <= 0, gruppi.c.totale <= riferimento * 3)).options(
        selectinload(Pezzo.profilo), selectinload(Pezzo.colore)).order_by(Pezzo.id)
    for p, totale, minima in session.execute(query.execution_options(yield_per=500)):
        p._quantita_scorta, p._scorta_gruppo = totale, minima
        _scrivi(ws, [p.profilo.codice, p.colore.nome_visualizzato, p.lunghezza_mm, totale,
                     minima, c.livello_scorta(p, soglia)])


def _chiudi_fogli(wb) -> None:
    """Chiude i fogli (e i generatori di righe in sospeso di openpyxl).

    Senza questo, dopo un'uscita per eccezione il garbage collector chiude
    i generatori su file già chiusi: ``ValueError: I/O operation on closed file``
    (segnalato da pytest come PytestUnraisableExceptionWarning).
    """
    for ws in wb.worksheets:
        try:
            ws.close()
        except Exception:                    # noqa: BLE001 - già chiuso (salvataggio ok)
            pass


# ------------------------------------------------------------------ validazione
def _leggi_cella(valore: Any, modello: type, colonna: str, foglio: str, riga: int,
                 errori: list[ErroreBackup]) -> Any:
    col = modello.__table__.c[colonna]
    tipo = col.type

    def err(motivo: str) -> None:
        errori.append(ErroreBackup(foglio, riga, colonna, motivo))

    if isinstance(valore, str) and valore == "":
        valore = None
    if valore is None:
        if not col.nullable and not col.primary_key and isinstance(tipo, (Integer, Numeric, DateTime, Boolean, Enum)):
            err("valore mancante")
        elif not col.nullable and not col.primary_key:
            return ""                             # testo NOT NULL: vuoto = stringa vuota
        elif col.primary_key:
            err("valore mancante")
        return None
    if isinstance(tipo, Boolean):
        if isinstance(valore, bool):
            return valore
        err(f"booleano atteso (trovato {valore!r})")
    elif isinstance(tipo, Integer):
        if isinstance(valore, bool):
            err("intero atteso")
        elif isinstance(valore, (int, float)) and float(valore).is_integer():
            return int(valore)
        else:
            err(f"intero atteso (trovato {valore!r})")
    elif isinstance(tipo, Numeric):
        try:
            if isinstance(valore, bool) or not isinstance(valore, (int, float, Decimal)):
                raise InvalidOperation
            numero = Decimal(str(valore))
            if not numero.is_finite():
                raise InvalidOperation
            return numero.quantize(Decimal(1).scaleb(-(tipo.scale or 0)))
        except InvalidOperation:
            err(f"numero atteso (trovato {valore!r})")
    elif isinstance(tipo, DateTime):
        try:
            d = datetime.fromisoformat(str(valore))
        except ValueError:
            err(f"data/ora ISO 8601 attesa (trovato {valore!r})")
            return None
        if d.tzinfo is None:
            err("manca il fuso orario (offset UTC)")
            return None
        return d.astimezone(timezone.utc)
    else:                                         # testo / Enum
        testo = valore if isinstance(valore, str) else str(valore)
        if getattr(tipo, "length", None) and len(testo) > tipo.length:
            err(f"massimo {tipo.length} caratteri")
        if modello is Profilo and colonna == "codice":
            from ..db.normalizzazione import normalizza_codice
            testo = normalizza_codice(testo)
        ammessi = STATI_VALIDI.get(colonna)
        if ammessi is not None and testo not in ammessi:
            err(f"valore non ammesso '{testo}'")
        return testo
    return None


def valida_backup_logico_excel(percorso_input: str | Path) -> BackupValidato:
    """Legge e valida TUTTO senza toccare il database."""
    percorso = Path(percorso_input)
    if not percorso.is_file():
        raise FileNotFoundError(f"File non trovato: {percorso}")
    try:
        wb = load_workbook(percorso, read_only=True, data_only=False)
    except Exception as e:  # noqa: BLE001 - zip corrotto, xml non valido, ecc.
        raise BackupNonValidoError((ErroreBackup("", None, "", f"file XLSX non apribile: {e}"),)) from e
    try:
        nomi = tuple(wb.sheetnames)
        from .export_excel import INTESTAZIONI as intestazioni_report
        if nomi and "Metadati" not in nomi and all(
                tuple(next(wb[n].iter_rows(values_only=True), ())) in
                (INTESTAZIONI_REPORT_STORICO, tuple(intestazioni_report)) for n in nomi):
            raise BackupNonValidoError((ErroreBackup(
                "Inventario", None, "",
                "report Inventario a foglio singolo o per colore: contiene solo le giacenze, "
                "senza ID, movimenti, spezzoni né relazioni. NON è un backup completo: "
                "ripristino solo parziale (re-inserimento delle giacenze con l'import CSV)."),),
                formato_storico=True)
        if nomi not in (NOMI_FOGLI, ("Metadati", *FOGLI), ("Metadati",*FOGLI_STORICI), ("Metadati",*FOGLI_STORICI,*FOGLI_LEGGIBILI)):
            raise BackupNonValidoError((ErroreBackup(
                "", None, "", f"fogli attesi {list(NOMI_FOGLI)}, trovati {list(nomi)}"),))
        righe_foglio = {n: list(wb[n].iter_rows(values_only=True)) for n in ("Metadati", *FOGLI) if n in wb.sheetnames}
    finally:
        wb.close()

    errori: list[ErroreBackup] = []
    meta: dict[str, Any] = {}
    r_meta = righe_foglio["Metadati"]
    if not r_meta or tuple(r_meta[0][:2]) != ("chiave", "valore"):
        errori.append(ErroreBackup("Metadati", 1, "", "intestazione attesa: chiave, valore"))
    for r in r_meta[1:]:
        if r and r[0] is not None:
            meta[str(r[0])] = r[1]
    if meta.get("versione_formato") not in (1, 2, 3, VERSIONE_FORMATO):
        errori.append(ErroreBackup("Metadati", None, "versione_formato",
                                   f"deve essere {VERSIONE_FORMATO} (trovato {meta.get('versione_formato')!r})"))
    try:
        esportato = datetime.fromisoformat(str(meta.get("esportato_il_utc")))
        if esportato.tzinfo is None:
            raise ValueError
        esportato = esportato.astimezone(timezone.utc)
    except ValueError:
        esportato = datetime.fromtimestamp(0, timezone.utc)
        errori.append(ErroreBackup("Metadati", None, "esportato_il_utc", "data/ora ISO 8601 con fuso attesa"))

    tabelle: dict[str, tuple[Mapping[str, Any], ...]] = {}
    for nome, modello in FOGLI.items():
        if nome not in righe_foglio:
            if meta.get('versione_formato') in (1,2,3):
                tabelle[nome]=();continue
            errori.append(ErroreBackup(nome,None,'','foglio commesse mancante nel formato 4'));continue
        righe = righe_foglio[nome]
        attese = INTESTAZIONI[nome]
        facoltative = COLONNE_FACOLTATIVE.get(nome, ())
        if nome == "Pezzi" and meta.get("versione_formato") in (2, 3, 4):
            facoltative = ()  # non perdere l'identità dei barcode unitari
        base = attese[:len(attese) - len(facoltative)] if facoltative else attese
        intestazione: tuple[str, ...] | None = None
        if righe:
            testa = righe[0]
            if (tuple(testa[:len(attese)]) == attese
                    and all(v in (None, "") for v in testa[len(attese):])):
                intestazione = attese
            elif (facoltative
                  and tuple(testa[:len(base)]) == base
                  and all(v in (None, "") for v in testa[len(base):])):
                intestazione = base            # file vecchio: colonne facoltative assenti
        if intestazione is None:
            errori.append(ErroreBackup(nome, 1, "",
                                       f"intestazioni attese {list(attese)} (o, per i file vecchi, {list(base)})"))
            continue
        convertite: list[Mapping[str, Any]] = []
        for numero, r in enumerate(righe[1:], start=2):
            if all(v in (None, "") for v in r):
                continue
            valori = list(r) + [None] * (len(intestazione) - len(r))
            riga_conv = {c: _leggi_cella(valori[i], modello, c, nome, numero, errori)
                         for i, c in enumerate(intestazione)}
            for c in attese[len(intestazione):]:      # colonne facoltative assenti -> NULL
                riga_conv[c] = False if c == "unitario" else None
            if (riga_conv.get("colore_hex") is not None
                    and not _HEX_VALIDO.match(riga_conv["colore_hex"])):
                errori.append(ErroreBackup(nome, numero, "colore_hex",
                                           f"valore non valido {riga_conv['colore_hex']!r} (atteso #RRGGBB)"))
            riga_conv["_riga"] = numero
            convertite.append(MappingProxyType(riga_conv))
        tabelle[nome] = tuple(convertite)
        atteso = meta.get(f"righe_{nome}")
        if atteso != len(convertite):
            errori.append(ErroreBackup(nome, None, "", f"{len(convertite)} righe ma Metadati dichiara {atteso!r}"))

    if len(tabelle) == len(FOGLI):
        _controlli_relazionali(tabelle, errori)
    if errori:
        raise BackupNonValidoError(tuple(errori))
    soglia = meta.get("soglia_sotto_scorta")
    if soglia is not None and (type(soglia) is not int or not 1 <= soglia <= 99):
        raise BackupNonValidoError((ErroreBackup("Metadati", None, "soglia_sotto_scorta", "intero da 1 a 99 atteso"),))
    return BackupValidato(VERSIONE_FORMATO, esportato, MappingProxyType(tabelle), soglia)


def _controlli_relazionali(tabelle, errori: list[ErroreBackup]) -> None:
    ids: dict[str, set] = {}
    for nome, righe in tabelle.items():
        visti: dict[Any, int] = {}
        for r in righe:
            if nome=='Commesse':
                from ..services.archivio_commesse import chiave_cognome
                try:
                    if chiave_cognome(r.get('cognome'))!=r.get('cognome_chiave') or not re.fullmatch('[0-9a-f]{64}',r.get('identita') or ''):
                        raise ValueError('Identità o cognome non coerente')
                except ValueError as e:errori.append(ErroreBackup(nome,r['_riga'],'',str(e)))
            if nome=='RigheCommesse':
                from ..services.commesse import RichiestaTaglio
                try:RichiestaTaglio(r.get('profilo'),r.get('colore'),r.get('lunghezza'),r.get('quantita'),r.get('riferimento'),r.get('barra_intera'))
                except (ValueError,TypeError) as e:errori.append(ErroreBackup(nome,r['_riga'],'',str(e)))
            if nome == "Profili" and (not r.get("codice") or not r.get("peso_kg_per_metro", 0) or
                                      r["peso_kg_per_metro"] <= 0 or r.get("lunghezza_standard_mm", 0) <= 0):
                errori.append(ErroreBackup(nome, r["_riga"], "", "codice, peso e lunghezza positivi obbligatori"))
            if r["id"] is None:
                continue
            if r["id"] in visti:
                errori.append(ErroreBackup(nome, r["_riga"], "id", f"duplicato (già alla riga {visti[r['id']]})"))
            visti[r["id"]] = r["_riga"]
        ids[nome] = set(visti)
        for colonne in UNIVOCHE.get(nome, ()):
            visti_u: dict[tuple, int] = {}
            for r in righe:
                if nome == "Pezzi" and len(colonne) > 1 and r.get("unitario"):
                    continue
                chiave = tuple(r[c] for c in colonne)
                if None in chiave:
                    continue
                if chiave in visti_u:
                    errori.append(ErroreBackup(nome, r["_riga"], "+".join(colonne),
                                               f"duplicato (già alla riga {visti_u[chiave]})"))
                visti_u[chiave] = r["_riga"]
    for (nome, colonna), padre in FK.items():
        for r in tabelle[nome]:
            if r[colonna] is not None and r[colonna] not in ids[padre]:
                errori.append(ErroreBackup(nome, r["_riga"], colonna,
                                           f"riferimento a {padre}.id={r[colonna]} inesistente"))
    for nome, modello in FOGLI.items():           # vincoli CHECK noti
        for r in tabelle[nome]:
            if nome == "Pezzi" and r.get("unitario") and r.get("quantita") not in (0, 1):
                errori.append(ErroreBackup(nome, r["_riga"], "quantita", "un barcode unitario ammette solo 0 oppure 1"))
            for colonna, minimo in (("quantita", 1 if nome == "Movimenti" else 0), ("lunghezza_mm", 1)):
                if colonna in r and r[colonna] is not None and r[colonna] < minimo:
                    errori.append(ErroreBackup(nome, r["_riga"], colonna, f"deve essere almeno {minimo}"))


# -------------------------------------------------------------------- restore
def _riallinea_sequenze(session: Session) -> None:
    if session.get_bind().dialect.name != "postgresql":
        return
    for modello in FOGLI.values():
        tab = modello.__tablename__
        session.execute(text(
            f"SELECT setval(pg_get_serial_sequence('{tab}', 'id'), "
            f"COALESCE((SELECT MAX(id) FROM {tab}), 1), (SELECT MAX(id) IS NOT NULL FROM {tab}))"))


def ripristina_backup_logico_excel(
    session: Session,
    backup: BackupValidato,
    *,
    modalita: Literal["db_vuoto", "merge"],
) -> None:
    """Ripristina un backup validato; un errore qualsiasi -> rollback completo."""
    if not isinstance(backup, BackupValidato):
        raise TypeError("serve un BackupValidato (usa valida_backup_logico_excel)")
    if modalita not in ("db_vuoto", "merge"):
        raise ValueError("modalita deve essere 'db_vuoto' o 'merge'")
    if session.in_transaction():
        raise RipristinoRifiutatoError(
            "la sessione ha già una transazione aperta: il ripristino ne richiede una propria")
    with session.begin():                          # un errore qualsiasi -> rollback completo
        if session.get_bind().dialect.name == "postgresql":
            for modello in FOGLI.values():
                session.execute(text(f"LOCK TABLE {modello.__tablename__} IN EXCLUSIVE MODE"))
        _verifica_destinazione(session, backup, modalita)
        for nome, modello in FOGLI.items():
            righe = [{k: v for k, v in r.items() if k != "_riga"} for r in backup.tabelle[nome]]
            if righe:
                session.execute(insert(modello.__table__), righe)
        _riallinea_sequenze(session)
        if backup.soglia_scorta is not None:
            from ..domain import Impostazione
            from ..services.impostazioni import CHIAVE_SOGLIA
            riga = session.get(Impostazione, CHIAVE_SOGLIA)
            if riga is None:
                session.add(Impostazione(chiave=CHIAVE_SOGLIA, valore=str(backup.soglia_scorta)))
            else:
                riga.valore = str(backup.soglia_scorta)


def _verifica_destinazione(session: Session, backup: BackupValidato, modalita: str) -> None:
    if modalita == "db_vuoto":
        pieni = [m.__tablename__ for m in FOGLI.values()
                 if session.scalar(select(func.count()).select_from(m)) > 0]
        if pieni:
            raise RipristinoRifiutatoError(f"database non vuoto (tabelle con dati: {pieni}); "
                                           "usa modalita='merge' solo per aggiungere record nuovi")
        return
    # merge: nessun aggiornamento, rifiuta ogni collisione (ID, univoci, FK verso il DB)
    problemi: list[str] = []
    id_backup = {n: {r["id"] for r in backup.tabelle[n]} for n in FOGLI}
    for nome, modello in FOGLI.items():
        esistenti = set(session.scalars(select(modello.id)))
        for i in sorted(id_backup[nome] & esistenti):
            problemi.append(f"{nome}: id {i} già presente")
        for colonne in UNIVOCHE.get(nome, ()):
            if len(colonne) == 1:
                col = getattr(modello, colonne[0])
                gia = set(session.scalars(select(col)))
            else:
                query = select(*[getattr(modello, c) for c in colonne])
                if nome == "Pezzi":
                    query = query.where(Pezzo.unitario.is_(False))
                gia = {tuple(r) for r in session.execute(query)}
            for r in backup.tabelle[nome]:
                if nome == "Pezzi" and len(colonne) > 1 and r.get("unitario"):
                    continue
                chiave = tuple(r[c] for c in colonne)
                if None in chiave:
                    continue
                if chiave in gia or (len(colonne) == 1 and r[colonne[0]] in gia):
                    problemi.append(f"{nome} riga {r['_riga']}: {'+'.join(colonne)} già presente nel database")
    for (nome, colonna), padre in FK.items():
        padre_db = set(session.scalars(select(FOGLI[padre].id)))
        for r in backup.tabelle[nome]:
            if r[colonna] is not None and r[colonna] not in id_backup[padre] and r[colonna] not in padre_db:
                problemi.append(f"{nome} riga {r['_riga']}: {colonna}={r[colonna]} senza padre")
    if problemi:
        raise RipristinoRifiutatoError("merge rifiutato, nessuna modifica:\n" + "\n".join(problemi[:20]))
