"""Fase 7 — ValidatoreMaiuscolo: unità e integrazione con QLineEdit."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PySide6.QtGui import QValidator  # noqa: E402
from PySide6.QtWidgets import QApplication, QLineEdit  # noqa: E402

from magazzino_profili.ui.validatori import ValidatoreMaiuscolo  # noqa: E402


@pytest.fixture()
def app(qapp: QApplication):  # fixture di pytest-qt
    return qapp


def test_unitario(app):
    v = ValidatoreMaiuscolo(None)
    casi = [
        ("ab12", "AB12", 0),
        (" aB-12 ", " AB-12 ", 4),
        ("  az 2001 ", "  AZ 2001 ", 10),
        ("", "", 0),
        ("mIxEd üß", "MIXED ÜSS", 7),
    ]
    for testo, atteso, pos in casi:
        stato, valore, p = v.validate(testo, pos)
        assert stato == QValidator.State.Acceptable
        assert valore == atteso
        assert p == pos


def test_settext_diventa_maiuscolo(app):
    q = QLineEdit()
    q.setValidator(ValidatoreMaiuscolo(q))
    q.setText("ab12")
    assert q.text() == "AB12"


def test_digitazione_diventa_maiuscolo(app, qtbot):
    from PySide6.QtTest import QTest

    q = QLineEdit()
    q.setValidator(ValidatoreMaiuscolo(q))
    qtbot.keyClick(q, "a")
    qtbot.keyClick(q, "b")
    qtbot.keyClick(q, "1")
    qtbot.keyClick(q, "2")
    assert q.text() == "AB12"
