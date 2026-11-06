"""Fase 8 — ``ui.registro_colori`` (UI, offscreen): Swatch, priorità, pixmap.

Verifica a pixel: tinta unita ESATTA al centro (tema scuro E chiaro),
bicolore diviso a metà, «sbiadito» = solo trasparenza, non definito =
cerchio tratteggiato (NESSUN pixel pieno al centro).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtGui import QPixmap

from magazzino_profili.domain import Colore
from magazzino_profili.ui import registro_colori as rc
from magazzino_profili.ui.tema import alterna_tema, tema_attivo


def _factory(tmp_path: Path, nome_db: str = "registro.db"):
    from magazzino_profili.db import crea_engine, crea_session_factory, crea_tabelle

    eng = crea_engine(url=f"sqlite:///{tmp_path / nome_db}")
    crea_tabelle(eng)
    return crea_session_factory(eng)


def _rgb(px) -> tuple[int, int, int]:
    return (px.red(), px.green(), px.blue())


# ------------------------------------------------------------------ Swatch
def test_swatch_css_e_descrizione() -> None:
    unita = rc.Swatch(("#B63A32",), rc.CONFERMATO)
    assert unita.css() == "#B63A32"
    assert unita.definito

    bicolore = rc.Swatch(("#111111", "#F2F2EE"), rc.SUGGERITO)
    assert "qlineargradient" in bicolore.css()
    assert "#111111" in bicolore.css() and "#F2F2EE" in bicolore.css()
    assert "suggerito" in bicolore.descrizione()

    vuoto = rc.Swatch((), rc.NON_DEFINITO)
    assert not vuoto.definito
    assert vuoto.css() == "#9aa0a8"                    # neutro, mai casuale
    assert vuoto.descrizione() == "Colore non definito"


# ------------------------------------------------------------------ priorità
def test_priorita_confermato_suggerito_non_definito() -> None:
    rc.registro().carica([
        ("NERO", "Nero", "#123456"),        # confermato: ha la precedenza
        ("RAL1013", "Bianco perla", None),  # suggerito dal codice
        ("AN007", "Finitura X", None),      # non definito
        ("NERO-ROSSO", "Bicolore", None),   # bicolore suggerito
    ])
    reg = rc.registro()
    assert reg.swatch("nero").colori == ("#123456",)          # maiuscole/minuscole
    assert reg.swatch("nero").origine == rc.CONFERMATO
    assert reg.swatch("RAL1013").colori == ("#E3D9C6",)
    assert reg.swatch("RAL1013").origine == rc.SUGGERITO
    assert reg.swatch("AN007").origine == rc.NON_DEFINITO
    assert reg.swatch("NERO-ROSSO").colori == ("#1E1F22", "#B63A32")
    # codice mai visto -> non definito (MAI casuale)
    assert reg.swatch("ZZZ").origine == rc.NON_DEFINITO
    assert reg.swatch("ZZZ").colori == ()


def test_hex_non_valido_ignorato(tmp_path: Path) -> None:
    factory = _factory(tmp_path, "invalido.db")
    s = factory()
    s.add(Colore(codice_normalizzato="NERO", nome_visualizzato="Nero", colore_hex="blu scuro"))
    s.commit()
    rc.ricarica_da_database(s)
    s.close()
    # valore non valido ignorato: si passa al suggerimento
    assert rc.registro().swatch("NERO").origine == rc.SUGGERITO
    assert rc.registro().swatch("NERO").colori == ("#1E1F22",)


def test_ricarica_da_database(tmp_path: Path) -> None:
    factory = _factory(tmp_path, "db.db")
    s = factory()
    s.add(Colore(codice_normalizzato="RAL9010", nome_visualizzato="Bianco puro"))
    s.add(Colore(codice_normalizzato="NERO", nome_visualizzato="Nero", colore_hex="#010203"))
    s.commit()
    rc.ricarica_da_database(s)
    s.close()

    assert rc.registro().swatch("RAL9010").origine == rc.SUGGERITO
    assert rc.registro().swatch("RAL9010").colori == ("#F1ECE1",)
    assert rc.registro().swatch("NERO").colori == ("#010203",)
    assert rc.registro().swatch("NERO").origine == rc.CONFERMATO


# ------------------------------------------------------------------ pixmap
def test_pixmap_tinta_unita_centro_esatto_tema_scuro_e_chiaro(qapp) -> None:  # noqa: ARG001
    scuro = tema_attivo()
    alterna_tema()
    try:
        chiaro = tema_attivo()
        for t in (scuro, chiaro):
            img = rc.pixmap_swatch(rc.Swatch(("#B63A32",), rc.CONFERMATO), 32, t)
            assert isinstance(img, QPixmap) and img.width() == 32
            assert _rgb(img.toImage().pixelColor(16, 16)) == (0xB6, 0x3A, 0x32)
    finally:
        alterna_tema()


def test_pixmap_bicolore_meta_sinistra_destra(qapp) -> None:  # noqa: ARG001
    t = tema_attivo()
    img = rc.pixmap_swatch(rc.Swatch(("#111111", "#F2F2EE"), rc.SUGGERITO), 32, t)
    assert _rgb(img.toImage().pixelColor(8, 16)) == (0x11, 0x11, 0x11)
    assert _rgb(img.toImage().pixelColor(24, 16)) == (0xF2, 0xF2, 0xEE)


def test_pixmap_sbiadito_cambia_solo_alfa(qapp) -> None:  # noqa: ARG001
    t = tema_attivo()
    img = rc.pixmap_swatch(rc.Swatch(("#B63A32",), rc.CONFERMATO), 32, t, sbiadito=True)
    px = img.toImage().pixelColor(16, 16)
    assert px.alpha() < 255                            # solo trasparenza
    # QPixmap usa alpha premoltiplicato: la conversione RGB può arrotondare di 1.
    assert all(abs(a - b) <= 1 for a, b in zip(_rgb(px), (0xB6, 0x3A, 0x32)))


def test_pixmap_non_definito_cerchio_tratteggiato(qapp) -> None:  # noqa: ARG001
    """NESSUN riempimento pieno: solo anello tratteggiato + «?" (pochi pixel)."""
    t = tema_attivo()
    img = rc.pixmap_swatch(rc.Swatch((), rc.NON_DEFINITO), 32, t)
    im = img.toImage()
    opachi = sum(1 for y in range(32) for x in range(32) if im.pixelColor(x, y).alpha() > 128)
    # Un disco PIENO di d=32 sarebbe ~700 pixel su 1024; anello + «?» ne usa molti meno.
    assert 50 < opachi < 400, opachi
    assert rc.Swatch((), rc.NON_DEFINITO).descrizione() == "Colore non definito"
