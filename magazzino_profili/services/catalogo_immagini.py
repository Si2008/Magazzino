"""Catalogo delle immagini di sezione: ricerca per codice profilo normalizzato.

Il catalogo è una cartella di PNG il cui nome è il codice del profilo
(es. ``AZ2001.png``). I file che iniziano con ``_`` non sono profili.
"""

from __future__ import annotations

import logging
import os
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from ..db.normalizzazione import normalizza_codice

logger = logging.getLogger(__name__)

NOME_CARTELLA_DEFAULT = "catalogo_immagini"
VARIABILE_AMBIENTE = "MAGAZZINO_CATALOGO_IMMAGINI"
_FIRMA_PNG = b"\x89PNG\r\n\x1a\n"
_DIMENSIONE_MAX_BYTE = 20 * 1024 * 1024


def _base_programma() -> Path:
    """Cartella dell'exe (frozen) o radice del progetto. Mai _MEIPASS, mai la CWD."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def _valore_da_config(percorso_config: Path | None) -> str | None:
    from ..db.config import trova_config
    file_config = trova_config(percorso_config)
    candidati = [file_config] if file_config else []
    for file in candidati:
        try:
            if not file.is_file():
                continue
            with open(file, "rb") as fonte:
                dati = tomllib.load(fonte)
        except (OSError, tomllib.TOMLDecodeError) as errore:
            logger.warning("config.toml non leggibile per il catalogo immagini: %s", errore)
            continue
        sezione = dati.get("immagini")
        if isinstance(sezione, dict):
            valore = sezione.get("catalogo")
            if isinstance(valore, str) and valore.strip():
                return valore.strip()
        return None
    return None


def cartella_catalogo(percorso_config: str | Path | None = None) -> Path:
    """Ordine: variabile d'ambiente, ``[immagini] catalogo`` in config.toml, default.

    Un percorso relativo è risolto rispetto a :func:`_base_programma`.
    """
    from ..db.config import trova_config
    file = trova_config(percorso_config)
    base = file.parent if file else _base_programma()
    variabile = os.environ.get(VARIABILE_AMBIENTE, "").strip()
    scelta = variabile or _valore_da_config(Path(percorso_config) if percorso_config else None)
    if scelta:
        percorso = Path(scelta).expanduser()
        return percorso if percorso.is_absolute() else base / percorso
    candidati = [base / NOME_CARTELLA_DEFAULT, _base_programma() / NOME_CARTELLA_DEFAULT]
    if getattr(sys, "_MEIPASS", None):
        candidati.append(Path(sys._MEIPASS) / NOME_CARTELLA_DEFAULT)
    return next((p for p in candidati if p.is_dir() and any(p.glob("*.png"))),
                _base_programma() / NOME_CARTELLA_DEFAULT)


def png_valido(percorso: Path) -> bool:
    """File regolare, firma PNG, dimensione plausibile."""
    try:
        dimensione = percorso.stat().st_size
        if dimensione < len(_FIRMA_PNG) or dimensione > _DIMENSIONE_MAX_BYTE:
            return False
        with open(percorso, "rb") as file:
            return file.read(len(_FIRMA_PNG)) == _FIRMA_PNG
    except OSError:
        return False


@dataclass
class _Indice:
    mtime_ns: int = -1
    voci: dict[str, Path] = field(default_factory=dict)


class CatalogoImmagini:
    """Indice codice normalizzato → PNG, costruito dall'elenco reale della cartella.

    Il percorso di un file NON viene mai costruito dal testo digitato: si cerca
    solo nel dizionario creato leggendo la cartella.
    """

    def __init__(self, cartella: str | Path | None = None) -> None:
        self._cartella = Path(cartella) if cartella is not None else cartella_catalogo()
        self._indice = _Indice()

    @property
    def cartella(self) -> Path:
        return self._cartella

    def _aggiorna_indice(self) -> None:
        try:
            mtime = self._cartella.stat().st_mtime_ns
        except OSError:
            self._indice = _Indice()
            return
        if mtime == self._indice.mtime_ns:
            return
        voci: dict[str, Path] = {}
        ambigui: set[str] = set()
        try:
            with os.scandir(self._cartella) as elenco:
                for voce in elenco:
                    percorso = Path(voce.path)
                    if percorso.suffix.lower() != ".png" or percorso.stem.startswith("_"):
                        continue
                    try:
                        if not voce.is_file():
                            continue
                    except OSError:
                        continue
                    chiave = normalizza_codice(percorso.stem)
                    if not chiave:
                        continue
                    if chiave in voci or chiave in ambigui:
                        ambigui.add(chiave)
                        voci.pop(chiave, None)
                    else:
                        voci[chiave] = percorso
        except OSError as errore:
            logger.warning("Catalogo immagini non leggibile (%s): %s", self._cartella, errore)
            self._indice = _Indice()
            return
        for chiave in sorted(ambigui):
            logger.warning(
                "Catalogo immagini: più file per il codice %s, nessuna proposta", chiave
            )
        self._indice = _Indice(mtime_ns=mtime, voci=voci)

    def trova(self, codice: str) -> Path | None:
        """PNG valido del codice (qualsiasi grafia), oppure ``None``."""
        chiave = normalizza_codice(codice or "")
        if not chiave:
            return None
        self._aggiorna_indice()
        percorso = self._indice.voci.get(chiave)
        if percorso is None or not png_valido(percorso):
            return None
        return percorso
