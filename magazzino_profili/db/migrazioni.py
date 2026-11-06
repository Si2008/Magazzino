"""Applicazione delle migrazioni SQL.

Le migrazioni sono file ``*.sql`` nella cartella ``migrations/``
alla radice del progetto, applicati in ordine lessicografico dei
nomi (prefisso numerico). I file già applicati vengono tracciati
nella tabella ``migrazioni_applicate`` e non vengono rieseguiti.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from sqlalchemy import inspect
import hashlib
from sqlalchemy.engine import Engine

CARTELLA_MIGRAZIONI = Path(__file__).resolve().parents[2] / "migrations"


def migrazioni_pendenti(engine):
    if not CARTELLA_MIGRAZIONI.is_dir():
        raise FileNotFoundError("Cartella migrations assente: installazione incompleta")
    applicate = set()
    if "migrazioni_applicate" in inspect(engine).get_table_names():
        with engine.connect() as conn:
            applicate = set(conn.scalars(text("SELECT nome FROM migrazioni_applicate")))
    return [p for p in sorted(CARTELLA_MIGRAZIONI.glob("*.sql")) if p.name not in applicate]


def separa_istruzioni(sql):
    """Separatori SQL fuori da stringhe, commenti e blocchi dollar-quoted."""
    import re
    righe, inizio, i, lunghezza = [], 0, 0, len(sql)
    while i < lunghezza:
        if sql.startswith("--", i):
            fine = sql.find("\n", i + 2)
            i = lunghezza if fine < 0 else fine + 1
        elif sql.startswith("/*", i):
            profondita = 1
            i += 2
            while i < lunghezza and profondita:
                if sql.startswith("/*", i): profondita += 1; i += 2
                elif sql.startswith("*/", i): profondita -= 1; i += 2
                else: i += 1
            if profondita: raise ValueError("Commento SQL non terminato")
        elif sql[i] in ("'", '"'):
            delimitatore = sql[i]
            i += 1
            while i < lunghezza:
                if sql[i] == delimitatore:
                    if i + 1 < lunghezza and sql[i+1] == delimitatore: i += 2; continue
                    i += 1
                    break
                if sql[i] == "\\" and delimitatore == "'": i += 2
                else: i += 1
            else: raise ValueError("Stringa SQL non terminata")
        elif sql[i] == "$" and (tag := re.match(r"\$(?:[A-Za-z_][A-Za-z0-9_]*)?\$", sql[i:])):
            delimitatore = tag.group()
            fine = sql.find(delimitatore, i + len(delimitatore))
            if fine < 0: raise ValueError("Blocco SQL dollar-quoted non terminato")
            i = fine + len(delimitatore)
        elif sql[i] == ";":
            if sql[inizio:i].strip(): righe.append(sql[inizio:i].strip())
            i += 1; inizio = i
        else: i += 1
    if sql[inizio:].strip(): righe.append(sql[inizio:].strip())
    return righe


def schema_atteso():
    if not CARTELLA_MIGRAZIONI.is_dir():
        raise FileNotFoundError("Cartella migrations assente: installazione incompleta")
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(CARTELLA_MIGRAZIONI.glob("*.sql"))}


def versione_schema_attesa():
    return max((int(n.split("_", 1)[0]) for n in schema_atteso()), default=0)


def applica_migrazioni(engine: Engine, *, crea_schema=False) -> list[str]:
    """Lotto atomico: lock, schema, DDL e registro sono annullati insieme se fallisce.

    Il backup verificato viene creato dal chiamante prima del lotto. Il ripristino
    automatico usa il rollback transazionale, senza DROP/pg_restore --clean sui dati.
    """
    attese = schema_atteso()
    from ..percorsi_installazione import installata
    import sys
    if installata() and getattr(sys, "frozen", False):
        import json
        from .. import __version__
        from ..distribuzione import APP_ID
        manifesto = json.loads((Path(sys.executable).parent / "installazione.json").read_text(encoding="utf-8"))
        if (manifesto.get("app_id") != APP_ID or manifesto.get("versione") != __version__ or
                manifesto.get("migrazioni") != attese or manifesto.get("schema") != versione_schema_attesa()):
            raise RuntimeError("Pacchetto installato incompleto o incoerente: migrazione rifiutata")
    contenuti = {n: separa_istruzioni((CARTELLA_MIGRAZIONI/n).read_text(encoding="utf-8")) for n in attese}
    eseguite = []
    with engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            conn.execute(text("SELECT pg_advisory_xact_lock(727001)"))
        elif conn.dialect.name == "sqlite" and not conn.connection.driver_connection.in_transaction:
            # SQLite in modalita legacy non apre da solo una transazione per DDL.
            conn.exec_driver_sql("BEGIN IMMEDIATE")
        conn.execute(text("CREATE TABLE IF NOT EXISTS migrazioni_applicate (nome TEXT PRIMARY KEY)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS migrazioni_checksum (nome TEXT PRIMARY KEY, sha256 VARCHAR(64) NOT NULL)"))
        applicate = set(conn.scalars(text("SELECT nome FROM migrazioni_applicate")))
        estranee = applicate - set(attese)
        if estranee:
            raise RuntimeError("Schema database piu recente o incompatibile con questa versione: " + ", ".join(sorted(estranee)))
        for nome, sha in attese.items():
            nota = conn.scalar(text("SELECT sha256 FROM migrazioni_checksum WHERE nome=:nome"), {"nome":nome})
            if nota is not None and nota != sha:
                raise RuntimeError(f"Migrazione gia applicata modificata: {nome}")
        if crea_schema:
            from ..domain import Base
            Base.metadata.create_all(conn)
        for nome, sha in attese.items():
            if nome not in applicate:
                for istruzione in contenuti[nome]: conn.execute(text(istruzione))
                conn.execute(text("INSERT INTO migrazioni_applicate (nome) VALUES (:nome)"), {"nome":nome})
                eseguite.append(nome)
            conn.execute(text("INSERT INTO migrazioni_checksum (nome,sha256) VALUES (:nome,:sha) ON CONFLICT (nome) DO NOTHING"), {"nome":nome,"sha":sha})
    return eseguite
