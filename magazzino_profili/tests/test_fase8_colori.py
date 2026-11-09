"""Fase 8: colori — dizionario, registro, servizi, interfaccia (offscreen).

Copre: ``normalizza_hex``, ``suggerisci_colori`` (RAL / nomi / bicolore /
ignoto → mai colore casuale), ``Swatch.css`` / ``descrizione``,
``ricarica_da_database``, ``imposta_colore_hex`` (sessioni nuove per ogni
chiamata) e il dialogo «Gestione colori» + chip di Inventario in offscreen.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ------------------------------------------------------------------ helpers
def _factory(tmp_path: Path, nome_db: str = "fase8.db"):
    from magazzino_profili.db import crea_engine, crea_session_factory, crea_tabelle

    eng = crea_engine(url=f"sqlite:///{tmp_path / nome_db}")
    crea_tabelle(eng)
    return crea_session_factory(eng)


# ------------------------------------------------------------------ colori_base
def test_normalizza_hex() -> None:
    from magazzino_profili.services.colori_base import normalizza_hex

    assert normalizza_hex("#b63a32") == "#B63A32"
    assert normalizza_hex("b63a32") == "#B63A32"
    assert normalizza_hex("  #B63A32  ") == "#B63A32"
    # non validi
    assert normalizza_hex("#b63a3") is None
    assert normalizza_hex("#b63a32ff") is None
    assert normalizza_hex("#gggggg") is None
    assert normalizza_hex("") is None
    assert normalizza_hex(None) is None
    assert normalizza_hex("blu") is None


def test_suggerisci_colori_ral_e_nomi() -> None:
    from magazzino_profili.services.colori_base import suggerisci_colori

    assert suggerisci_colori("RAL1013") == ("#E3D9C6",)
    assert suggerisci_colori("ral 9010") == ("#F1ECE1",)
    assert suggerisci_colori("NERO") == ("#1E1F22",)
    assert suggerisci_colori("bianco") == ("#F2F2EE",)
    # radice più lunga prevale: VERDEMUSC -> MUSC, non VERD
    assert suggerisci_colori("VERDEMUSC") == ("#5E6B3A",)
    assert suggerisci_colori("MARRCUOIO") == ("#8B5A2B",)  # radice MARRCUOIO (come CUOIO)


def test_suggerisci_colori_bicolore() -> None:
    from magazzino_profili.services.colori_base import suggerisci_colori

    assert suggerisci_colori("NERO-ROSSO") == ("#1E1F22", "#B63A32")
    assert suggerisci_colori("NERO/ROSSO") == ("#1E1F22", "#B63A32")
    assert suggerisci_colori("RAL1013-RAL6005") == ("#E3D9C6", "#2F4538")
    # una parte sola non riconosciuta -> None (mai un colore sbagliato)
    assert suggerisci_colori("RAL1013-AN007") is None


def test_suggerisci_colori_ignoti_da_sempre_none() -> None:
    from magazzino_profili.services.colori_base import suggerisci_colori

    assert suggerisci_colori("AN007") is None
    assert suggerisci_colori("RAL 9999") is None
    assert suggerisci_colori("NERO-BLUBLU") is None
    assert suggerisci_colori("") is None
    assert suggerisci_colori(None) is None  # type: ignore[arg-type]
    assert suggerisci_colori("A-B-C") is None


# ------------------------------------------------------------------ registro
def test_swatch_css_e_descrizione() -> None:
    from magazzino_profili.ui import registro_colori as rc

    unita = rc.Swatch(("#B63A32",), rc.CONFERMATO)
    assert unita.css() == "#B63A32"
    assert unita.descrizione() == "#B63A32 (confermato)"

    bicolore = rc.Swatch(("#111111", "#F2F2EE"), rc.SUGGERITO)
    assert "qlineargradient" in bicolore.css()
    assert "#111111" in bicolore.css() and "#F2F2EE" in bicolore.css()
    assert "(suggerito" in bicolore.descrizione()

    vuoto = rc.Swatch((), rc.NON_DEFINITO)
    assert vuoto.css() == "#9aa0a8"
    assert vuoto.descrizione() == "Colore non definito"


def test_registro_priorita_confermato_suggerito_ignoto() -> None:
    from magazzino_profili.ui import registro_colori as rc

    rc.registro().carica([
        ("NERO", "Nero", "#123456"),        # confermato: ha la precedenza
        ("RAL1013", "Bianco perla", None),  # suggerito dal codice
        ("AN007", "Finitura X", None),      # non definito
        ("NERO-ROSSO", "Bicolore", None),   # bicolore suggerito
    ])
    assert rc.registro().swatch("nero").colori == ("#123456",)
    assert rc.registro().swatch("nero").origine == rc.CONFERMATO
    assert rc.registro().swatch("RAL1013").colori == ("#E3D9C6",)
    assert rc.registro().swatch("RAL1013").origine == rc.SUGGERITO
    assert rc.registro().swatch("AN007").origine == rc.NON_DEFINITO
    assert not rc.registro().swatch("AN007").definito
    assert rc.registro().swatch("NERO-ROSSO").colori == ("#1E1F22", "#B63A32")
    # codice mai visto -> non definito (mai casuale)
    assert rc.registro().swatch("ZZZ").origine == rc.NON_DEFINITO


def test_ricarica_da_database(tmp_path: Path) -> None:
    from magazzino_profili.domain import Colore
    from magazzino_profili.ui import registro_colori as rc

    factory = _factory(tmp_path, "registro.db")
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


def test_pixmap_swatch_offscreen(qapp) -> None:  # noqa: ARG001
    from PySide6.QtGui import QPixmap
    from magazzino_profili.ui import registro_colori as rc
    from magazzino_profili.ui.tema import tema_attivo

    t = tema_attivo()
    # tinta unita: il centro deve essere il colore esatto
    img = rc.pixmap_swatch(rc.Swatch(("#B63A32",), rc.CONFERMATO), 32, t)
    assert isinstance(img, QPixmap)
    assert img.width() == 32
    centro = img.toImage().pixelColor(16, 16)
    assert (centro.red(), centro.green(), centro.blue()) == (0xB6, 0x3A, 0x32)

    # bicolore: metà sinistra e metà destra diverse
    bicolore = rc.pixmap_swatch(rc.Swatch(("#111111", "#F2F2EE"), rc.SUGGERITO), 32, t)
    sx = bicolore.toImage().pixelColor(8, 16)
    dx = bicolore.toImage().pixelColor(24, 16)
    assert (sx.red(), sx.green(), sx.blue()) == (0x11, 0x11, 0x11)
    assert (dx.red(), dx.green(), dx.blue()) == (0xF2, 0xF2, 0xEE)

    # sbiadito: trasparenza (alpha < 255 al centro)
    sbiadito = rc.pixmap_swatch(rc.Swatch(("#B63A32",), rc.CONFERMATO), 32, t, sbiadito=True)
    assert sbiadito.toImage().pixelColor(16, 16).alpha() < 255


# ------------------------------------------------------------------ servizi
def test_imposta_colore_hex(tmp_path: Path) -> None:
    from magazzino_profili.domain import Colore
    from magazzino_profili.services.colori import imposta_colore_hex

    factory = _factory(tmp_path, "servizi.db")
    s = factory()
    colore = Colore(codice_normalizzato="NERO", nome_visualizzato="Nero")
    s.add(colore)
    s.commit()
    cid = colore.id
    s.close()

    # valore non valido -> ValueError e nessuna scrittura
    s = factory()
    with pytest.raises(ValueError):
        imposta_colore_hex(s, cid, "blu scuro")
    s.close()
    s = factory()
    assert s.get(Colore, cid).colore_hex is None
    s.close()

    # esagono valido -> salvato in maiuscolo
    s = factory()
    assert imposta_colore_hex(s, cid, "#b63a32") == "#B63A32"
    s.close()
    s = factory()
    assert s.get(Colore, cid).colore_hex == "#B63A32"
    s.close()

    # None / vuoto -> rimosso
    s = factory()
    assert imposta_colore_hex(s, cid, None) is None
    s.close()
    s = factory()
    assert s.get(Colore, cid).colore_hex is None
    s.close()

    # colore inesistente -> LookupError
    s = factory()
    with pytest.raises(LookupError):
        imposta_colore_hex(s, 9999, "#111111")
    s.close()


# ------------------------------------------------------------------ interfaccia
def test_icona_colore_offscreen(qtbot) -> None:  # noqa: ARG001
    from magazzino_profili.ui import registro_colori as rc
    from magazzino_profili.ui.componenti import icona_colore

    rc.registro().carica([
        ("NERO", "Nero", "#B63A32"),
        ("AN007", "Finitura X", None),
    ])
    ico = icona_colore("NERO", diametro=24)
    assert not ico.isNull()
    assert ico.pixmap(24).width() == 24
    # sbiadita: il centro deve avere alpha < 255
    ico_s = icona_colore("NERO", diametro=24, sbiadita=True)
    assert ico_s.pixmap(24).toImage().pixelColor(12, 12).alpha() < 255
    # codice ignoto: pallino neutro (non nullo, non casuale)
    ico_neutro = icona_colore("AN007", diametro=24)
    assert not ico_neutro.isNull()


def test_dialogo_gestione_colori(qtbot, tmp_path: Path) -> None:
    from magazzino_profili.domain import Colore
    from magazzino_profili.ui import registro_colori as rc
    from magazzino_profili.ui.gestione_colori import GestioneColori

    factory = _factory(tmp_path, "dialogo.db")
    s = factory()
    s.add(Colore(codice_normalizzato="NERO", nome_visualizzato="Nero", colore_hex="#B63A32"))
    s.add(Colore(codice_normalizzato="RAL1013", nome_visualizzato="Bianco perla"))
    s.add(Colore(codice_normalizzato="AN007", nome_visualizzato="Finitura X"))
    s.commit()
    # registro singleton: ricarica da QUESTO database (stato pulito)
    rc.ricarica_da_database(s)
    s.close()

    d = GestioneColori(factory)
    qtbot.addWidget(d)

    assert d.tabella.rowCount() == 3
    assert "1 non definiti" in d.contatori.text()
    assert "1 suggeriti" in d.contatori.text()
    assert "1 confermati" in d.contatori.text()

    # filtro "Suggeriti" -> solo RAL1013
    d.filtro.setCurrentIndex(d.filtro.findData(rc.SUGGERITO))
    assert d.tabella.rowCount() == 1
    assert d.tabella.item(0, 1).text() == "RAL1013"

    # ricerca per nome -> "NERO" (Bianco perla)
    d.filtro.setCurrentIndex(0)
    d.cerca.setText("bianco perla")
    assert d.tabella.rowCount() == 1
    assert d.tabella.item(0, 1).text() == "RAL1013"

    # «Conferma suggerito»: salva il suggerimento a tinta unita (RAL1013 -> #E3D9C6)
    d.cerca.clear()
    # elenco_colori ordina per codice: AN007(0), NERO(1), RAL1013(2)
    d.tabella.selectRow(2)
    assert d.tabella.item(2, 1).text() == "RAL1013"
    assert d._btn_conferma.isEnabled()
    # per NERO (già confermato) il pulsante resta disabilitato
    d.tabella.selectRow(1)
    assert not d._btn_conferma.isEnabled()
    d.tabella.selectRow(2)
    d._azione_conferma()
    s = factory()
    assert s.get(Colore, 2).colore_hex == "#E3D9C6"
    s.close()
    # dopo la conferma: stato "Confermato" e contatori aggiornati
    assert d.tabella.rowCount() == 3
    assert "2 confermati" in d.contatori.text()


def test_tabella_pezzi_chip_da_registro(qtbot, tmp_path: Path) -> None:
    from magazzino_profili.services.anagrafica import crea_profilo
    from magazzino_profili.services import carica
    from magazzino_profili.ui.tabella_pezzi import TabellaPezzi

    factory = _factory(tmp_path, "chip.db")
    s = factory()
    crea_profilo(s, "AB12", "Angolo 120 mm", 1.25, 6000, "test")
    s.commit()
    s.close()
    s = factory()
    carica(s, "AB12", "NERO", 6000, 1, "test", "init")
    s.close()

    t = TabellaPezzi(factory)
    qtbot.addWidget(t)
    t.aggiorna()

    # tab "Tutti" + tab NERO
    assert t._tabbar.count() == 2
    assert t._codice_tab[0] is None
    assert t._codice_tab[1] == "NERO"
    # tooltip della tab: descrizione dello swatch
    assert "suggerito" in t._tabbar.tabToolTip(1).lower()
    # la riga tabella ha il codice in UserRole+1 (Qt 6: UserRole = 256) e tooltip Fase 8
    from PySide6.QtCore import Qt as _Qt

    assert t._tabella.item(0, 2).data(_Qt.ItemDataRole.UserRole + 1) == "NERO"
