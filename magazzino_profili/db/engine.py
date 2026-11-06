"""Creazione dell'engine SQLAlchemy e del factory di sessioni."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ..domain import Base
from .config import ConfigurazioneDatabase, leggi_config


def crea_engine(
    url: str | None = None,
    config: ConfigurazioneDatabase | None = None,
) -> Engine:
    """Crea l'engine di connessione.

    L'URL è preso, in ordine di priorità:
    1. dal parametro ``url`` (es. per i test);
    2. dal parametro ``config``;
    3. da ``config.toml`` tramite :func:`leggi_config`.
    """
    if url is None:
        if config is None:
            config = leggi_config()
        url = config.database_url
    return create_engine(
        url,
        pool_pre_ping=True,
        connect_args=_parametri_connessione(url),
    )


def _parametri_connessione(url: str) -> dict:
    """Timeout short for PostgreSQL: if the server is not started it fails quickly."""
    if str(url).startswith("postgres"):
        return {"connect_timeout": 5}
    return {}


def crea_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Factory di sessioni con commit esplicito e oggetti non 'scaduti'."""
    return sessionmaker(bind=engine, expire_on_commit=False)


def crea_tabelle(engine: Engine) -> None:
    """Crea tutte le tabelle del dominio (solo per setup/ambiente di dev)."""
    from sqlalchemy import text
    with engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            conn.execute(text("SELECT pg_advisory_xact_lock(727001)"))
        Base.metadata.create_all(conn)
