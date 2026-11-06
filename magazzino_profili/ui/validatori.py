"""Validatori dei campi di testo."""

from __future__ import annotations

from PySide6.QtGui import QValidator


class ValidatoreMaiuscolo(QValidator):
    """Accetta qualsiasi testo ma lo restituisce in maiuscolo.

    Agisce su digitazione, incolla e ``setText``; il segnale ``textChanged``
    arriva una sola volta, già con il testo finale.
    """

    def validate(self, testo: str, posizione: int):
        return (QValidator.State.Acceptable, testo.upper(), posizione)
