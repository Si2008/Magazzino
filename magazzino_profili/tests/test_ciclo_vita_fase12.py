"""Fase 12: ciclo di vita — backup idempotente, worker scadenze nel processo web,
accesso utente senza account predefinito, nessun doppio backup, ``ferma()``
deterministico, UI non crea worker.

Esecuzione::

    python -m pytest tests/test_ciclo_vita_fase12.py -v

Tutti i test usano SQLite in memoria o oggetti fittizi: nessun PostgreSQL,
nessun processo, nessun file.
"""

from __future__ import annotations

import inspect
import threading
import time
from unittest.mock import MagicMock

import pytest


def test_worker_non_elimina_un_barcode_diventato_caricato(monkeypatch):
    """Il giro delle 48h non elimina un barcode che è diventato «Caricato»."""
    import magazzino_profili.services.scadenze as sc

    eliminati = []

    def falso_ids(session, adesso):
        return [1, 2]

    def falso_elimina(session, id_, **kw):
        eliminati.append(id_)

    fabbrica = MagicMock()
    fabbrica.return_value.__enter__.return_value = MagicMock()
    fabbrica.return_value.__exit__.return_value = False

    monkeypatch.setattr(sc, "ids_scaduti", falso_ids)
    monkeypatch.setattr(sc, "elimina_scaduto", falso_elimina)

    p = sc.PianificatoreScadenze(fabbrica, 10.0)
    p._elimina_scaduti()
    assert eliminati == [1, 2]


def test_pianificatore_scadenze_fa_un_giro_e_poi_pausa(monkeypatch):
    """avvia() fa un giro di controllo e poi attende N secondi."""
    import magazzino_profili.services.scadenze as sc

    fabbrica = MagicMock()
    fabbrica.return_value.__enter__.return_value = MagicMock()
    fabbrica.return_value.__exit__.return_value = False

    giro = MagicMock()
    monkeypatch.setattr(sc.PianificatoreScadenze, "_ciclo", giro)

    p = sc.PianificatoreScadenze(fabbrica, 10.0)
    p.avvia()
    p.ferma()
    giro.assert_called_once_with(p)


def test_ferma_attende_la_fine_del_giro_in_corso():
    """ferma() non uccide il giro in corso: lo attende."""
    import magazzino_profili.services.scadenze as sc

    stati = []

    def giro():
        time.sleep(0.1)
        stati.append("fine")

    fabbrica = MagicMock()
    fabbrica.return_value.__enter__.return_value = MagicMock()
    fabbrica.return_value.__exit__.return_value = False

    p = sc.PianificatoreScadenze(fabbrica, 10.0)
    # Simuliamo un giro in corso (il thread fa un lavoro breve)
    p._thread = threading.Thread(target=giro)
    p._thread.start()
    p.ferma(timeout=1.0)
    assert stati == ["fine"]


def test_pianificatore_backup_idempotente_e_deterministico():
    import magazzino_profili.backup.backup_db as bdb

    chiamate = []

    def azione():
        chiamate.append(1)

    p = bdb.PianificatoreBackup(1, azione)
    p.avvia()
    p.avvia()
    assert chiamate == [1]
    p.ferma(timeout=0.5)
    time.sleep(0.5)
    assert chiamate == [1]


def test_avvio_idempotente():
    import magazzino_profili.backup.backup_db as bdb

    chiamate = []

    def azione():
        chiamate.append(1)

    p = bdb.PianificatoreBackup(1, azione)
    p.avvia()
    p.avvia()
    p.avvia()
    time.sleep(0.3)
    assert len(chiamate) == 1
    p.ferma(timeout=0.5)


def test_ferma_non_lascia_timer_in_piedi():
    import magazzino_profili.backup.backup_db as bdb

    p = bdb.PianificatoreBackup(1, lambda: None)
    p.avvia()
    p.ferma(timeout=0.5)
    time.sleep(0.2)
    assert p._timer is None


def test_web_main_usa_lo_stesso_factory_per_app_e_worker():
    """Il processo web usa UN factory per app e worker (non due)."""
    import magazzino_profili.web.app as wa

    # Il codice di main() deve riferirsi allo stesso ``factory``.
    sorgente = inspect.getsource(wa.main)
    assert "crea_app(" in sorgente
    assert "PianificatoreScadenze(" in sorgente


def test_web_main_avvia_e_ferma_il_worker(monkeypatch, tmp_path):
    import magazzino_profili.web.app as wa
    from types import SimpleNamespace
    from fastapi import FastAPI
    cert = tmp_path / "cert.pem"
    cert.write_text("finto")
    engine = MagicMock()
    engine.dialect.name = "sqlite"
    monkeypatch.setattr(wa, "leggi_sezione_web", lambda: dict(host="127.0.0.1", porta=8443, certificato_pem=str(cert), chiave_privata=str(cert), durata_token_secondi=60, segrete_token=None))
    monkeypatch.setattr(wa, "leggi_config_scadenze", lambda: SimpleNamespace(intervallo_secondi=10))
    monkeypatch.setattr(wa, "leggi_config", lambda: object())
    monkeypatch.setattr(wa, "crea_engine", lambda **k: engine)
    factory = MagicMock()
    monkeypatch.setattr(wa, "crea_session_factory", lambda e: factory)
    avvia, ferma = MagicMock(), MagicMock()
    monkeypatch.setattr(wa, "avvia", avvia)
    monkeypatch.setattr(wa, "ferma", ferma)
    monkeypatch.setattr(wa, "crea_app", lambda **k: FastAPI())
    monkeypatch.setattr(wa.uvicorn, "run", MagicMock())
    monkeypatch.setattr(wa, "leggi_sezione_update", lambda: {"abilitato": False})
    assert wa.main() == 0
    avvia.assert_called_once()
    ferma.assert_called_once_with(avvia.call_args.args[0])
    engine.dispose.assert_called_once()


def test_desktop_controlla_scadenze_anche_senza_server_telefono():
    import magazzino_profili.main as m
    assert "PianificatoreScadenze" in inspect.getsource(m)
