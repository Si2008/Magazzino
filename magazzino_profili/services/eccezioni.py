"""Eccezioni dedicate dei servizi di magazzino.

Le eccezioni di dominio (ad esempio ``QuantitaInsufficienteError``)
restano definite in ``domain``: importarle direttamente da
``magazzino_profili.domain`` dove servono.
"""


class ProfiloNonTrovatoError(Exception):
    """Il codice profilo non esiste in anagrafica.

    Il profilo va creato in anagrafica: il carico non lo crea.
    """

    def __init__(self, codice_normalizzato: str) -> None:
        self.codice_normalizzato = codice_normalizzato
        super().__init__(
            f"Profilo non trovato in anagrafica: codice '{codice_normalizzato}'. "
            "Creare il profilo in anagrafica prima di effettuare il carico."
        )


class PezzoNonTrovatoError(Exception):
    """Il pezzo cercato (per combinazione o per barcode) non esiste."""

    def __init__(self, descrizione: str) -> None:
        self.descrizione = descrizione
        super().__init__(f"Pezzo non trovato: {descrizione}")


class SpezzoneNonTrovatoError(Exception):
    """Lo spezzone indicato non esiste in magazzino."""

    def __init__(self, spezzone_id: int) -> None:
        self.spezzone_id = spezzone_id
        super().__init__(f"Spezzone non trovato: id {spezzone_id}")
