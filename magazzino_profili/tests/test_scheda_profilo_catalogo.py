"""Fase 7 — SchedaProfilo: proposta immagine, guardie e salvataggio."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select

from magazzino_profili.db import crea_session_factory
from magazzino_profili.domain import Base, Profilo
from magazzino_profili.services import anagrafica
from magazzino_profili.services.catalogo_immagini import CatalogoImmagini
from magazzino_profili.services.proposta_immagine import StatoImmagine
from magazzino_profili.ui.scheda_profilo import SchedaProfilo

FIRMA = b"\x89PNG\r\n\x1a\n"


def _png_vero(cartella, nome: str):
    """PNG reale, decodificabile da Qt (Pillow)."""
    from PIL import Image

    f = cartella / nome
    Image.new("RGB", (8, 8), (200, 30, 30)).save(f, format="PNG")
    return f


@pytest.fixture()
def factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return crea_session_factory(engine)


@pytest.fixture()
def scheda(qapp, factory, catalogo_isolato):
    catalogo_isolato.mkdir(exist_ok=True)
    _png_vero(catalogo_isolato, "AZ2001.png")
    _png_vero(catalogo_isolato, "ZZ9.png")
    w = SchedaProfilo(factory, catalogo=CatalogoImmagini(catalogo_isolato))
    yield w
    w.close()


def _compila_nuovo(w: SchedaProfilo, codice="AB99"):
    w._nuovo()
    w.codice.setText(codice)
    w.descrizione.setText("Descrizione test")
    w.lunghezza.setText("6000")


def test_nuovo_profilo_mostra_proposta(scheda, catalogo_isolato):
    scheda._nuovo()
    assert scheda._proposta.stato is StatoImmagine.NESSUNA
    scheda.codice.setText("az 2001")
    assert scheda._proposta.stato is StatoImmagine.PROPOSTA
    assert scheda._proposta.percorso == catalogo_isolato / "AZ2001.png"
    assert scheda._immagine_locale == str(catalogo_isolato / "AZ2001.png")
    assert not scheda._nota_catalogo.isHidden()
    assert "AZ2001.png" in scheda._nota_catalogo.text()
    assert not scheda._anteprima.pixmap().isNull()


def test_nuovo_profilo_codice_assente_nessuna_immagine(scheda):
    scheda._nuovo()
    scheda.codice.setText("ZZ999")
    assert scheda._proposta.stato is StatoImmagine.NESSUNA
    assert scheda._immagine_locale is None
    assert scheda._nota_catalogo.isHidden()


def test_profilo_esistente_mai_proposta(scheda, catalogo_isolato):
    # profilo già in anagrafica, immagine salvata
    s = scheda._factory()
    p = anagrafica.crea_profilo(s, "AZ2001", "Esistente", 1.0, 6000, "t")
    s.close()
    scheda._rinfresca_tabella()
    for i in range(scheda._tabella.rowCount()):
        if scheda._righe[i][1] == "AZ2001":
            scheda._tabella.selectRow(i)
            break
    assert scheda._profilo_id is not None
    assert scheda._proposta.stato is StatoImmagine.NESSUNA
    assert scheda._nota_catalogo.isHidden()


def test_manuale_non_sovrascritto_dal_cambiamento_codice(scheda, catalogo_isolato):
    scheda._nuovo()
    manuale = _png_vero(catalogo_isolato, "mia.png")
    # stesso percorso dello stato che _importa_immagine imposterebbe
    scheda._immagine_locale = str(manuale)
    scheda._proposta.su_importazione_manuale(manuale)
    assert scheda._proposta.stato is StatoImmagine.MANUALE
    scheda.codice.setText("az 2001")
    assert scheda._proposta.stato is StatoImmagine.MANUALE
    assert scheda._immagine_locale == str(manuale)


def test_rimossa_niente_riproposta_finche_codice_non_cambia(scheda, catalogo_isolato):
    scheda._nuovo()
    scheda.codice.setText("az 2001")
    assert scheda._proposta.stato is StatoImmagine.PROPOSTA
    scheda._rimuovi_immagine()  # nuovo profilo + PROPOSTA: nessun dialogo
    assert scheda._proposta.stato is StatoImmagine.RIMOSSA
    assert scheda._immagine_locale is None
    assert scheda._nota_catalogo.isHidden()
    scheda.codice.setText("az2001")  # stessa chiave normalizzata
    assert scheda._proposta.stato is StatoImmagine.RIMOSSA
    scheda.codice.setText("zz9")  # codice diverso: nuova ricerca
    assert scheda._proposta.stato is StatoImmagine.PROPOSTA


def test_pulsante_nuovo_azzera_stato(scheda, catalogo_isolato):
    scheda._nuovo()
    scheda.codice.setText("az 2001")
    assert scheda._proposta.stato is StatoImmagine.PROPOSTA
    scheda._nuovo()
    assert scheda._proposta.stato is StatoImmagine.NESSUNA
    assert scheda._immagine_locale is None
    assert scheda._nota_catalogo.isHidden()
    assert scheda.codice.text() == ""


def test_salva_file_sparito_nessun_profilo(scheda, catalogo_isolato, tmp_path):
    scheda._nuovo()
    scheda.codice.setText("AB99")
    scheda.descrizione.setText("Descrizione test")
    scheda.lunghezza.setText("6000")
    sparito = _png_vero(tmp_path, "sparito.png")
    scheda._immagine_locale = str(sparito)
    sparito.unlink()  # il file non c'è più

    scheda.salva_profilo()

    assert scheda._factory().scalar(
        select(func.count()).select_from(Profilo)
    ) == 0
    assert scheda.messaggio.text() != ""


def test_salva_con_proposta_crea_profilo_con_immagine(scheda, catalogo_isolato):
    # la copia finisce nella cartella di default "immagini_sezioni" (relativa alla CWD): la puliamo
    Destinazione = Path("immagini_sezioni")
    prima = set(Destinazione.iterdir()) if Destinazione.is_dir() else set()

    scheda._nuovo()
    scheda.codice.setText("az 2001")
    scheda.descrizione.setText("Descrizione test")
    scheda.lunghezza.setText("6000")
    scheda.salva_profilo()

    prof = scheda._factory().scalar(
        select(Profilo).where(Profilo.codice == "AZ2001")
    )
    assert prof is not None
    assert prof.immagine_sezione is not None
    assert Path(prof.immagine_sezione).is_file()

    # pulizia: rimuoviamo solo i file creati da questo test
    dopo = set(Destinazione.iterdir())
    for nuovo in dopo - prima:
        nuovo.unlink()
