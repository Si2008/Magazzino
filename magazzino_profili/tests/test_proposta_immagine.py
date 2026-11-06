"""Fase 7 — GestoreProposta: transizioni di stato (logica pura)."""

from __future__ import annotations

from pathlib import Path

from magazzino_profili.services.catalogo_immagini import CatalogoImmagini
from magazzino_profili.services.proposta_immagine import (
    GestoreProposta,
    StatoImmagine,
)

FIRMA = b"\x89PNG\r\n\x1a\n"


class _CatalogoContato(CatalogoImmagini):
    def __init__(self, cartella):
        super().__init__(cartella)
        self.chiamate = 0

    def trova(self, codice):
        self.chiamate += 1
        return super().trova(codice)


def _prepara(cartella: Path) -> None:
    (cartella / "az2001.png").write_bytes(FIRMA + b"dati")
    (cartella / "zz9.png").write_bytes(FIRMA + b"dati")


def test_proposta_trovata(catalogo_isolato: Path):
    _prepara(catalogo_isolato)
    g = GestoreProposta(CatalogoImmagini(catalogo_isolato))
    g.su_codice_cambiato("az 2001")
    assert g.stato is StatoImmagine.PROPOSTA
    assert g.percorso is not None and g.percorso.name == "az2001.png"


def test_nessuna_se_assente(catalogo_isolato: Path):
    g = GestoreProposta(CatalogoImmagini(catalogo_isolato))
    g.su_codice_cambiato("zz999")
    assert g.stato is StatoImmagine.NESSUNA and g.percorso is None


def test_codice_vuoto_non_chiamata_catalogo(catalogo_isolato: Path):
    cat = _CatalogoContato(catalogo_isolato)
    g = GestoreProposta(cat)
    for testo in ("", "   ", None):  # type: ignore[arg-type]
        g.su_codice_cambiato(testo)
        assert g.stato is StatoImmagine.NESSUNA
    assert cat.chiamate == 0


def test_manuale_non_sovrascritto(catalogo_isolato: Path):
    _prepara(catalogo_isolato)
    g = GestoreProposta(CatalogoImmagini(catalogo_isolato))
    manuale = catalogo_isolato / "mia.png"
    manuale.write_bytes(FIRMA + b"x")
    g.su_importazione_manuale(manuale)
    assert g.stato is StatoImmagine.MANUALE and g.percorso == manuale
    g.su_codice_cambiato("az 2001")
    assert g.stato is StatoImmagine.MANUALE and g.percorso == manuale


def test_rimossa_niente_riproposta_stesso_codice(catalogo_isolato: Path):
    _prepara(catalogo_isolato)
    g = GestoreProposta(CatalogoImmagini(catalogo_isolato))
    g.su_codice_cambiato("az 2001")
    assert g.stato is StatoImmagine.PROPOSTA
    g.su_rimozione("AZ 2001")
    assert g.stato is StatoImmagine.RIMOSSA and g.percorso is None
    g.su_codice_cambiato("az 2001")  # stessa chiave normalizzata (AZ2001)
    assert g.stato is StatoImmagine.RIMOSSA
    g.su_codice_cambiato("zz9")  # codice diverso: nuova ricerca
    assert g.stato is StatoImmagine.PROPOSTA and g.percorso.name == "zz9.png"


def test_azzera(catalogo_isolato: Path):
    _prepara(catalogo_isolato)
    g = GestoreProposta(CatalogoImmagini(catalogo_isolato))
    g.su_codice_cambiato("az 2001")
    g.azzera()
    assert g.stato is StatoImmagine.NESSUNA and g.percorso is None
