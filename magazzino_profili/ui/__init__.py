"""Pacchetto interfaccia utente (PySide6).

La UI non contiene logica di business: chiama solo i moduli
``services/``, ``barcode/``, ``reports/`` e ``sicurezza/``.
"""

from .finestra_principale import DialogoAccesso, FinestraPrincipale

__all__ = ["DialogoAccesso", "FinestraPrincipale"]
