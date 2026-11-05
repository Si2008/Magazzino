"""Anagrafica profili: creazione, aggiornamento e immagine sezione.

Le immagini sono PNG importati dall'utente: vengono COPIATE in una
cartella dedicata del programma e nel profilo si salva il percorso
della copia (il file originale dell'utente resta intatto).
"""

import hashlib
import shutil
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.normalizzazione import normalizza_codice
from ..domain import Profilo
from ..file_sicuri import blocco_cartella, destinazione_atomica
from ..db.config import leggi_sezione

# Profilo.immagine_sezione è String(512): il percorso salvato non può superarlo.
_LUNGHEZZA_MAX_PERCORSO = 512


def _hash_file(percorso: Path) -> str:
    sintesi = hashlib.sha256()
    with open(percorso, "rb") as file:
        for blocco in iter(lambda: file.read(65536), b""):
            sintesi.update(blocco)
    return sintesi.hexdigest()


def _stesso_file(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return False


def _destinazione_senza_conflitti(origine: Path, cartella: Path, profilo_id: int) -> Path:
    """Destinazione della copia: mai sovrascrivere un file diverso.

    - destinazione libera: come prima (``cartella / nome``);
    - occupata dallo stesso file (catalogo = cartella di destinazione): nessuna copia;
    - occupata da un file identico (SHA-256): lo si riusa;
    - occupata da un file diverso: ``<stem>-<profilo_id>.png``.
    """
    destinazione = cartella / origine.name
    if not destinazione.exists():
        return destinazione
    if _stesso_file(origine, destinazione):
        return destinazione
    if _hash_file(origine) == _hash_file(destinazione):
        return destinazione
    impronta = _hash_file(origine)
    candidato = cartella / f"{origine.stem}-{profilo_id}-{impronta}{origine.suffix}"
    if candidato.exists() and _hash_file(candidato) != impronta:
        raise FileExistsError("Conflitto sull'immagine: nessun file è stato sovrascritto")
    return candidato


class ProfiloGiaEsistenteError(Exception):
    """Un profilo con lo stesso codice normalizzato esiste già."""

    def __init__(self, codice_normalizzato: str) -> None:
        self.codice_normalizzato = codice_normalizzato
        super().__init__(
            f"Esiste già un profilo con codice '{codice_normalizzato}'"
        )


def crea_profilo(
    session: Session,
    codice: str,
    descrizione: str,
    peso_kg_per_metro: float,
    lunghezza_standard_mm: int,
    utente: str = "",
    *,
    file_immagine: str | Path | None = None,
    auto_immagine: bool = True,
) -> Profilo:
    """Crea un nuovo profilo in anagrafica.

    Il codice viene normalizzato con la funzione di dominio; se un
    profilo con lo stesso codice esiste già si solleva
    :class:`ProfiloGiaEsistenteError`.
    """
    codice_n = normalizza_codice(codice)
    if not codice_n or not descrizione.strip():
        raise ValueError("Codice e descrizione del profilo sono obbligatori")
    if peso_kg_per_metro <= 0 or lunghezza_standard_mm <= 0:
        raise ValueError("Peso e lunghezza standard devono essere positivi")

    with session.begin():
        esistente = session.scalar(select(Profilo).where(Profilo.codice == codice_n))
        if esistente is not None:
            raise ProfiloGiaEsistenteError(codice_n)

        profilo = Profilo(
            codice=codice_n,
            descrizione=descrizione.strip(),
            peso_kg_per_metro=peso_kg_per_metro,
            lunghezza_standard_mm=lunghezza_standard_mm,
        )
        session.add(profilo)
        session.flush()
        if file_immagine is None and auto_immagine:
            from .catalogo_immagini import CatalogoImmagini
            file_immagine = CatalogoImmagini().trova(codice_n)
        if file_immagine is not None:
            _associa_in_transazione(session, profilo.id, file_immagine)

    return profilo


def aggiorna_profilo(
    session: Session,
    profilo_id: int,
    descrizione: str | None = None,
    peso_kg_per_metro: float | None = None,
    lunghezza_standard_mm: int | None = None,
    *,
    file_immagine: str | Path | None = None,
    rimuovi_immagine: bool = False,
) -> Profilo:
    """Aggiorna i campi anagrafici del profilo indicato (solo quelli forniti)."""
    with session.begin():
        profilo = session.get(Profilo, profilo_id)
        if profilo is None:
            raise ValueError(f"Profilo non trovato: id {profilo_id}")
        if descrizione is not None:
            if not descrizione.strip():
                raise ValueError("La descrizione è obbligatoria")
            profilo.descrizione = descrizione.strip()
        if peso_kg_per_metro is not None:
            if peso_kg_per_metro <= 0:
                raise ValueError("Il peso deve essere positivo")
            profilo.peso_kg_per_metro = peso_kg_per_metro
        if lunghezza_standard_mm is not None:
            if lunghezza_standard_mm <= 0:
                raise ValueError("La lunghezza standard deve essere positiva")
            profilo.lunghezza_standard_mm = lunghezza_standard_mm
        if rimuovi_immagine:
            profilo.immagine_sezione = None
        elif file_immagine is not None:
            _associa_in_transazione(session, profilo.id, file_immagine)

    return profilo


def associa_immagine_sezione(
    session: Session,
    profilo_id: int,
    file_origine: str | Path,
    cartella_destinazione: str | Path | None = None,
) -> str:
    with session.begin():
        return _associa_in_transazione(session, profilo_id, file_origine, cartella_destinazione)


def _associa_in_transazione(session, profilo_id, file_origine, cartella_destinazione=None):
    """Copia il PNG dell'utente nella cartella dedicata del programma
    e salva il percorso della copia sul profilo.

    Restituisce il percorso salvato. Accetta solo file ``.png``.
    """
    origine = Path(file_origine)
    if origine.suffix.lower() != ".png":
        raise ValueError("L'immagine della sezione deve essere un file PNG")
    if not origine.is_file():
        raise FileNotFoundError(f"Immagine non trovata: {origine}")
    from PIL import Image
    with Image.open(origine) as immagine:
        if immagine.format != "PNG":
            raise ValueError("Il file non contiene un'immagine PNG")
        immagine.verify()

    _, base = leggi_sezione("immagini")
    cartella = Path(cartella_destinazione) if cartella_destinazione is not None else base / "immagini_sezioni"
    cartella.mkdir(parents=True, exist_ok=True)
    with blocco_cartella(cartella):
        destinazione = _destinazione_senza_conflitti(origine, cartella, profilo_id)
        if len(str(destinazione.resolve())) > _LUNGHEZZA_MAX_PERCORSO:
            raise ValueError("Percorso dell'immagine troppo lungo (massimo 512 caratteri).")
        if not _stesso_file(origine, destinazione) and not destinazione.exists():
            with destinazione_atomica(destinazione) as provvisorio:
                shutil.copyfile(origine, provvisorio)
    percorso_salvato = str(destinazione.resolve())

    profilo = session.get(Profilo, profilo_id)
    if profilo is None:
        raise ValueError(f"Profilo non trovato: id {profilo_id}")
    profilo.immagine_sezione = percorso_salvato

    return percorso_salvato


def rimuovi_immagine_sezione(session: Session, profilo_id: int) -> Profilo:
    """Toglie l'immagine di sezione dal profilo (``immagine_sezione=None``).

    Non cancella il file da disco: toglie solo il riferimento salvato.
    """
    with session.begin():
        profilo = session.get(Profilo, profilo_id)
        if profilo is None:
            raise ValueError(f"Profilo non trovato: id {profilo_id}")
        profilo.immagine_sezione = None

    return profilo
