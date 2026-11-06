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
import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.normalizzazione import normalizza_codice
from ..domain import Profilo
from ..services.carico import _carica_in_transazione, carica
from ..services.consultazione import itera_pezzi
from ..services.eccezioni import ProfiloNonTrovatoError
from ..file_sicuri import destinazione_atomica

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

    with destinazione_atomica(percorso) as temporaneo, open(temporaneo, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file, delimiter=";")
        writer.writerow(INTESTAZIONI)
        for pezzo in itera_pezzi(session):
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


_OBBLIGATORIE = ("Codice profil", "Colore", "Lunghezza (mm)", "Quantita")
_INTERO = re.compile(r"[0-9]+")  # solo cifre ASCII: niente '1_000', '+5', cifre unicode


def _leggi_righe(percorso: Path) -> list[tuple[int, str, str, int, int, str | None]]:
    """Legge e valida il CSV legacy. Solleva ``ValueError`` con TUTTI gli errori.

    - letto con ``utf-8-sig``: accetta file con e senza BOM (Excel lo aggiunge);
    - riga completamente vuota: ignorata;
    - riga con dati ma senza codice o senza colore: ERRORE (non più scartata);
    - lunghezza e quantità: interi > 0.
    """
    with open(percorso, encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file, delimiter=";")
        if reader.fieldnames is None:
            raise ValueError("Intestazione del CSV vuota")
        header = {nome.strip(): nome for nome in reader.fieldnames}
        for obbligatoria in _OBBLIGATORIE:
            if obbligatoria not in header:
                raise ValueError(f"Intestazione CSV mancante: '{obbligatoria}'")

        righe: list[tuple[int, str, str, int, int, str | None]] = []
        errori: list[str] = []

        def valore(riga: dict, nome: str) -> str:
            return (riga.get(header[nome]) or "").strip()

        for numero_riga, riga in enumerate(reader, start=2):
            if not any((v or "").strip() for v in riga.values() if isinstance(v, str)):
                continue  # riga vuota (anche ';;;;;;;')
            codice, colore = valore(riga, "Codice profil"), valore(riga, "Colore")
            lung_t, qta_t = valore(riga, "Lunghezza (mm)"), valore(riga, "Quantita")
            problemi = []
            if not codice:
                problemi.append("codice profilo mancante")
            if not colore:
                problemi.append("colore mancante")
            for nome, testo in (("lunghezza", lung_t), ("quantità", qta_t)):
                if not _INTERO.fullmatch(testo):
                    problemi.append(f"{nome} non è un intero (trovato '{testo}')")
                elif int(testo) < (0 if nome == "quantità" else 1):
                    problemi.append(f"{nome} non valido")
            if problemi:
                errori.append(f"riga {numero_riga}: " + "; ".join(problemi))
                continue
            ubicazione = None
            if "Ubicazione" in header:
                ubicazione = valore(riga, "Ubicazione") or None
            righe.append((numero_riga, codice, colore, int(lung_t), int(qta_t), ubicazione))
    if errori:
        elenco = "\n".join(errori[:50]) + (f"\n... e altri {len(errori) - 50}" if len(errori) > 50 else "")
        raise ValueError(f"CSV non valido, nulla è stato importato:\n{elenco}")
    return righe


def importa_peczi_csv(
    session: Session,
    percorso_input: str | Path,
    utente: str = "",
    causale: str = "Importazione csv",
    *, unitari: bool = False, vassoio_predefinito: str | None = None,
) -> int:
    """Importa un inventario CSV legacy: ogni riga è un ``carica`` (CARICO).

    Tutto o niente: validazione completa prima della scrittura, poi UNA
    transazione. Se un carico fallisce nessuna riga viene salvata.
    Il barcode del file è ignorato (viene rigenerato). Righe con la stessa
    combinazione si sommano: è la semantica del carico.

    Restituisce il numero di righe importate.
    """
    percorso = Path(percorso_input)
    if not percorso.is_file():
        raise FileNotFoundError(f"File CSV non trovato: {percorso}")

    righe = _leggi_righe(percorso)
    if unitari:
        visti = set()
        for numero, *dati in righe:
            chiave = tuple(str(v).strip().upper() for v in dati)
            if chiave in visti:
                raise ValueError(f"CSV, riga {numero}: riga duplicata; nessun pezzo importato")
            visti.add(chiave)

    # Lettura su una sessione separata: la sessione del chiamante non deve
    # avere una transazione già aperta, perché sotto si usa session.begin().
    with Session(bind=session.get_bind()) as lettura:
        codici_noti = set(lettura.scalars(select(Profilo.codice)))
    mancanti = sorted({normalizza_codice(r[1]) for r in righe} - codici_noti)
    if mancanti:
        raise ProfiloNonTrovatoError(", ".join(mancanti))

    riga_corrente = 0
    try:
        with session.begin():
            for riga_corrente, codice, colore, lunghezza, quantita, ubicazione in righe:
                if quantita == 0:
                    # Un export con giacenza zero non è un nuovo carico.
                    continue
                if unitari:
                    from ..services.pezzi_unitari import _crea_in_transazione
                    rimanenti = quantita
                    while rimanenti:
                        lotto = min(rimanenti, 1000)
                        _crea_in_transazione(session, codice, colore, lunghezza, lotto, utente,
                                             causale, ubicazione, vassoio_predefinito)
                        rimanenti -= lotto
                else:
                    _carica_in_transazione(
                        session, codice, colore, lunghezza, quantita, utente, causale, ubicazione
                    )
    except Exception as errore:
        raise RuntimeError(
            f"Importazione annullata alla riga {riga_corrente} del CSV: {errore}. "
            "Nessuna riga è stata salvata."
        ) from errore
    return len(righe)
