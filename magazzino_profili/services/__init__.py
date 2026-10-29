"""Pacchetto dei servizi di magazzino: carico, scarico, spezzoni e giacenza."""

from ..domain import QuantitaInsufficienteError
from .carico import carica
from .eccezioni import (
    BarcodeDuplicatoError,
    PezzoEliminatoError,
    PezzoNonTrovatoError,
    ProfiloNonTrovatoError,
    SpezzoneNonTrovatoError,
)
from .pezzi import aggiorna_barcode, imposta_numero_vassoio, imposta_scorta_minima
from .scarico import scarica
from .stati import (
    STATI_BARCODE,
    elimina_manualmente,
    elimina_scaduti,
    elimina_scaduto,
    imposta_stato,
    lista_scaduti_per_eliminazione,
)
from .spezzoni import registra_spezzone, utilizza_spezzone

__all__ = [
    "STATI_BARCODE",
    "BarcodeDuplicatoError",
    "PezzoEliminatoError",
    "PezzoNonTrovatoError",
    "ProfiloNonTrovatoError",
    "QuantitaInsufficienteError",
    "SpezzoneNonTrovatoError",
    "aggiorna_barcode",
    "carica",
    "elimina_manualmente",
    "elimina_scaduti",
    "elimina_scaduto",
    "imposta_numero_vassoio",
    "imposta_scorta_minima",
    "imposta_stato",
    "lista_scaduti_per_eliminazione",
    "registra_spezzone",
    "scarica",
    "utilizza_spezzone",
]
