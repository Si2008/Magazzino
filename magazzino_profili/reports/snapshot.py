"""Lettura coerente delle esportazioni senza alterare la sessione chiamante."""
from contextlib import contextmanager
from sqlalchemy.orm import Session


@contextmanager
def sessione_snapshot(sessione):
    bind = sessione.get_bind()
    if bind.dialect.name != "postgresql":
        yield sessione
        return
    # Engine con opzioni per questa sola connessione: nessun cambio globale del pool.
    engine = bind.engine if hasattr(bind, "engine") else bind
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn:
        with conn.begin():
            conn.exec_driver_sql("SET TRANSACTION READ ONLY")
            with Session(bind=conn) as lettura:
                yield lettura
