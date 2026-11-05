"""Regressione Fase 3b — B-03: errori DB in UI loggati, bug propagati.

``_aggiorna_stato_riepilogo`` intercetta solo ``SQLAlchemyError``
(mostrando «Database non raggiungibile» e registrando il traceback);
qualsiasi altra eccezione (es. ``RuntimeError`` per un bug nel codice)
deve propagarsi, non essere confusa con un problema di database.
"""

import logging
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import OperationalError

from magazzino_profili.services import consultazione, impostazioni
from magazzino_profili.ui.finestra_principale import FinestraPrincipale


def _self_minimo(qapp) -> SimpleNamespace:
    """Duck-typing del ``self``: solo gli attributi letti dal metodo sotto
    test, senza istanziare la classe Qt (Shiboken richiede ``__init__``)."""
    from PySide6.QtWidgets import QLabel

    class _SessioneFinta:
        def close(self) -> None:
            pass

    f = SimpleNamespace()
    f._factory = lambda: _SessioneFinta()
    f._stato_db = QLabel()
    f._pallino_db = QLabel()
    f._conta_riepilogo = QLabel()
    return f


def test_stato_db_errore_sql_loggato_etichetta_non_raggiungibile(qapp, monkeypatch, caplog) -> None:
    f = _self_minimo(qapp)
    monkeypatch.setattr(impostazioni, "leggi_soglia", lambda sessione: 100)

    def guasto_db(*_args, **_kwargs):
        raise OperationalError("SELECT 1", {}, Exception("db down"))

    monkeypatch.setattr(consultazione, "riepilogo_inventario", guasto_db)
    with caplog.at_level(logging.ERROR):
        FinestraPrincipale._aggiorna_stato_riepilogo(f)

    assert f._stato_db.text() == "Database non raggiungibile"
    recordi = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert recordi, "nessun record ERROR: il traceback non è stato registrato"
    assert any(r.exc_info is not None for r in recordi)


def test_stato_db_bug_reale_si_propaga(qapp, monkeypatch) -> None:
    f = _self_minimo(qapp)
    monkeypatch.setattr(impostazioni, "leggi_soglia", lambda sessione: 100)

    def bug_nel_codice(*_args, **_kwargs):
        raise RuntimeError("bug")

    monkeypatch.setattr(consultazione, "riepilogo_inventario", bug_nel_codice)
    with pytest.raises(RuntimeError, match="bug"):
        FinestraPrincipale._aggiorna_stato_riepilogo(f)
