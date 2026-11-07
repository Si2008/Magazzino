"""Conferma e risultato della simulazione di un richiamo."""

from collections.abc import Callable
from html import escape

from PySide6.QtWidgets import QMessageBox

from ..services.richiamo_vassoi import EsitoRichiamo, OrigineRichiamo, simula_richiamo
from .messaggi import chiedi_conferma


def conferma_simulazione(
    parent,
    *,
    codice: str,
    descrizione: str,
    barcode: str,
    vassoio: str,
    origine: OrigineRichiamo,
    selezione_attiva: Callable[[], bool],
) -> None:
    titolo = "Simulazione richiamo vassoio"
    testo = (
        f"<p>Profilo: {escape(codice)}<br>Descrizione: {escape(descrizione or 'Non disponibile')}<br>"
        f"Barcode: {escape(barcode)}<br>Vassoio: {escape(vassoio)}</p>"
        "Nessun comando verrà inviato a ICON."
    )
    if not chiedi_conferma(parent, titolo, testo, "Simula richiamo"):
        return
    if not selezione_attiva():
        QMessageBox.warning(parent, titolo, "La selezione è cambiata. Seleziona di nuovo il pezzo.")
        return

    risultato = simula_richiamo(vassoio, origine)
    mostra = QMessageBox.information if risultato.esito is EsitoRichiamo.SIMULATO else QMessageBox.warning
    mostra(parent, titolo, risultato.messaggio)
