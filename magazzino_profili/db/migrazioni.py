"""Applicazione delle migrazioni SQL.

Le migrazioni sono file ``*.sql`` nella cartella ``migrations/``
alla radice del progetto, applicati in ordine lessicografico dei
nomi (prefisso numerico). I file già applicati vengono tracciati
nella tabella ``migrazioni_applicate`` e non vengono rieseguiti.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine

CARTELLA_MIGRAZIONI = Path(__file__).resolve().parents[2] / "migrations"


def applica_migrazioni(engine: Engine) -> list[str]:
    """Applica le migrazioni non ancora eseguite e restituisce i nomi
    dei file applicati durante questa chiamata (vuoto se nessuna)."""
    if not CARTELLA_MIGRAZIONI.is_dir():
        return []

    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS migrazioni_applicate "
                "(nome TEXT PRIMARY KEY)"
            )
        )
        gia_applicate = {
            riga[0] for riga in conn.execute(text("SELECT nome FROM migrazioni_applicate"))
        }

    eseguite: list[str] = []
    for file in sorted(CARTELLA_MIGRAZIONI.glob("*.sql")):
        if file.name in gia_applicate:
            continue
        sql = file.read_text(encoding="utf-8")
        # Le migrazioni sono composte da istruzioni semplici separate da ';'.
        istruzioni = [s.strip() for s in sql.split(";") if s.strip()]
        with engine.begin() as conn:
            if conn.dialect.name == "postgresql":
                # Due avvii simultanei: il secondo attende il lock transazionale
                # e poi trova la migrazione già registrata, quindi non la riesegue
                # (senza il blocco falliva con IntegrityError su migrazioni_applicate).
                conn.execute(text("SELECT pg_advisory_xact_lock(727001)"))
                if conn.execute(
                    text("SELECT 1 FROM migrazioni_applicate WHERE nome = :nome"),
                    {"nome": file.name},
                ).first():
                    continue
            for istruzione in istruzioni:
                conn.execute(text(istruzione))
            conn.execute(
                text("INSERT INTO migrazioni_applicate (nome) VALUES (:nome)"),
                {"nome": file.name},
            )
        eseguite.append(file.name)

    return eseguite
