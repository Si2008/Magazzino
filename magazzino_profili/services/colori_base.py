"""Colori di partenza (approssimati) dedotti dal codice colore: solo suggerimenti."""

from __future__ import annotations

import re

_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")

# Valori APPROSSIMATI per la visualizzazione (non sono i valori ufficiali RAL).
_RAL: dict[str, str] = {
    "1013": "#E3D9C6",   # bianco perla
    "6005": "#2F4538",   # verde muschio
    "8017": "#45322E",   # marrone cioccolato
    "9010": "#F1ECE1",   # bianco puro
    "9011": "#23282B",   # nero grafite
    "7016": "#383E42",   # antracite, approssimazione per lo schermo
    "9005": "#0E0E10",
    "8014": "#4A3728",
}
_CODICI_NOTI: dict[str, str] = {}  # i codici del fornitore richiedono un valore confermato

# Radici del nome -> colore. Si cerca la radice più lunga contenuta nella parte.
_RADICI: tuple[tuple[str, str], ...] = (
    ("ANTRACITE", "#3A3F44"),
    ("MARRCUOIO", "#8B5A2B"),
    ("CUOIO", "#8B5A2B"),
    ("DOUG", "#B4824E"),      # effetto legno douglas
    ("ARANCION", "#E07B1F"),
    ("ARGENTO", "#B9BDC4"),
    ("BIANCO", "#F2F2EE"),
    ("BRONZO", "#8A6A43"),
    ("CORTEN", "#8C4A2F"),
    ("GREZZO", "#A9ADB2"),
    ("GRIGIO", "#8A8F96"),
    ("MUSC", "#5E6B3A"),
    ("MARR", "#5B4030"),
    ("NERO", "#1E1F22"),
    ("PINO", "#C8A878"),      # effetto legno pino
    ("ROSSO", "#B63A32"),
    ("VERD", "#3F6B4F"),
)
_RADICI_ORDINATE = sorted(_RADICI, key=lambda r: -len(r[0]))
_SEPARATORI = re.compile(r"[-/]+")
_NON_ALNUM = re.compile(r"[^A-Z0-9]")


def normalizza_hex(valore: str | None) -> str | None:
    """``#rrggbb`` maiuscolo oppure ``None`` se non valido."""
    if not isinstance(valore, str):
        return None
    v = valore.strip()
    if not v.startswith("#"):
        v = "#" + v
    return v.upper() if _HEX.match(v) else None


def _colore_di_parte(parte: str) -> str | None:
    p = _NON_ALNUM.sub("", parte.upper())
    if not p:
        return None
    if p in _CODICI_NOTI:
        return _CODICI_NOTI[p]
    m = re.match(r"^(?:RAL)?(\d{4})(?:[A-Z]*)$", p)
    if m:
        return _RAL.get(m.group(1))
    # nome: la radice più lunga contenuta; es. VERDEMUSC -> MUSC prevale su VERD
    for radice, hx in _RADICI_ORDINATE:
        if radice in p:
            return hx
    return None


def suggerisci_colori(codice: str, nome: str = "") -> tuple[str, ...] | None:
    """Uno o due colori suggeriti (bicolore: ``A-B`` o ``A/B``), altrimenti ``None``.

    Se anche una sola parte non è riconosciuta restituisce ``None``: meglio
    "da definire" che un colore sbagliato.
    """
    testo = (codice or "").upper().strip()
    if not testo:
        return None
    parti = [p for p in _SEPARATORI.split(testo) if p]
    if not 1 <= len(parti) <= 2:
        return None
    colori = [_colore_di_parte(p) for p in parti]
    if any(c is None for c in colori) and nome.strip() and nome.strip().upper() != testo:
        parti_nome = [p for p in _SEPARATORI.split(nome.upper()) if p]
        if len(parti_nome) == len(parti):
            colori = [c or _colore_di_parte(n) for c, n in zip(colori, parti_nome)]
    if any(c is None for c in colori):
        return None
    return tuple(colori)  # type: ignore[arg-type]
