"""Crea un utente del Magazzino Profili (con ruolo).

Uso::

    python -m magazzino_profili.crea_utente                     # interattivo (chiede i dati)
    python -m magazzino_profili.crea_utente NOME PASSWORD       # ruolo = OPERATORE
    python -m magazzino_profili.crea_utente NOME PASSWORD AMMINISTRATORE

Ruoli: AMMINISTRATORE, OPERATORE, SOLA_LETTURA.
La password viene salvata in hash bcrypt.
"""

from __future__ import annotations

import secrets
import sys
from string import ascii_letters, digits

from .db import (
    ErroreConfigurazione,
    crea_engine,
    crea_session_factory,
    leggi_config,
)
from .sicurezza import Ruolo, crea_utente


def _password_casuale(lunghezza: int = 12) -> str:
    """Genera una password casuale sicura (solo alfanumerici)."""
    return "".join(secrets.choice(ascii_letters + digits) for _ in range(lunghezza))


def main() -> int:
    argomenti = sys.argv[1:]
    if "--help" in argomenti or "-h" in argomenti:
        print(__doc__)
        return 0

    nome = argomenti[0] if len(argomenti) > 0 else input("Nome utente: ").strip()
    password = (
        argomenti[1]
        if len(argomenti) > 1
        else (input("Password (vuota = casuale): ") or _password_casuale())
    )
    ruolo_nome = (
        argomenti[2]
        if len(argomenti) > 2
        else input("Ruolo (AMMINISTRATORE/OPERATORE/SOLA_LETTURA): ")
    ).upper()
    ruolo = Ruolo(ruolo_nome)

    try:
        config = leggi_config()
    except ErroreConfigurazione as errore:
        print(f"ERRORE config.toml: {errore}")
        return 1

    engine = crea_engine(config=config)
    factory = crea_session_factory(engine)
    with factory() as session:
        try:
            crea_utente(session, nome, password, ruolo)
        except ValueError as errore:
            print(f"ERRORE: {errore}")
            return 1
    print(f"Utente creato: {nome} (ruolo {ruolo.value})")
    if len(argomenti) < 2:
        print(f"Password: {password}  (conservalala!)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
