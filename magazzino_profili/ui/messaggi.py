"""Messaggi per l'utente: errori comprensibili e conferme delle operazioni pericolose.

Il testo mostrato in primo piano spiega il problema e cosa fare. Il dettaglio
tecnico (tipo di errore e messaggio originale) va nel riquadro "Dettagli" del
messaggio e nel registro ``app.log``: non viene nascosto.
"""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QMessageBox, QWidget
from sqlalchemy.exc import IntegrityError, OperationalError

from ..domain import QuantitaInsufficienteError
from ..services.anagrafica import ProfiloGiaEsistenteError
from ..services.eccezioni import PezzoNonTrovatoError, ProfiloNonTrovatoError

logger = logging.getLogger("magazzino_profili.ui")


def testo_per_utente(errore: BaseException, azione: str) -> str:
    """Frase in italiano, comprensibile a chi usa il programma."""
    if isinstance(errore, ProfiloNonTrovatoError):
        return (
            f"Il profilo {errore.codice_normalizzato} non è in anagrafica. "
            "Crealo nella scheda Profili, poi riprova."
        )
    if isinstance(errore, QuantitaInsufficienteError):
        return (
            f"Giacenza insufficiente: ci sono {errore.quantita_corrente} pezzi, "
            f"ne hai indicati {errore.quantita_richiesta}. Nessuna modifica è stata salvata."
        )
    if isinstance(errore, PezzoNonTrovatoError):
        return "Nessun pezzo corrisponde a questo barcode o a questa combinazione. Controlla i dati inseriti."
    if isinstance(errore, ProfiloGiaEsistenteError):
        return f"Esiste già un profilo con il codice {errore.codice_normalizzato}."
    if isinstance(errore, OperationalError):
        return (
            "Impossibile comunicare con il database. Verifica che PostgreSQL sia avviato "
            "e riprova. Se il problema continua, consulta app.log."
        )
    if isinstance(errore, IntegrityError):
        return (
            "Il dato non può essere salvato perché è in conflitto con un altro record. "
            "Ricarica la scheda e riprova."
        )
    if isinstance(errore, ValueError):
        # I messaggi di validazione dei servizi sono già in italiano e indicano il problema.
        return str(errore)
    return f"{azione} non è stato completato per un errore imprevisto. I dettagli sono in app.log."


def mostra_errore(parent: QWidget | None, titolo: str, errore: BaseException, azione: str) -> None:
    """Registra l'errore completo nel log e mostra un messaggio comprensibile."""
    logger.error("%s non riuscito", azione, exc_info=errore)
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Warning)
    box.setWindowTitle(titolo)
    box.setText(testo_per_utente(errore, azione))
    box.setDetailedText(f"{type(errore).__name__}: {errore}")
    box.setStandardButtons(QMessageBox.Ok)
    box.exec()


def chiedi_conferma(
    parent: QWidget | None,
    titolo: str,
    testo: str,
    azione: str,
    pericolosa: bool = False,
) -> bool:
    """Chiede conferma esplicita. Il pulsante predefinito è "Annulla"."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Warning if pericolosa else QMessageBox.Question)
    box.setWindowTitle(titolo)
    box.setText(testo)
    annulla = box.addButton("Annulla", QMessageBox.RejectRole)
    conferma = box.addButton(azione, QMessageBox.AcceptRole)
    box.setDefaultButton(annulla)
    box.setEscapeButton(annulla)
    box.exec()
    return box.clickedButton() is conferma
