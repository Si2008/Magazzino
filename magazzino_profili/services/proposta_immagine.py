"""Stato dell'immagine di un NUOVO profilo (logica pura, testabile senza Qt)."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from ..db.normalizzazione import normalizza_codice
from .catalogo_immagini import CatalogoImmagini


class StatoImmagine(Enum):
    NESSUNA = "nessuna"
    PROPOSTA = "proposta"    # trovata nel catalogo, non ancora salvata
    MANUALE = "manuale"      # importata dall'utente: mai sovrascritta
    RIMOSSA = "rimossa"      # tolta dall'utente: non riproporre finché il codice non cambia


class GestoreProposta:
    def __init__(self, catalogo: CatalogoImmagini) -> None:
        self._catalogo = catalogo
        self.stato = StatoImmagine.NESSUNA
        self.percorso: Path | None = None
        self._codice_rimosso: str | None = None

    def azzera(self) -> None:
        self.stato = StatoImmagine.NESSUNA
        self.percorso = None
        self._codice_rimosso = None

    def su_codice_cambiato(self, testo: str) -> None:
        if self.stato is StatoImmagine.MANUALE:
            return
        chiave = normalizza_codice(testo or "")
        if self.stato is StatoImmagine.RIMOSSA:
            if chiave == self._codice_rimosso:
                return
            self._codice_rimosso = None
        trovato = self._catalogo.trova(chiave) if chiave else None
        self.percorso = trovato
        self.stato = StatoImmagine.PROPOSTA if trovato else StatoImmagine.NESSUNA

    def su_importazione_manuale(self, percorso: str | Path) -> None:
        self.stato = StatoImmagine.MANUALE
        self.percorso = Path(percorso)
        self._codice_rimosso = None

    def su_rimozione(self, testo_codice: str) -> None:
        self.stato = StatoImmagine.RIMOSSA
        self.percorso = None
        self._codice_rimosso = normalizza_codice(testo_codice or "")
