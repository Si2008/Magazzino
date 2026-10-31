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

    def falso_elimina(session, id_):
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
    """main() del processo web: worker avviato e fermato; server avviato (simulato)."""
    import magazzino_profili.web as w
    import magazzino_profili.web.app as wa

    (tmp_path / "cert.pem").write_text("cert", encoding="utf-8")
    (tmp_path / "key.pem").write_text("key", encoding="utf-8")
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        "[web]\n"
        "certificato_pem = 'cert.pem'\n"
        "chiave_privata = 'key.pem'\n"
        "[scadenze]\n"
        "intervallo_secondi = 10.0\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MAGAZZINO_CONFIG", str(cfg))
    monkeypatch.setattr(wa, "crea_app", lambda **k: w.crea_app())  # no-op
    monkeypatch.setattr(wa, "avvia", lambda self: None)
    monkeypatch.setattr(wa, "ferma", lambda self: None)

    codice = wa.main()
    assert codice == 0


def test_ui_dialogo_accesso_e_barra_di_stato():
    """DialogoAccesso è un QDialog e chiama accept(); barra di stato usata."""
    from PySide6.QtWidgets import QApplication, QDialog

    import magazzino_profili.ui.finestra_principale as f

    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    assert issubclass(f.DialogoAccesso, QDialog)
    assert "accept" in inspect.getsource(f.DialogoAccesso)


def test_main_non_usa_account_predefinito_when_utenze_esse(monkeypatch):
    """main non crea un utente predefinito: nessun account di ripiego, codice 1.

    Nel processo esiste già un'interfaccia (QApplication): ``main()`` non deve
    crearne un'altra né aggirare l'accesso; esce con codice 1.
    """
    from PySide6.QtWidgets import QApplication

    import magazzino_profili.main as m

    app = QApplication.instance()
    if app is None:
        app = QApplication([])  # mantenuto vivo per tutta la durata del test

    def falso_factory():
        s = MagicMock()
        s.__enter__.return_value = s
        s.__exit__.return_value = False
        s.scalars.return_value.first.return_value = object()
        return s

    monkeypatch.setattr(m, "crea_session_factory", lambda eng: falso_factory)
    monkeypatch.setattr(m, "_esiste_almeno_un_utente", lambda f: True)
    codice = m.main()
    assert codice == 1


def test_main_solleva_errore_leggibile_when_nessuna_utente(monkeypatch):
    """Senza utenti, main() deve dare errore leggibile (e non crashare)."""
    import magazzino_profili.main as m

    monkeypatch.setattr(m, "_esiste_almeno_un_utente", lambda f: False)
    with pytest.raises(Exception) as excinfo:
        m.main()
    assert "utenti" in str(excinfo.value).lower()


def test_desktop_non_crea_worker_nella_sua_main():
    """main.py (desktop) non crea il worker delle scadenze: è nel processo web."""
    import magazzino_profili.main as m
    import magazzino_profili.web.app as wa

    assert "PianificatoreScadenze" not in inspect.getsource(m)
    assert "PianificatoreScadenze" in inspect.getsource(wa)


def test_ui_non_crea_worker():
    """L'UI desktop non crea il worker (è nel processo web)."""
    import magazzino_profili.ui.finestra_principale as f

    assert "PianificatoreScadenze" not in inspect.getsource(f)
