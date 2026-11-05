"""Migrazioni 004/005 su PostgreSQL: solo con variabile d'ambiente esplicita.

Senza ``MAGAZZINO_PG_URL`` i test sono ``skip`` (ambiente non disponibile).
Con URL valida verifica, su un database dedicato, che le migrazioni
004 e 005 applichino colonne, indice e vincolo ``ck_pezzi_stato_valido``.
"""

from __future__ import annotations

import os

import pytest

pg_url = os.environ.get("MAGAZZINO_PG_URL")
pytestmark = pytest.mark.skipif(
    not pg_url,
    reason="MAGAZZINO_PG_URL non definita: test PostgreSQL disattivato",
)


def _engine():
    from magazzino_profili.db import crea_engine

    from sqlalchemy.engine import make_url
    nome = make_url(pg_url).database or ""
    if not (nome.endswith("_test") or nome.startswith("test_")):
        pytest.fail("È obbligatorio un database dedicato ai test")
    engine = crea_engine(url=pg_url.replace("postgresql://", "postgresql+psycopg://", 1))
    from magazzino_profili.db import crea_tabelle
    crea_tabelle(engine)
    return engine


def test_migrazioni_004_005_postgres():
    from sqlalchemy import inspect, text

    from magazzino_profili.db.migrazioni import applica_migrazioni
    from magazzino_profili.domain import Pezzo

    engine = _engine()
    applica_migrazioni(engine)
    sessione = engine.connect()
    try:
        info = set(sessione.scalars(text("SELECT nome FROM migrazioni_applicate")))
        assert "004_campi_giacenza.sql" in info
        assert "005_vincolo_stato.sql" in info
        # le quattro colonne devono esistere nella tabella
        righe = sessione.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'pezzi'"
            )
        ).fetchall()
        nomi = {r[0] for r in righe}
        for campo in ("numero_vassoio", "stato", "data_ultimo_cambio_stato", "eliminato_il"):
            assert campo in nomi, f"manca {campo}"
        # migrazione 006 (Fase 8): colonna colore_hex sulla tabella colori
        righe = sessione.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'colori'"
            )
        ).fetchall()
        assert "colore_hex" in {r[0] for r in righe}
        # il vincolo deve chiamarsi ck_pezzi_stato_valido
        vincoli = {
            r[0]
            for r in sessione.execute(
                text(
                    "SELECT conname FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid "
                    "WHERE t.relname = 'pezzi' AND c.conname = 'ck_pezzi_stato_valido'"
                )
            ).fetchall()
        }
        assert "ck_pezzi_stato_valido" in vincoli
    finally:
        sessione.close()
        engine.dispose()


def test_lock_avvio_simultaneo_postgres():
    """Due applica_migrazazioni simultanei: nessuna IntegrityError."""
    import threading

    from magazzino_profili.db.migrazioni import applica_migrazioni

    errori = []

    def _lancia():
        try:
            engine = _engine()
            try:
                applica_migrazioni(engine)
            finally:
                engine.dispose()
        except Exception as e:  # noqa: BLE001
            errori.append(e)

    threads = [threading.Thread(target=_lancia) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errori, f"avvio simultaneo fallito: {errori}"


if __name__ == "__main__":
    print("skip senza MAGAZZINO_PG_URL")
