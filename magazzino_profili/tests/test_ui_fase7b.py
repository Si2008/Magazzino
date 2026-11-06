"""Fase 7B: telefono come lettore barcode (UI + controllo polling)."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QLabel
from sqlalchemy import create_engine, select

from magazzino_profili.db import crea_session_factory
from magazzino_profili.domain import Base, Colore, Pezzo, Profilo
from magazzino_profili.sicurezza import Ruolo
from magazzino_profili.services import telefono
from magazzino_profili.ui.collega_telefono import (
    ControlloTelefono,
    DialogoTelefono,
    aggiorna_pulsante_telefono,
)
from magazzino_profili.ui.scheda_carico import SchedaCarico
from magazzino_profili.ui.scheda_scarico import SchedaScarico


@pytest.fixture()
def factory():
    """Factory su SQLite in memoria (condivisione SingletonThreadPool)."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return crea_session_factory(engine)


def _pezzo(factory) -> None:
    s = factory()
    try:
        profilo = Profilo(codice="AB12", descrizione="Busta", peso_kg_per_metro=1.2, lunghezza_standard_mm=6000)
        colore = Colore(codice_normalizzato="AN007", nome_visualizzato="Antracite")
        s.add_all([profilo, colore])
        s.flush()
        s.add(
            Pezzo(
                profilo=profilo,
                colore=colore,
                lunghezza_mm=6000,
                quantita=5,
                barcode="AB12-AN007-6000",
            )
        )
        s.commit()
    finally:
        s.close()


# ------------------------------------------------------------------ ControlloTelefono
def test_controllo_avvia_scarta_la_coda_poi_riceve_le_nuove(factory, qapp) -> None:
    # due scansioni "vecchie" già in coda
    for codice in ("VECCHIO-1", "VECCHIO-2"):
        s = factory()
        try:
            telefono.registra_scansione(s, codice, "maria")
        finally:
            s.close()

    c = ControlloTelefono(factory)
    ricevute: list[str] = []
    c.scansione.connect(lambda b: ricevute.append(b))
    assert ricevute == []
    c.avvia()
    c.controlla()  # giro 1: scarta le vecchie, non le emette
    assert ricevute == []

    # ora il telefono invia una scansione nuova
    s = factory()
    try:
        telefono.registra_scansione(s, "NUOVA-1", "maria")
    finally:
        s.close()
    c.controlla()  # giro 2: la riceve
    assert ricevute == ["NUOVA-1"]
    c.ferma()


def test_controllo_stato_collegato_e_ferma(factory, qapp) -> None:
    c = ControlloTelefono(factory)
    eventi: list[bool] = []
    c.stato_cambiato.connect(lambda v: eventi.append(v))
    assert c.collegato is False

    c.avvia()
    assert c.attivo is True
    c.controlla()  # nessun ping ancora
    assert c.collegato is False

    # il telefono pinga
    s = factory()
    try:
        telefono.registra_ping(s)
    finally:
        s.close()
    c.controlla()
    assert c.collegato is True
    assert eventi[-1] is True

    # e poi si ferma
    c.ferma()
    assert c.attivo is False
    assert c.collegato is False
    assert eventi[-1] is False


# ------------------------------------------------------------------ schede
def test_scarico_ricevi_scansione_compila_e_chiede_causale(factory, qapp) -> None:
    _pezzo(factory)
    scheda = SchedaScarico(factory, "maria")
    assert scheda.causale.text().strip() == ""
    assert scheda.anteprima.text() == ""

    scheda.ricevi_scansione("ab12-an007-6000")

    assert scheda.barcode.text() == "AB12-AN007-6000"
    assert "giacenza: 5 pz" in scheda.anteprima.text()
    # isVisible() sarebbe False in test (finestre mai mostrate): controllo il testo
    assert "causale" in scheda.messaggio.text().lower()
    # consuma i timer programmati da mostra() mentre il widget è ancora vivo
    qapp.processEvents()


def test_carico_ricevi_scansione_compila_il_campo(factory, qapp) -> None:
    _pezzo(factory)
    scheda = SchedaCarico(factory, "maria")
    assert scheda.barcode.text() == ""
    scheda.ricevi_scansione("ab12-an007-6000")
    assert scheda.barcode.text() == "AB12-AN007-6000"


def test_aggiorna_pulsante_telefono(factory, qapp) -> None:
    _pezzo(factory)
    scheda = SchedaScarico(factory, "maria")
    assert scheda.btn_telefono.text() == "Collega telefono"
    assert scheda.btn_telefono.property("telefono") == "off"

    aggiorna_pulsante_telefono(scheda.btn_telefono, True)
    assert scheda.btn_telefono.text() == "Telefono collegato"
    assert scheda.btn_telefono.property("telefono") == "on"

    aggiorna_pulsante_telefono(scheda.btn_telefono, False)
    assert scheda.btn_telefono.text() == "Collega telefono"


# ------------------------------------------------------------------ finestra principale
def test_finestra_consegna_la_scansione_solo_sulla_scheda_attiva(factory, qapp, monkeypatch) -> None:
    from magazzino_profili.ui.finestra_principale import FinestraPrincipale

    _pezzo(factory)
    finestra = FinestraPrincipale(factory, Ruolo.AMMINISTRATORE, "test")
    ricevute: list[str] = []
    monkeypatch.setattr(
        "magazzino_profili.ui.scheda_scarico.SchedaScarico.ricevi_scansione",
        lambda self, b: ricevute.append(b),
    )
    toasts: list[str] = []
    monkeypatch.setattr(finestra, "mostra_toast", lambda m, t: toasts.append(m))

    # scheda attiva: Scarico -> consegna
    finestra._tab.setCurrentWidget(finestra.scheda_scarico)
    assert finestra._tab.currentWidget() is finestra.scheda_scarico
    finestra._su_scansione_telefono("AB12-AN007-6000")
    assert ricevute == ["AB12-AN007-6000"]
    assert toasts == []

    # scheda attiva: Inventario -> non consegna, avvisa
    finestra._tab.setCurrentWidget(finestra.scheda_inventario)
    assert finestra._tab.currentWidget() is finestra.scheda_inventario
    ricevute.clear()
    finestra._su_scansione_telefono("AB12-AN007-6000")
    assert ricevute == []
    assert len(toasts) == 1
    assert "carico o scarico" in toasts[0].lower()

    # i pulsanti sono aggiornati allo stato del controllo
    assert finestra.scheda_carico.btn_telefono.property("telefono") == "off"
    assert finestra.scheda_scarico.btn_telefono.property("telefono") == "off"
    finestra._controllo_telefono.ferma()


def test_dialogo_telefono_stati(factory, qapp) -> None:
    c = ControlloTelefono(factory)
    # senza indirizzo: messaggio di configurazione
    d1 = DialogoTelefono(c, None)
    testo = " ".join(w.text() for w in d1.findChildren(QLabel))
    assert "Inserisci l'indirizzo HTTPS" in testo
    assert "HTTPS" in testo
    d1.close()

    # con indirizzo: QR presente + testo dell'indirizzo
    d2 = DialogoTelefono(c, "https://magazzino.esempio.it:8443/")
    con_qr = [w for w in d2.findChildren(QLabel) if w.pixmap() is not None and not w.pixmap().isNull()]
    assert con_qr, "il dialogo senza QR non mostra nessun pixmap"
    pixmap = con_qr[0].pixmap()
    assert pixmap.width() > 10 and pixmap.height() > 10
    assert any("magazzino.esempio.it" in (w.text() or "") for w in d2.findChildren(QLabel))
    d2.close()
