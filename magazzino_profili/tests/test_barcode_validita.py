"""Test della validità dei valori barcode e del campo scanner.

``valida_per_barcode`` deve accettare esattamente i codici prodotti da
``db.normalizzazione.genera_barcode`` (maiuscole, cifre, trattino) e
rifiutare tutto il resto.

La classe ``TestCampoScanner`` usa ``pytest-qt`` per simulare la
digitazione e la pressione di Invio.
"""

import os

# I test del widget Qt girano in modalità headless: la piattaforma va
# fissata PRIMA del primo import di PySide6 in questo processo.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from magazzino_profili.barcode import CampoScanner, valida_per_barcode
from magazzino_profili.db.normalizzazione import genera_barcode


class _FalsoProfilo:
    """Doppio minimo: espone l'attributo ``codice`` atteso."""

    def __init__(self, codice: str) -> None:
        self.codice = codice


class _FalsoColore:
    """Doppio minimo: espone l'attributo ``codice_normalizzato`` atteso."""

    def __init__(self, codice_normalizzato: str) -> None:
        self.codice_normalizzato = codice_normalizzato


def test_accetta_i_codici_generati_da_normalizzazione():
    """Ogni codice che genera_barcode() produce deve essere valido."""
    casi = [
        (_FalsoProfilo("AB12"), _FalsoColore("AN007"), 6000),
        (_FalsoProfilo(" ab/12 x "), _FalsoColore("an 007"), 3000),
        (_FalsoProfilo("PROFILO"), _FalsoColore("ROSSO"), 125),
    ]
    for profilo, colore, lunghezza in casi:
        codice = genera_barcode(profilo, colore, lunghezza)
        assert valida_per_barcode(codice), f"codice generato rigettato a torto: {codice}"


def test_accetta_caratteri_ammissi():
    """Maiuscole, cifre e trattino sono sempre ammessi."""
    assert valida_per_barcode("AB12-AN007-6000")
    assert valida_per_barcode("A")
    assert valida_per_barcode("123")
    assert valida_per_barcode("A-B-C")


def test_rifiuta_caratteri_non_ammissi():
    """Spazi, minuscole, punteggiatura e caratteri accentati: rifiutati."""
    non_ammissi = ["", "   ", "ab12", "AB 12", "AB_12", "AB12é", "AB/12", "AB12.AN007"]
    for valore in non_ammissi:
        assert not valida_per_barcode(valore), f"valore accettato a torto: {valore!r}"


class TestCampoScanner:
    """Il campo scanner emette il codice all'Invio e si svuota."""

    def test_invio_emette_il_barcode_e_svuota_il_campo(self, qtbot):
        """Simula la digitazione + Invio: segnale col valore ripulito
        dagli spazi, campo svuotato per la scansione successiva."""
        campo = CampoScanner()
        campo.show()

        ricevuti: list[str] = []
        campo.barcode_scansionato.connect(ricevuti.append)

        qtbot.waitSignal(campo.barcode_scansionato)
        QTest.keyClicks(campo, " AB12-AN007-6000 ")
        QTest.keyPress(campo, Qt.Key_Return)

        assert ricevuti == ["AB12-AN007-6000"]
        assert campo.text() == ""

    def test_campo_ha_il_focus_alla_creazione(self, qtbot):
        """Il campo è pronto a ricevere la scansione appena creato."""
        campo = CampoScanner()
        campo.show()
        # In piattaforma headless il focus viene consegnato al primo giro
        # di event loop: attendiamo prima di verificarlo.
        qtbot.wait(50)
        assert campo.hasFocus()

    def test_invio_su_campo_vuoto_non_emette(self, qtbot):
        """Invio su campo vuoto: nessun segnale, campo resta vuoto."""
        campo = CampoScanner()
        campo.show()

        ricevuti: list[str] = []
        campo.barcode_scansionato.connect(ricevuti.append)

        QTest.keyPress(campo, Qt.Key_Return)

        assert ricevuti == []
        assert campo.text() == ""
