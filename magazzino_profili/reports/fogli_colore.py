"""Nomi di foglio compatibili con Excel e ODS, distinti anche dopo la pulizia."""
import re


def nome_foglio_colore(codice, occupati):
    base = re.sub(r"[\x00-\x1f\x7f\\/*?:\[\]]", "-", str(codice)).strip().strip("'") or "Senza colore"
    base = base[:31]
    nome, numero = base, 2
    while nome.casefold() in occupati:
        suffisso = f" ({numero})"
        nome = base[:31-len(suffisso)] + suffisso
        numero += 1
    occupati.add(nome.casefold())
    return nome
