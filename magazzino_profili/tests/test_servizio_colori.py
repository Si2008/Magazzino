"""Fase 8 — ``services.colori``: ``elenco_colori`` e ``imposta_colore_hex``.

``imposta_colore_hex`` apre ``session.begin()`` come gli altri servizi:
OGNI chiamata del test usa una sessione NUOVA da ``factory()`` (mai una
sessione che ha già eseguito query).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from magazzino_profili.domain import Colore
from magazzino_profili.services.colori import elenco_colori, imposta_colore_hex


def _factory(tmp_path: Path, nome_db: str = "servizi.db"):
    from magazzino_profili.db import crea_engine, crea_session_factory, crea_tabelle

    eng = crea_engine(url=f"sqlite:///{tmp_path / nome_db}")
    crea_tabelle(eng)
    return crea_session_factory(eng)


def test_elenco_colori_ordinato(tmp_path: Path) -> None:
    factory = _factory(tmp_path, "elenco.db")
    s = factory()
    s.add(Colore(codice_normalizzato="RAL1013", nome_visualizzato="Bianco perla"))
    s.add(Colore(codice_normalizzato="NERO", nome_visualizzato="Nero"))
    s.commit()
    s.close()

    s = factory()
    righe = elenco_colori(s)
    s.close()
    assert [r.codice_normalizzato for r in righe] == ["NERO", "RAL1013"]


def test_imposta_colore_hex_valido_in_maiuscolo(tmp_path: Path) -> None:
    factory = _factory(tmp_path, "set.db")
    s = factory()
    colore = Colore(codice_normalizzato="NERO", nome_visualizzato="Nero")
    s.add(colore)
    s.commit()
    cid = colore.id
    s.close()

    s = factory()
    assert imposta_colore_hex(s, cid, "#b63a32") == "#B63A32"
    s.close()

    s = factory()
    assert s.get(Colore, cid).colore_hex == "#B63A32"
    s.close()


def test_rimozione_con_none_e_stringa_vuota(tmp_path: Path) -> None:
    factory = _factory(tmp_path, "del.db")
    s = factory()
    colore = Colore(codice_normalizzato="NERO", nome_visualizzato="Nero", colore_hex="#111111")
    s.add(colore)
    s.commit()
    cid = colore.id
    s.close()

    s = factory()
    assert imposta_colore_hex(s, cid, None) is None
    s.close()
    s = factory()
    assert s.get(Colore, cid).colore_hex is None
    s.close()

    s = factory()
    imposta_colore_hex(s, cid, "#222222")
    s.close()
    s = factory()
    assert imposta_colore_hex(s, cid, "") is None          # vuoto = rimozione
    s.close()
    s = factory()
    assert s.get(Colore, cid).colore_hex is None
    s.close()


def test_valore_non_valido_valueerror_senza_modifiche(tmp_path: Path) -> None:
    factory = _factory(tmp_path, "err.db")
    s = factory()
    colore = Colore(codice_normalizzato="NERO", nome_visualizzato="Nero", colore_hex="#111111")
    s.add(colore)
    s.commit()
    cid = colore.id
    s.close()

    s = factory()
    with pytest.raises(ValueError, match="#RRGGBB"):
        imposta_colore_hex(s, cid, "blu scuro")
    s.close()

    s = factory()
    assert s.get(Colore, cid).colore_hex == "#111111"     # invariato
    s.close()


def test_colore_inesistente_lookuperror(tmp_path: Path) -> None:
    factory = _factory(tmp_path, "no.db")
    s = factory()
    with pytest.raises(LookupError):
        imposta_colore_hex(s, 9999, "#111111")
    s.close()
