"""Richiamo di un vassoio in simulazione locale."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from time import monotonic
from typing import Literal

from ..percorsi_installazione import dati_runtime

OrigineRichiamo = Literal["scarico", "commessa"]


class EsitoRichiamo(str, Enum):
    SIMULATO = "simulato"
    VASSOIO_NON_VALIDO = "vassoio_non_valido"
    NON_DISPONIBILE = "non_disponibile"
    RIFIUTATO = "rifiutato"
    SCONOSCIUTO = "sconosciuto"


@dataclass(frozen=True)
class RisultatoRichiamo:
    esito: EsitoRichiamo
    messaggio: str
    durata_secondi: float


def numero_vassoio(valore: str | None) -> str | None:
    """Riconosce un numero di vassoio, anche se preceduto da «Vassoio»."""
    if not isinstance(valore, str) or len(valore) > 128:
        return None
    trovato = re.fullmatch(r"(?:vassoio +)?([0-9]+)", valore.strip(" "), re.IGNORECASE)
    if trovato is None or not trovato[1].strip("0"):
        return None
    return trovato[1]


def _simula(_vassoio: str) -> bool:
    """Simula l'accettazione senza comunicare con l'impianto."""
    return True


def simula_richiamo(
    vassoio: str | None,
    origine: OrigineRichiamo,
    *,
    simulatore: Callable[[str], bool] = _simula,
) -> RisultatoRichiamo:
    """Prova una sola richiesta e registra l'esito nei dati dell'app."""
    inizio = monotonic()
    data_ora = datetime.now().astimezone().isoformat(timespec="seconds")
    numero = numero_vassoio(vassoio)
    if numero is None:
        esito = EsitoRichiamo.VASSOIO_NON_VALIDO
        messaggio = "Il pezzo non ha un numero di vassoio valido."
    else:
        try:
            risposta = simulatore(numero)
        except (FileNotFoundError, ConnectionRefusedError):
            esito = EsitoRichiamo.NON_DISPONIBILE
            messaggio = "Simulazione: ICON non disponibile."
        except (OSError, ValueError):
            esito = EsitoRichiamo.SCONOSCIUTO
            messaggio = "Simulazione: esito sconosciuto. Controlla lo stato prima di riprovare."
        else:
            if risposta is True:
                esito = EsitoRichiamo.SIMULATO
                messaggio = f"Richiamo del vassoio {numero} simulato. Nessun comando inviato a ICON."
            elif risposta is False:
                esito = EsitoRichiamo.RIFIUTATO
                messaggio = "Simulazione: richiesta rifiutata."
            else:
                esito = EsitoRichiamo.SCONOSCIUTO
                messaggio = "Simulazione: esito sconosciuto. Risposta non riconosciuta."

    durata = monotonic() - inizio
    registro = dati_runtime() / "log" / "richiami-vassoi.jsonl"
    try:
        registro.parent.mkdir(parents=True, exist_ok=True)
        voce = dict(data_ora=data_ora, vassoio=numero, origine=origine,
                    modalita="simulazione", esito=esito.value, durata_secondi=durata)
        with registro.open("a", encoding="utf-8") as file:
            file.write(json.dumps(voce, ensure_ascii=False) + "\n")
    except OSError:
        messaggio += "\nIl registro dei richiami non è scrivibile."
    return RisultatoRichiamo(esito, messaggio, durata)
