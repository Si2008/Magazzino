"""Controllo periodico delle scadenze (barcode «Scaricato» da almeno 48 ore).

Gira in un thread di sottofondo ma NON si fida di timer in memoria: a ogni giro
rilegge i dati persistenti (stato e orario dell'ultimo passaggio), quindi dopo un
riavvio dell'app o del computer la scadenza è identica. Il primo controllo parte
subito all'avvio, nel thread: non rallenta l'apertura della finestra.
"""

import logging
import threading
from collections.abc import Callable
from datetime import datetime

from .stati import elimina_scaduti, utc_now

logger = logging.getLogger(__name__)


class ControlloScadenze:
    def __init__(
        self,
        factory,
        intervallo_secondi: float = 300.0,
        *,
        now: Callable[[], datetime] = utc_now,
        su_eliminati: Callable[[int], None] | None = None,
    ) -> None:
        self._factory = factory
        self._intervallo = intervallo_secondi
        self._now = now
        self._su_eliminati = su_eliminati  # chiamato nel thread del controllo: in Qt usa un segnale
        self._fermo = threading.Event()
        self._thread: threading.Thread | None = None

    def esegui_ora(self) -> int:
        """Un controllo completo. Un errore viene registrato con traceback e non ferma il servizio."""
        try:
            eliminati = elimina_scaduti(self._factory, now=self._now)
        except Exception:  # noqa: BLE001 - il ciclo deve sopravvivere; il traceback resta nel log
            logger.exception("Controllo scadenze non riuscito: si riprova al prossimo giro")
            return 0
        if eliminati and self._su_eliminati is not None:
            try:
                self._su_eliminati(eliminati)
            except Exception:  # noqa: BLE001
                logger.exception("Notifica delle eliminazioni automatiche non riuscita")
        return eliminati

    def _ciclo(self) -> None:
        while not self._fermo.is_set():
            self.esegui_ora()
            self._fermo.wait(self._intervallo)

    def avvia(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._fermo.clear()
        self._thread = threading.Thread(target=self._ciclo, name="controllo-scadenze", daemon=True)
        self._thread.start()

    def ferma(self, timeout: float = 10.0) -> None:
        self._fermo.set()
        if self._thread is not None:
            self._thread.join(timeout)
            self._thread = None
