"""Fase 13 completa — popup di aggiornamento (pytest-qt, tutto simulato).

Nessun download reale e nessun processo: ``scarica`` e ``esegui`` sono
iniettati. La classe di errore del servizio viene presa per nome dal
modulo (nessun refuso possibile).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from PySide6.QtWidgets import QDialog, QLabel

from magazzino_profili.services import aggiornamenti as ag
from magazzino_profili.ui.dialogo_aggiornamento import DialogoAggiornamento

ECC = getattr(ag, [n for n in dir(ag) if n.startswith("Errore")][0])

DATI = b"installer-finto" * 1000
SHA = hashlib.sha256(DATI).hexdigest()


def _manifest() -> ag.Manifest:
    return ag.Manifest(
        versione="2.0.0",
        url_installer="https://esempio.invalid/i.exe",
        sha256=SHA,
        dimensione=len(DATI),
        note="correzione dei bug segnalati",
    )


def test_dialogo_mostra_versioni_e_note(qtbot):
    dlg = DialogoAggiornamento(_manifest(), scarica=None)
    qtbot.addWidget(dlg)
    assert dlg.windowTitle() == "Aggiornamento disponibile"
    testi = " ".join(q.text() for q in dlg.findChildren(QLabel))
    assert "2.0.0" in testi and "correzione dei bug segnalati" in testi
    assert dlg._btn_ora.text() == "Scarica e installa ora"
    assert dlg._btn_poi.text() == "Più tardi"


def test_più_tardi_chiude_con_rejected(qtbot):
    dlg = DialogoAggiornamento(_manifest(), scarica=None)
    qtbot.addWidget(dlg)
    dlg._btn_poi.click()
    assert dlg.result() == QDialog.Rejected


def _scarica_ok(cartella_destinazione: Path):
    def scarica(manifest, cartella, avanzamento=None):
        if avanzamento:
            avanzamento(0, len(DATI))
            avanzamento(len(DATI), len(DATI))
        finale = Path(cartella) / "Installer-2.0.0.exe"
        finale.write_bytes(DATI)
        return finale

    return scarica


def test_flusso_installa_lancia_nuova_versione(qtbot):
    eseguiti = []
    dlg = DialogoAggiornamento(
        _manifest(), scarica=_scarica_ok(Path()), esegui=eseguiti.append
    )
    qtbot.addWidget(dlg)
    dlg._btn_ora.click()
    qtbot.waitUntil(lambda: "preparo il riavvio" in dlg._stato.text(), timeout=5000)
    assert dlg.result() == QDialog.Accepted
    assert eseguiti and isinstance(eseguiti[0], list) and len(eseguiti[0]) >= 2


def test_errore_download_mostra_recupero_e_permette_riprovare(qtbot):
    def scarica_ko(manifest, cartella, avanzamento=None):
        raise ECC("Errore simulato di rete.")

    dlg = DialogoAggiornamento(_manifest(), scarica=scarica_ko)
    qtbot.addWidget(dlg)
    dlg._btn_ora.click()
    qtbot.waitUntil(lambda: "Recupero" in dlg._stato.text(), timeout=5000)
    assert "Errore simulato di rete" in dlg._stato.text()
    assert dlg.result() == QDialog.Rejected  # ancora aperta, non accettata
    assert dlg._btn_ora.isEnabled()  # si può riprovare


def test_avanzamento_barra(qtbot):
    dlg = DialogoAggiornamento(_manifest(), scarica=_scarica_ok(Path()), esegui=lambda comando: None)
    qtbot.addWidget(dlg)
    dlg._btn_ora.click()
    qtbot.waitUntil(lambda: "preparo il riavvio" in dlg._stato.text(), timeout=5000)
    assert dlg._barra.value() == 100


def test_config_aggiornamento_github_di_default(tmp_path):
    cfg = ag.leggi_config_aggiornamento(tmp_path / "inesistente.toml")
    assert cfg.abilitato is True and cfg.feed_url == ag.GITHUB_FEED


def test_config_aggiornamento_da_file(tmp_path):
    file = tmp_path / "config.toml"
    file.write_text(
        '[update]\nabilitato = true\nfeed_url = "https://x/m.json"\n',
        encoding="utf-8",
    )
    cfg = ag.leggi_config_aggiornamento(file)
    assert cfg.abilitato is True and cfg.feed_url == "https://x/m.json"


def test_config_aggiornamento_file_ileggibile(tmp_path):
    file = tmp_path / "config.toml"
    file.write_text("non = toml valido [", encoding="utf-8")
    cfg = ag.leggi_config_aggiornamento(file)
    assert cfg.abilitato is False
