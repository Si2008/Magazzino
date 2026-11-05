"""Fase 8 — Inventario/Scarico: chip e tabella leggono dallo STESSE registro.

- ``icona_colore``: pallino dal registro, «sbiadita» = solo trasparenza;
- tabella pezzi: chip colore + tooltip + colore della riga = Swatch unico;
- dopo ``imposta_colore_hex`` + ``aggiorna()`` il chip cambia (confermato);
- dialogo «Gestione colori»: filtri, ricerca, «Conferma suggerito».
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt as _Qt
from sqlalchemy import select

from magazzino_profili.domain import Colore
from magazzino_profili.services import carica
from magazzino_profili.services.anagrafica import crea_profilo
from magazzino_profili.services.colori import imposta_colore_hex
from magazzino_profili.ui import registro_colori as rc
from magazzino_profili.ui.componenti import icona_colore
from magazzino_profili.ui.tabella_pezzi import TabellaPezzi


def _factory(tmp_path: Path, nome_db: str = "inv.db"):
    from magazzino_profili.db import crea_engine, crea_session_factory, crea_tabelle

    eng = crea_engine(url=f"sqlite:///{tmp_path / nome_db}")
    crea_tabelle(eng)
    return crea_session_factory(eng)


def _db_con_pozzi(tmp_path: Path) -> object:
    factory = _factory(tmp_path)
    s = factory()
    crea_profilo(s, "AB12", "Angolo 120 mm", 1.25, 6000, "test")
    s.commit()
    s.close()
    s = factory()
    carica(s, "AB12", "NERO", 6000, 1, "test", "init")
    s.close()
    return factory


def test_icona_colore_offscreen(qtbot) -> None:  # noqa: ARG001
    rc.registro().carica([
        ("NERO", "Nero", "#B63A32"),
        ("AN007", "Finitura X", None),
    ])
    ico = icona_colore("NERO", diametro=24)
    assert not ico.isNull()
    assert ico.pixmap(24).width() == 24
    # sbiadita: stessa icona, centro con alpha < 255 (solo trasparenza)
    ico_s = icona_colore("NERO", diametro=24, sbiadita=True)
    assert ico_s.pixmap(24).toImage().pixelColor(12, 12).alpha() < 255
    # codice ignoto: pallino neutro (non nullo, non casuale)
    assert not icona_colore("AN007", diametro=24).isNull()


def test_tabella_pezzi_chip_e_tooltip(qtbot, tmp_path: Path) -> None:
    factory = _db_con_pozzi(tmp_path)
    t = TabellaPezzi(factory)
    qtbot.addWidget(t)
    t.aggiorna()

    # tab «Tutti» + tab NERO
    assert t._tabbar.count() == 2
    assert t._codice_tab[0] is None
    assert t._codice_tab[1] == "NERO"
    assert "suggerito" in t._tabbar.tabToolTip(1).lower()
    # la riga tabella porta il codice in UserRole+1 (stesso Swatch del chip)
    assert t._tabella.item(0, 2).data(_Qt.ItemDataRole.UserRole + 1) == "NERO"


def test_chip_cambia_dopo_imposta_e_aggiorna(qtbot, tmp_path: Path) -> None:
    factory = _db_con_pozzi(tmp_path)
    t = TabellaPezzi(factory)
    qtbot.addWidget(t)
    t.aggiorna()
    prima = t._tabbar.tabIcon(1).pixmap(24).toImage().pixelColor(12, 12)
    assert (prima.red(), prima.green(), prima.blue()) == (0x1E, 0x1F, 0x22)  # suggerito NERO

    # l'utente CONFERMA un hex diverso: dopo aggiorna() il chip mostra il confermato
    s = factory()
    colore = next(iter(s.scalars(select(Colore))))
    colore_id = colore.id
    s.close()
    s = factory()
    imposta_colore_hex(s, colore_id, "#FF00FF")
    s.close()
    t.aggiorna()
    dopo = t._tabbar.tabIcon(1).pixmap(24).toImage().pixelColor(12, 12)
    assert (dopo.red(), dopo.green(), dopo.blue()) == (0xFF, 0x00, 0xFF)
    assert "confermato" in t._tabbar.tabToolTip(1).lower()


def test_dialogo_gestione_colori(qtbot, tmp_path: Path) -> None:
    from magazzino_profili.ui.gestione_colori import GestioneColori

    factory = _factory(tmp_path, "dialogo.db")
    s = factory()
    s.add(Colore(codice_normalizzato="NERO", nome_visualizzato="Nero", colore_hex="#B63A32"))
    s.add(Colore(codice_normalizzato="RAL1013", nome_visualizzato="Bianco perla"))
    s.add(Colore(codice_normalizzato="AN007", nome_visualizzato="Finitura X"))
    s.commit()
    rc.ricarica_da_database(s)          # registro singleton: stato pulito
    s.close()

    d = GestioneColori(factory)
    qtbot.addWidget(d)
    assert d.tabella.rowCount() == 3
    assert "1 non definiti" in d.contatori.text()
    assert "1 suggeriti" in d.contatori.text()
    assert "1 confermati" in d.contatori.text()

    # filtro «Suggeriti» -> solo RAL1013
    d.filtro.setCurrentIndex(d.filtro.findData(rc.SUGGERITO))
    assert d.tabella.rowCount() == 1
    assert d.tabella.item(0, 1).text() == "RAL1013"

    # ricerca per nome
    d.filtro.setCurrentIndex(0)
    d.cerca.setText("bianco perla")
    assert d.tabella.rowCount() == 1
    assert d.tabella.item(0, 1).text() == "RAL1013"

    # «Conferma suggerito» salva il suggerimento (RAL1013 -> #E3D9C6)
    d.cerca.clear()
    d.tabella.selectRow(2)                                   # ordine: AN007, NERO, RAL1013
    assert d.tabella.item(2, 1).text() == "RAL1013"
    assert d._btn_conferma.isEnabled()
    d.tabella.selectRow(1)
    assert not d._btn_conferma.isEnabled()                   # NERO già confermato
    d.tabella.selectRow(2)
    d._azione_conferma()
    s = factory()
    assert s.get(Colore, 2).colore_hex == "#E3D9C6"
    s.close()
    assert "2 confermati" in d.contatori.text()
