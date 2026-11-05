"""Fase 8 — ``services.colori_base``: ``normalizza_hex`` e ``suggerisci_colori``.

I valori sono approssimazioni per la visualizzazione. Mai un colore casuale
da hash: se anche una sola parte del codice non è riconosciuta -> ``None``.
"""

from __future__ import annotations

import pytest

from magazzino_profili.services.colori_base import normalizza_hex, suggerisci_colori


def test_normalizza_hex_validi() -> None:
    assert normalizza_hex("#b63a32") == "#B63A32"
    assert normalizza_hex("b63a32") == "#B63A32"      # senza #: accettato
    assert normalizza_hex("  #B63A32  ") == "#B63A32"
    assert normalizza_hex("#E3D9C6") == "#E3D9C6"


def test_normalizza_hex_invalidi() -> None:
    assert normalizza_hex("#b63a3") is None           # 5 cifre
    assert normalizza_hex("#b63a32ff") is None        # 7 cifre
    assert normalizza_hex("#gggggg") is None
    assert normalizza_hex("blu") is None
    assert normalizza_hex("") is None
    assert normalizza_hex(None) is None               # type: ignore[arg-type]
    assert normalizza_hex(123) is None                # type: ignore[arg-type]


# ------------------------------------------------------------------ suggerimenti
def test_suggerisci_ral_e_nomi_semplici() -> None:
    assert suggerisci_colori("RAL1013") == ("#E3D9C6",)
    assert suggerisci_colori("ral 9010") == ("#F1ECE1",)   # minuscolo + spazi
    assert suggerisci_colori("NERO") == ("#1E1F22",)
    assert suggerisci_colori("bianco") == ("#F2F2EE",)


def test_suggerisci_radice_piu_lunga_prevale() -> None:
    # VERDEMUSC -> MUSC (più lunga) prevale su VERD
    assert suggerisci_colori("VERDEMUSC") == ("#5E6B3A",)
    assert suggerisci_colori("MARR.CUOIO") == ("#8B5A2B",)  # MARRCUOIO / CUOIO
    assert suggerisci_colori("MARR.MART") == ("#5B4030",)   # MARR


def test_suggerisci_bicolore() -> None:
    assert suggerisci_colori("NERO-ROSSO") == ("#1E1F22", "#B63A32")
    assert suggerisci_colori("NERO/ROSSO") == ("#1E1F22", "#B63A32")
    assert suggerisci_colori("RAL1013-RAL6005") == ("#E3D9C6", "#2F4538")
    assert suggerisci_colori("9010-NERO") == ("#F1ECE1", "#1E1F22")


def test_suggerisci_una_parta_sconosciuta_none() -> None:
    assert suggerisci_colori("RAL1013-AN007") is None
    assert suggerisci_colori("NERO-BLUBLU") is None
    assert suggerisci_colori("AZ560FA-MD37") is None


# I 34 codici REALI del backup 19/10/2026 -> esattamente i colori indicati (Spec 2).
CODICI_REALI_RICONOSCIUTI: dict[str, tuple[str, ...]] = {
    "RAL1013": ("#E3D9C6",),
    "BIANCOOP": ("#F2F2EE",),
    "RAL9010": ("#F1ECE1",),
    "ARANCION": ("#E07B1F",),
    "RAL9011": ("#23282B",),
    "RAL6005": ("#2F4538",),
    "RAL8017": ("#45322E",),
    "CORTEN": ("#8C4A2F",),
    "W.DOUG.": ("#B4824E",),
    "PINOSC": ("#C8A878",),
    "9010POLIT.": ("#F1ECE1",),
    "9011POLIT.": ("#23282B",),
    "1013POLIT": ("#E3D9C6",),
    "ROSSORAFF": ("#B63A32",),
    "MARR.MART": ("#5B4030",),
    "MARR.CUOIO": ("#8B5A2B",),
    "GRIGIORAFF": ("#8A8F96",),
    "VERDERAFF": ("#3F6B4F",),
    "VERDEMUSC": ("#5E6B3A",),
    "MARR.RAFF": ("#5B4030",),
    "VERDEMART": ("#3F6B4F",),
    "GRIGIOMART": ("#8A8F96",),
    "GRIGIOM897": ("#8A8F96",),
    "ANTRACITE": ("#3A3F44",),
    "ARGENTO": ("#B9BDC4",),
    "GREZZO": ("#A9ADB2",),
    "BRONZO": ("#8A6A43",),
    "BRONZORAG": ("#8A6A43",),
    "NERO": ("#1E1F22",),
    "NEROPOLI": ("#1E1F22",),
    "NEROPOL.": ("#1E1F22",),
    "9010-VERDMUSCH": ("#F1ECE1", "#5E6B3A"),
    "1013-VERD6063": ("#E3D9C6", "#3F6B4F"),
    "9010-NERO": ("#F1ECE1", "#1E1F22"),
}


def test_colori_base_codici_reali() -> None:
    assert len(CODICI_REALI_RICONOSCIUTI) == 34
    for codice, atteso in CODICI_REALI_RICONOSCIUTI.items():
        assert suggerisci_colori(codice) == atteso, codice


# I 34 codici NON DEFINITI del backup: tutti -> None (mai un colore inventato).
CODICI_NON_DEFINITI: tuple[str, ...] = (
    "AZ558FA", "AZ560FA", "560-1013", "AZ572FA", "AZ622RI", "AZ592RI",
    "AZ576FA", "AZ580FA", "AZ556FA", "VARALLO", "AZ590FA", "AZA08RI",
    "AZW1RI", "AZ610FA", "R800", "AZ618FA", "PONZIO", "MD37", "PKA3",
    "MD30", "UBERAL23", "WPERAL", "MD253", "MD9061", "N.POLI", "B.DFV",
    "DFV", "MD37-AV.EFF.", "M633-AZ576FA", "AZ560FA-MD37", "ZA560FA-MD37",
    "AZ610FA-574FA", "AZ574FA", "580FA-1013",
)


def test_colori_base_34_non_definiti_tutti_none() -> None:
    assert len(CODICI_NON_DEFINITI) == 34
    for codice in CODICI_NON_DEFINITI:
        assert suggerisci_colori(codice) is None, codice


def test_input_strani_senza_eccezioni() -> None:
    assert suggerisci_colori("") is None
    assert suggerisci_colori(None) is None            # type: ignore[arg-type]
    assert suggerisci_colori("!!!") is None           # solo simboli
    assert suggerisci_colori("-") is None
    assert suggerisci_colori("A-B-C") is None         # più di 2 parti
    assert suggerisci_colori("X" * 200) is None
    assert suggerisci_colori("1234567890") is None    # non un RAL a 4 cifre
