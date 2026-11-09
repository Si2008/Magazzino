"""Fase 8: concorrenza e fusi orari con PostgreSQL di test (MAGAZZINO_TEST_DB_URL, database *_test)."""
import os
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from magazzino_profili.db.config import ErroreConfigurazione, leggi_config
from magazzino_profili.domain import Base, Colore, Pezzo, Profilo
from magazzino_profili.services import (
    PezzoEliminatoError, carica, elimina_scaduti, elimina_scaduto, imposta_stato,
    lista_scaduti_per_eliminazione, scarica,
)

_URL = os.environ.get("MAGAZZINO_TEST_DB_URL", "")
T0 = datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc)


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
    yield e
    Base.metadata.drop_all(e)
    e.dispose()


def _scaricato_a_t0(eng) -> int:
    with Session(eng, expire_on_commit=False) as s:
        pid = carica(s, "AB12", "NERO", 6000, 5, "t", "prova").id
    with Session(eng) as s:
        scarica(s, "AB12-NERO-6000", 5, "t", "Uscita completa")
    # Il clock della prova appartiene alla transizione, non al successivo
    # imposta_stato idempotente (che correttamente non cambia un timestamp).
    with Session(eng) as s, s.begin():
        p = s.get(Pezzo, pid)
        p.stato = None
        p.data_ultimo_cambio_stato = None
    with Session(eng, expire_on_commit=False) as s:
        imposta_stato(s, pid, "Scaricato", now=lambda: T0)
    return pid


def _stato(eng, pid):
    with Session(eng) as s:
        p = s.get(Pezzo, pid)
        return p.stato, p.data_ultimo_cambio_stato, p.eliminato_il


def _blocca_riga(eng, pid) -> Session:
    """Sessione A: riga bloccata, modifica non ancora confermata (commit a carico del test)."""
    a = Session(eng)
    a.begin()
    a.execute(select(Pezzo).where(Pezzo.id == pid).with_for_update()).scalar_one()
    return a


def _in_thread(funzione) -> tuple[threading.Thread, list]:
    esito: list = []

    def corpo() -> None:
        try:
            esito.append(funzione())
        except Exception as errore:  # noqa: BLE001 - serve il tipo esatto
            esito.append(errore)

    t = threading.Thread(target=corpo)
    t.start()
    return t, esito


def test_scadenza_esatta_con_timestamptz_e_clock_con_fuso(eng) -> None:
    pid = _scaricato_a_t0(eng)
    fuso = timezone(timedelta(hours=-5))
    with Session(eng) as s:
        prima = (T0 + timedelta(hours=48) - timedelta(microseconds=1)).astimezone(fuso)
        assert lista_scaduti_per_eliminazione(s, now=lambda: prima) == []
    with Session(eng) as s:
        esatta = (T0 + timedelta(hours=48)).astimezone(fuso)
        assert lista_scaduti_per_eliminazione(s, now=lambda: esatta) == [pid]
    stato, ts, _ = _stato(eng, pid)
    assert stato == "Scaricato" and ts == T0 and ts.utcoffset() is not None  # timestamp con fuso


def test_passaggio_a_caricato_in_corso_la_cancellazione_non_avviene(eng) -> None:
    pid = _scaricato_a_t0(eng)
    a = _blocca_riga(eng, pid)
    a.get(Pezzo, pid).stato = "Caricato"
    a.get(Pezzo, pid).data_ultimo_cambio_stato = T0 + timedelta(hours=49)
    a.flush()
    t, esito = _in_thread(lambda: _elimina(eng, pid, T0 + timedelta(hours=50)))
    try:
        time.sleep(0.7)
        assert esito == []  # il controllo attende la transazione che sta cambiando stato
        a.commit()
    finally:
        a.close()
    t.join(10)
    assert esito == [False]
    stato, _, eliminato = _stato(eng, pid)
    assert (stato, eliminato) == ("Caricato", None)


def test_nuovo_scaricato_in_corso_il_vecchio_timestamp_non_vale_piu(eng) -> None:
    pid = _scaricato_a_t0(eng)
    a = _blocca_riga(eng, pid)
    a.get(Pezzo, pid).data_ultimo_cambio_stato = T0 + timedelta(hours=47)  # nuova transizione a Scaricato
    a.flush()
    t, esito = _in_thread(lambda: _elimina(eng, pid, T0 + timedelta(hours=49)))
    time.sleep(0.7)
    a.commit()
    a.close()
    t.join(10)
    assert esito == [False] and _stato(eng, pid)[2] is None


def test_se_la_cancellazione_vince_il_cambio_di_stato_viene_rifiutato(eng) -> None:
    pid = _scaricato_a_t0(eng)
    assert _elimina(eng, pid, T0 + timedelta(hours=48)) is True
    with Session(eng) as s, pytest.raises(PezzoEliminatoError):
        imposta_stato(s, pid, "Caricato", now=lambda: T0 + timedelta(hours=49))
    assert _stato(eng, pid)[0] == "Scaricato"


def test_due_controlli_contemporanei_eliminano_una_sola_volta(eng) -> None:
    pid = _scaricato_a_t0(eng)
    via = threading.Barrier(2)
    esiti: list = []

    def controllo() -> None:
        via.wait()
        esiti.append(elimina_scaduti(lambda: Session(eng), now=lambda: T0 + timedelta(hours=48)))

    ts = [threading.Thread(target=controllo) for _ in range(2)]
    [t.start() for t in ts]
    [t.join(10) for t in ts]
    assert sorted(esiti) == [0, 1]
    assert _stato(eng, pid)[2] == T0 + timedelta(hours=48)


def test_riavvio_con_nuova_connessione_conserva_la_scadenza(eng) -> None:
    pid = _scaricato_a_t0(eng)
    nuova = create_engine(_URL.replace("postgresql://", "postgresql+psycopg://", 1))
    try:
        assert elimina_scaduti(lambda: Session(nuova), now=lambda: T0 + timedelta(hours=47)) == 0
        assert elimina_scaduti(lambda: Session(nuova), now=lambda: T0 + timedelta(hours=48)) == 1
    finally:
        nuova.dispose()
    assert _stato(eng, pid)[2] is not None


def _elimina(eng, pid, istante) -> bool:
    with Session(eng) as s:
        return elimina_scaduto(s, pid, now=lambda: istante)
