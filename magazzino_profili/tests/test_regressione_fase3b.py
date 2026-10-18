"""Regressione Fase 3b — B-01: ``registra_movimento`` rifiuta i bool.

In Python ``True``/``False`` sono ``int``: senza il controllo esplicito
sui bool, ``registra_movimento(s, pezzo, CARICO, True, "t")`` aggiunge
un pezzo e salva ``quantita=True`` nella traccia contabile.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from magazzino_profili.domain import (
    Base, Colore, Pezzo, Profilo, TipoMovimento, registra_movimento,
)


@pytest.fixture()
def sessione():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture()
def pezzo(sessione):
    p = Profilo(codice="AB12", descrizione="d", peso_kg_per_metro=1.0, lunghezza_standard_mm=6000)
    c = Colore(codice_normalizzato="NERO", nome_visualizzato="Nero")
    sessione.add_all([p, c]); sessione.flush()
    z = Pezzo(profilo=p, colore=c, lunghezza_mm=6000, quantita=5, barcode="AB12-NERO-6000")
    sessione.add(z); sessione.flush()
    return z


@pytest.mark.parametrize("valore", [True, False, 1.0, "3", None, 0, -2])
def test_quantita_non_intera_positiva_rifiutata(sessione, pezzo, valore):
    with pytest.raises(ValueError, match="intero positivo"):
        registra_movimento(sessione, pezzo, TipoMovimento.CARICO, valore, "t")
    assert pezzo.quantita == 5


def test_quantita_intera_positiva_accettata(sessione, pezzo):
    registra_movimento(sessione, pezzo, TipoMovimento.CARICO, 3, "t")
    assert pezzo.quantita == 8
