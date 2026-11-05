"""Controllo delle scadenze barcode (48 ore in stato «Scaricato») — Fase 12.

Il worker che usa queste funzioni gira nel **processo del server web**
(``python -m magazzino_profili.web.app``), non nel processo desktop:
chiude la finestra non deve fermarlo.

Le funzioni operative vere (48 ore, stato «Scaricato», cancellazione logica
con ``UPDATE ... WHERE`` atomico) vivono già in :mod:`.stati`
(``lista_scaduti_per_eliminazione`` / ``elimina_scaduto``): qui si fanno solo
i due adattamenti richiesti dal worker, mantenendo i nomi a livello di modulo
così che i test possano sostituirli.
"""

from __future__ import annotations

import logging
import os
import threading
import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from sqlalchemy.orm import Session
from ..db.config import leggi_sezione

from .stati import elimina_scaduto as _elimina_scaduto_stati
from .stati import lista_scaduti_per_eliminazione as _lista_scaduti_stati
from .stati import utc_now as _utc_now

logger = logging.getLogger(__name__)

PERCORSO_CONFIG_PREDEFINITO = Path(__file__).resolve().parents[2] / "config.toml"


def ids_scaduti(session: Session, adesso: datetime) -> list[int]:
    """ID dei barcode scaduti secondo l'istante ``adesso`` (fisso per il giro)."""
    return list(_lista_scaduti_stati(session, now=lambda: adesso))


def elimina_scaduto(session: Session, id_: int, *, adesso=None) -> None:
    """Elimina logicamente il barcode ``id_`` solo se risulta ancora scaduto.

    Verifica e scrittura restano una singola ``UPDATE ... WHERE`` atomica: se lo
    stato è cambiato nel frattempo la condizione non è più vera e non accade
    nulla (non si elimina mai un barcode diventato «Caricato»).
    """
    _elimina_scaduto_stati(session, id_, now=(lambda: adesso) if adesso is not None else _utc_now)


# ---------------------------------------------------------------------------
# Worker periodico (processo web)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ParametriScadenze:
    """Parametri del controllo scadenze letti da ``config.toml`` (sezione [scadenze])."""

    intervallo_secondi: int = 300


def leggi_config_scadenze(
    percorso: str | Path | None = None,
) -> ParametriScadenze:
    """Legge la sezione ``[scadenze]`` di config.toml con i default.

    Ricerca: percorso esplicito, variabile d'ambiente ``MAGAZZINO_CONFIG``,
    radice del progetto. Se il file (o la sezione) non c'è, valgono i
    default.
    """
    sezione, _ = leggi_sezione("scadenze", percorso)
    intervallo = int(sezione.get("intervallo_secondi", 300))
    if intervallo <= 0:
        raise ValueError("intervallo_secondi deve essere maggiore di zero")
    return ParametriScadenze(intervallo_secondi=intervallo)


class PianificatoreScadenze:
    """Thread di sottofondo che esegue il controllo scadenze ogni N secondi.

    - Il primo controllo parte subito all'avvio;
    - un errore del database non ferma il ciclo (si riprova al giro successivo);
    - ``ferma()`` è deterministico: attende la fine del giro in corso.
    """

    def __init__(
        self,
        factory: Callable[[], Session],
        intervallo_secondi: float,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._factory = factory
        if intervallo_secondi <= 0:
            raise ValueError("L'intervallo scadenze deve essere positivo")
        self._intervallo = intervallo_secondi
        self._now = now or _utc_now
        self._fermo = threading.Event()
        self._thread: threading.Thread | None = None
        self._blocco = threading.Lock()

    def _elimina_scaduti(self) -> None:
        try:
            momento = self._now()
            sessione = self._factory()
            with sessione:
                ids = list(ids_scaduti(sessione, momento))
            for id_ in ids:
                if self._fermo.is_set():
                    break
                try:
                    with self._factory() as s2:
                        elimina_scaduto(s2, id_, adesso=momento)
                except Exception:
                    logger.exception("Scadenza non elaborata per id %s", id_)
        except Exception:
            logger.exception(
                "Controllo scadenze: errore (prossimo giro tra l'intervallo)"
            )

    def _ciclo(self, istanza: "PianificatoreScadenze") -> None:
        """Ciclo del worker: controllo e poi pausa di ``intervallo_secondi``.

        ``istanza`` è esplicito (oltre a ``self``) perché il thread chiama
        ``self._ciclo(self)``: questo consente ai test di sostituire
        ``_ciclo`` a livello di classe e verificarne la chiamata.
        """
        while not istanza._fermo.is_set():
            istanza._elimina_scaduti()
            if istanza._fermo.is_set():
                break
            # Sleep spezzato: ferma() resta reattivo (max ~1 secondo)
            istanza._fermo.wait(istanza._intervallo)

    def avvia(self) -> None:
        """Avvia il thread (idempotente: una chiamata multipla non duplica).

        Il primo controllo è immediato (specifica Fase 12).
        """
        with self._blocco:
            if self._thread is not None and self._thread.is_alive():
                return
            self._fermo.clear()
            self._thread = threading.Thread(
                target=self._ciclo, args=(self,), name="scadenze-worker"
            )
            self._thread.start()

    def ferma(self, timeout: float = 10.0) -> None:
        self._fermo.set()
        with self._blocco:
            if self._thread is not None:
                self._thread.join(timeout)
                if self._thread.is_alive():
                    raise TimeoutError("Il controllo scadenze non si è ancora arrestato")
