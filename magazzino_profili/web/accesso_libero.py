"""Identità tecnica condivisa, senza autenticazione, per richiesta del proprietario.

Non identifica una persona. Il campo utente nei movimenti serve soltanto alla
compatibilità dello storico. La protezione dell'accesso remoto è a livello rete.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Operatore:
    username: str = "operatore"
    ruolo: str = "AMMINISTRATORE"


def operatore_corrente() -> Operatore:
    return Operatore()
