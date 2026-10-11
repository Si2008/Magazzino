"""Anagrafica profili: creazione, aggiornamento e immagine sezione.

Le immagini sono PNG importati dall'utente: vengono COPIATE in una
cartella dedicata del programma e nel profilo si salva il percorso
della copia (il file originale dell'utente resta intatto).
"""

import shutil
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.normalizzazione import normalizza_codice
from ..domain import Profilo


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

    return profilo


def aggiorna_profilo(
    session: Session,
    profilo_id: int,
    descrizione: str | None = None,
    peso_kg_per_metro: float | None = None,
    lunghezza_standard_mm: int | None = None,
) -> Profilo:
    """Aggiorna i campi anagrafici del profilo indicato (solo quelli forniti)."""
    with session.begin():
        profilo = session.get(Profilo, profilo_id)
        if profilo is None:
            raise ValueError(f"Profilo non trovato: id {profilo_id}")
        if descrizione is not None:
            profilo.descrizione = descrizione.strip()
        if peso_kg_per_metro is not None:
            if peso_kg_per_metro <= 0:
                raise ValueError("Il peso deve essere positivo")
            profilo.peso_kg_per_metro = peso_kg_per_metro
        if lunghezza_standard_mm is not None:
            if lunghezza_standard_mm <= 0:
                raise ValueError("La lunghezza standard deve essere positiva")
            profilo.lunghezza_standard_mm = lunghezza_standard_mm

    return profilo


def associa_immagine_sezione(
    session: Session,
    profilo_id: int,
    file_origine: str | Path,
    cartella_destinazione: str | Path = "immagini_sezioni",
) -> str:
    """Copia il PNG dell'utente nella cartella dedicata del programma
    e salva il percorso della copia sul profilo.

    Restituisce il percorso salvato. Accetta solo file ``.png``.
    """
    origine = Path(file_origine)
    if origine.suffix.lower() != ".png":
        raise ValueError("L'immagine della sezione deve essere un file PNG")
    if not origine.is_file():
        raise FileNotFoundError(f"Immagine non trovata: {origine}")

    cartella = Path(cartella_destinazione)
    cartella.mkdir(parents=True, exist_ok=True)
    destinazione = cartella / origine.name
    shutil.copy2(origine, destinazione)
    percorso_salvato = str(destinazione.resolve())

    with session.begin():
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
