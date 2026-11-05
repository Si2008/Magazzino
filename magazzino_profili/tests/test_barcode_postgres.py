"""Fase 7: concorrenza sul barcode con PostgreSQL di test (MAGAZZINO_TEST_DB_URL, database *_test)."""
import os
import threading
import time

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from magazzino_profili.db.config import ErroreConfigurazione, leggi_config
from magazzino_profili.domain import Base, Colore, Pezzo, Profilo
from magazzino_profili.services import BarcodeDuplicatoError, aggiorna_barcode, carica

_URL = os.environ.get("MAGAZZINO_TEST_DB_URL", "")


def _target_sicuro() -> bool:
    nome = (make_url(_URL).database or "").lower() if _URL else ""
    if not (nome.endswith("_test") or nome.startswith("test_")):
        return False
    try:
        return nome != leggi_config().dbname.lower()
    except ErroreConfigurazione:
        return True


pytestmark = pytest.mark.skipif(not _target_sicuro(), reason="serve MAGAZZINO_TEST_DB_URL verso un database *_test dedicato")


@pytest.fixture()
def eng():
    e = create_engine(_URL.replace("postgresql://", "postgresql+psycopg://", 1), pool_size=6)
    Base.metadata.drop_all(e)
    Base.metadata.create_all(e)
    with Session(e) as s:
        s.add(Profilo(codice="AB12", descrizione="d", peso_kg_per_metro=1.0, lunghezza_standard_mm=6000))
        s.add(Colore(codice_normalizzato="NERO", nome_visualizzato="Nero"))
        s.commit()
        carica(s, "AB12", "NERO", 6000, 5, "t", "prova")
        carica(s, "AB12", "NERO", 3000, 5, "t", "prova")
    yield e
    Base.metadata.drop_all(e)
    e.dispose()


def _ids(eng) -> tuple[int, int]:
    with Session(eng) as s:
        return tuple(s.scalars(select(Pezzo.id).order_by(Pezzo.id)))  # type: ignore[return-value]


def test_gara_sul_vincolo_di_unicita_diventa_barcode_duplicato(eng) -> None:
    """Deterministico: A scrive il barcode e non ha ancora fatto commit; B passa il controllo
    preventivo (non vede la riga non confermata) e si blocca sul vincolo UNIQUE."""
    id1, id2 = _ids(eng)
    a = Session(eng)
    a.begin()
    a.get(Pezzo, id2).barcode = "CONTESO-1"
    a.flush()
    esito: list = []

    def b() -> None:
        with Session(eng) as sessione_b:
            try:
                esito.append(aggiorna_barcode(sessione_b, id1, "contesO-1"))
            except Exception as errore:  # noqa: BLE001 - serve il tipo esatto
                esito.append(errore)

    t = threading.Thread(target=b)
    t.start()
    time.sleep(0.7)  # B è bloccato in attesa dell'indice univoco
    assert esito == []
    a.commit()
    a.close()
    t.join(10)
    assert isinstance(esito[0], BarcodeDuplicatoError)
    assert isinstance(esito[0].__cause__, IntegrityError)  # è passato dalla traduzione, non dal controllo
    with Session(eng) as s:
        assert s.scalar(select(func.count(Pezzo.id)).where(Pezzo.barcode == "CONTESO-1")) == 1
        assert s.get(Pezzo, id1).barcode == "AB12-NERO-6000"


def test_due_sessioni_stesso_barcode_una_sola_vince(eng) -> None:
    id1, id2 = _ids(eng)
    esiti: list = []
    via = threading.Barrier(2)

    def lavora(pezzo_id: int) -> None:
        with Session(eng) as s:
            via.wait()
            try:
                aggiorna_barcode(s, pezzo_id, "GARA-1")
                esiti.append("ok")
            except BarcodeDuplicatoError:
                esiti.append("duplicato")

    ts = [threading.Thread(target=lavora, args=(i,)) for i in (id1, id2)]
    [t.start() for t in ts]
    [t.join(10) for t in ts]
    assert sorted(esiti) == ["duplicato", "ok"], esiti
    with Session(eng) as s:
        assert s.scalar(select(func.count(Pezzo.id)).where(Pezzo.barcode == "GARA-1")) == 1
        assert s.scalar(select(func.count(Pezzo.id))) == 2
