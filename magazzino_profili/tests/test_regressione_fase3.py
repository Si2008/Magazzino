"""Regressioni della Fase 3: un test per ogni bug verificato corretto.

I test PostgreSQL (concorrenza) richiedono MAGAZZINO_TEST_DB_URL e
usano un database di test: create_all/drop_all sono eseguiti solo lì.
"""

from __future__ import annotations

import logging
import os
import threading
import zipfile
from pathlib import Path

import pytest
from PySide6.QtTest import QTest
from sqlalchemy import select

from magazzino_profili.backup.backup_db import PianificatoreBackup
from magazzino_profili.db import crea_engine, crea_session_factory, crea_tabelle
from magazzino_profili.domain import Base, Pezzo, Profilo
from magazzino_profili.reports import esporta_inventario_csv, importa_peczi_csv, importa_ods_file
from magazzino_profili.services import PezzoNonTrovatoError, carica, scarica
from magazzino_profili.services.anagrafica import crea_profilo
from magazzino_profili.services.consultazione import cerca_pezzi
from magazzino_profili.services.eccezioni import ProfiloNonTrovatoError
from magazzino_profili.ui.scheda_carico import SchedaCarico

PG_URL = os.environ.get("MAGAZZINO_TEST_DB_URL")
richiede_pg = pytest.mark.skipif(PG_URL is None, reason="MAGAZZINO_TEST_DB_URL non impostata")


def _fabbrica(tmp_path: Path, nome: str = "f3.db"):
    eng = crea_engine(url=f"sqlite:///{tmp_path / nome}")
    crea_tabelle(eng)
    return crea_session_factory(eng)


def _profilo(F, codice: str) -> None:
    s = F()
    crea_profilo(s, codice, f"Profilo {codice}", 1.0, 6000, "test")
    s.close()


def _pezzi(F) -> dict[str, int]:
    s = F()
    risultato = {p.barcode: p.quantita for p in s.scalars(select(Pezzo))}
    s.close()
    return risultato


# ---------------------------------------------------------------- P1 concorrenza
@richiede_pg
def test_concorrenza_nessuna_unita_persa() -> None:
    eng = crea_engine(url=PG_URL.replace("postgresql://", "postgresql+psycopg://", 1))
    Base.metadata.drop_all(eng)
    crea_tabelle(eng)
    F = crea_session_factory(eng)
    _profilo(F, "CONC1")
    s = F()
    carica(s, "CONC1", "BIANCO", 6000, 10, "test", "init")
    s.close()

    errori: list[str] = []

    def lavora() -> None:
        for _ in range(50):
            s = F()
            try:
                carica(s, "CONC1", "BIANCO", 6000, 1, "test", "thread")
            except Exception as e:  # noqa: BLE001 - il test deve vedere ogni errore
                errori.append(repr(e))
            finally:
                s.close()

    fili = [threading.Thread(target=lavora) for _ in range(3)]
    for f in fili:
        f.start()
    for f in fili:
        f.join()
    eng.dispose()
    assert errori == [], f"errori durante il carico concorrente: {errori[:3]}"
    assert _pezzi(F)["CONC1-BIANCO-6000"] == 10 + 150


@richiede_pg
def test_concorrenza_creazione_pezzo_senza_errori() -> None:
    eng = crea_engine(url=PG_URL.replace("postgresql://", "postgresql+psycopg://", 1))
    Base.metadata.drop_all(eng)
    crea_tabelle(eng)
    F = crea_session_factory(eng)
    _profilo(F, "CONC2")

    errori: list[str] = []

    def lavora() -> None:
        for _ in range(20):
            s = F()
            try:
                carica(s, "CONC2", "NERO", 3000, 1, "test", "thread")
            except Exception as e:  # noqa: BLE001
                errori.append(repr(e))
            finally:
                s.close()

    fili = [threading.Thread(target=lavora) for _ in range(3)]
    for f in fili:
        f.start()
    for f in fili:
        f.join()
    eng.dispose()
    assert errori == [], f"errori alla creazione concorrente: {errori[:3]}"
    assert _pezzi(F)["CONC2-NERO-3000"] == 60


# ---------------------------------------------------------------- P7 parser barcode
def test_parser_barcode_usa_anagrafica_con_trattino(qtbot, tmp_path) -> None:
    F = _fabbrica(tmp_path)
    _profilo(F, "AB-12")
    w = SchedaCarico(F, "test")
    qtbot.addWidget(w)
    w._compila_dal_barcode("AB-12-NERO-6000")
    assert (w.codice.text(), w.colore.text(), w.lunghezza.text()) == ("AB-12", "NERO", "6000")


def test_parser_barcode_ambiguo_non_compila(qtbot, tmp_path) -> None:
    F = _fabbrica(tmp_path)
    _profilo(F, "AB")
    _profilo(F, "AB-12")
    w = SchedaCarico(F, "test")
    qtbot.addWidget(w)
    w._compila_dal_barcode("AB-12-NERO-6000")
    assert w.codice.text() == "", "barcode ambiguo: i campi non devono essere compilati a caso"


def test_parser_barcode_esistente_ha_precedenza(qtbot, tmp_path) -> None:
    F = _fabbrica(tmp_path)
    _profilo(F, "AB")
    s = F()
    carica(s, "AB", "12-NERO", 6000, 2, "test", "init")
    s.close()
    w = SchedaCarico(F, "test")
    qtbot.addWidget(w)
    w._compila_dal_barcode("AB-12-NERO-6000")
    assert (w.codice.text(), w.colore.text()) == ("AB", "12-NERO")


# ---------------------------------------------------------------- S6 HTML nelle causali
def test_causale_html_mostrata_come_testo(qtbot, tmp_path) -> None:
    F = _fabbrica(tmp_path)
    _profilo(F, "AB12")
    s = F()
    carica(s, "AB12", "NERO", 6000, 1, "test", "<b>GRASSETTO</b>")
    s.close()
    w = SchedaCarico(F, "test")
    qtbot.addWidget(w)
    assert "<b>GRASSETTO</b>" in w.movimenti.toPlainText()


# ---------------------------------------------------------------- P8 scarico minuscolo
def test_scarico_accetta_barcode_minuscolo(tmp_path) -> None:
    F = _fabbrica(tmp_path)
    _profilo(F, "AB12")
    s = F()
    carica(s, "AB12", "AN007", 6000, 10, "test", "init")
    s.close()
    s = F()
    scarica(s, "ab12-an007-6000", 1, "test", "prova")
    s.close()
    assert _pezzi(F)["AB12-AN007-6000"] == 9


# ---------------------------------------------------------------- ricerca LIKE
def test_ricerca_jolly_non_sono_wildcard(tmp_path) -> None:
    F = _fabbrica(tmp_path)
    _profilo(F, "AB12")
    s = F()
    carica(s, "AB12", "AN007", 6000, 1, "test", "init")
    s.close()
    s = F()
    assert cerca_pezzi(s, "%") == []
    assert cerca_pezzi(s, "A_12") == []
    assert len(cerca_pezzi(s, "AB12")) == 1
    s.close()


# ---------------------------------------------------------------- servizio carico senza creazione
def test_carico_senza_creazione_non_crea_pezzi(tmp_path) -> None:
    F = _fabbrica(tmp_path)
    _profilo(F, "AB12")
    s = F()
    with pytest.raises(PezzoNonTrovatoError):
        carica(s, "AB12", "NERO", 6000, 1, "test", "web", None, crea_se_mancante=False)
    s.close()
    assert _pezzi(F) == {}


# ---------------------------------------------------------------- CSV
def test_csv_profilo_mancante_non_importa_nulla(tmp_path) -> None:
    F = _fabbrica(tmp_path)
    _profilo(F, "AB12")
    csv = tmp_path / "in.csv"
    csv.write_text(
        "Codice profil;Descrizione;Colore;Lunghezza (mm);Quantita;Ubicazione;Barcode\n"
        "AB12;x;NUOVO;6000;4;;\n"
        "NONESISTE;x;BIANCO;6000;1;;\n",
        encoding="utf-8",
    )
    s = F()
    with pytest.raises(ProfiloNonTrovatoError):
        importa_peczi_csv(s, csv, "test")
    s.close()
    assert _pezzi(F) == {}


def test_csv_riga_non_valida_indica_il_numero_di_riga(tmp_path) -> None:
    F = _fabbrica(tmp_path)
    _profilo(F, "AB12")
    csv = tmp_path / "in.csv"
    csv.write_text(
        "Codice profil;Colore;Lunghezza (mm);Quantita\n"
        "AB12;NERO;6000;3\n"
        "AB12;NERO;6000;abc\n",
        encoding="utf-8",
    )
    s = F()
    with pytest.raises(ValueError, match="riga 3"):
        importa_peczi_csv(s, csv, "test")
    s.close()
    assert _pezzi(F) == {}


def test_csv_ubicazione_sopravvive_al_round_trip(tmp_path) -> None:
    F = _fabbrica(tmp_path)
    _profilo(F, "AB12")
    s = F()
    carica(s, "AB12", "NERO", 6000, 5, "test", "init", "Scaffale A")
    s.close()
    out = tmp_path / "inv.csv"
    s = F()
    esporta_inventario_csv(s, out)
    s.close()
    s = F()
    s.execute(__import__("sqlalchemy").text("DELETE FROM movimenti"))
    s.execute(__import__("sqlalchemy").text("DELETE FROM pezzi"))
    s.commit()
    s.close()
    s = F()
    importa_peczi_csv(s, out, "test")
    s.close()
    s = F()
    pz = s.scalar(select(Pezzo))
    s.close()
    assert pz.ubicazione == "Scaffale A"


# ---------------------------------------------------------------- ODS vassoio e duplicati
def _ods(path: Path, righe: list[list]) -> None:
    def cella(v):
        if v == "":
            return "<table:table-cell/>"
        if isinstance(v, (int, float)):
            return (f'<table:table-cell office:value-type="float" office:value="{v}">'
                    f"<text:p>{v}</text:p></table:table-cell>")
        return f'<table:table-cell office:value-type="string"><text:p>{v}</text:p></table:table-cell>'
    corpo = "".join("<table:table-row>" + "".join(cella(v) for v in r) + "</table:table-row>" for r in righe)
    xml = ('<?xml version="1.0"?><office:document-content '
           'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
           'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
           'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"><office:body>'
           '<office:spreadsheet><table:table table:name="Foglio1">' + corpo +
           "</table:table></office:spreadsheet></office:body></office:document-content>")
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("content.xml", xml)


_INTESTAZIONE = ["Profilo", "Colore", "Vassoio", "Dimensione_mm", "Pezzi"]


def test_ods_vassoio_numerico_diventa_ubicazione(tmp_path) -> None:
    F = _fabbrica(tmp_path)
    _ods(tmp_path / "a.ods", [_INTESTAZIONE, ["CD22", "RAL7016", 4, 6000, 3]])
    s = F()
    importa_ods_file(s, tmp_path / "a.ods", "test")
    s.close()
    s = F()
    pz = s.scalar(select(Pezzo))
    s.close()
    assert pz.ubicazione == "Vassoio 4"


def test_ods_vassoio_gia_con_prefisso_non_duplicato(tmp_path) -> None:
    F = _fabbrica(tmp_path)
    _ods(tmp_path / "a.ods", [_INTESTAZIONE, ["CD22", "RAL7016", "Vassoio 4", 6000, 3]])
    s = F()
    importa_ods_file(s, tmp_path / "a.ods", "test")
    s.close()
    s = F()
    pz = s.scalar(select(Pezzo))
    s.close()
    assert pz.ubicazione == "Vassoio 4"


def test_ods_pezzo_esistente_senza_ubicazione_la_riceve(tmp_path) -> None:
    F = _fabbrica(tmp_path)
    _profilo(F, "CD22")
    s = F()
    carica(s, "CD22", "RAL7016", 6000, 1, "test", "init", None)
    s.close()
    _ods(tmp_path / "a.ods", [_INTESTAZIONE, ["CD22", "RAL7016", 4, 6000, 2]])
    s = F()
    importa_ods_file(s, tmp_path / "a.ods", "test")
    s.close()
    s = F()
    pz = s.scalar(select(Pezzo))
    s.close()
    assert pz.ubicazione == "Vassoio 4"
    assert pz.quantita == 3


# ---------------------------------------------------------------- B1 / S7 backup
def test_backup_errore_imprevisto_non_ferma_la_pianificazione(caplog) -> None:
    def azione():
        raise OSError("cartella non scrivibile")

    p = PianificatoreBackup(6, azione)
    p._attivo = True
    with caplog.at_level(logging.ERROR):
        p._esegui_e_ripiani()
    assert p._timer is not None, "il backup successivo deve restare pianificato"
    p.ferma()
    assert any("imprevisto" in r.getMessage() for r in caplog.records)


def test_backup_avvio_con_cartella_non_scrivibile_non_solleva(tmp_path) -> None:
    from magazzino_profili.backup.backup_db import esegui_backup

    bloccante = tmp_path / "file"
    bloccante.write_text("x")
    p = PianificatoreBackup(
        6,
        lambda: esegui_backup("localhost", 5432, "u", "p", "d", bloccante / "backup", 7, ("/bin/false",)),
    )
    p.avvia()  # non deve sollevare
    assert p._timer is not None
    p.ferma()


# ---------------------------------------------------------------- S8 setup config
def test_setup_non_altera_la_sezione_web(tmp_path, monkeypatch) -> None:
    import shutil
    import sys
    from pathlib import Path as P

    radice = P(__file__).resolve().parents[2]
    sys.path.insert(0, str(radice))
    import setup_database as sd

    shutil.copy(radice / "config.example.toml", tmp_path / "config.toml")
    monkeypatch.chdir(tmp_path)
    sd._write_config("PasswordDiProva1")
    testo = (tmp_path / "config.toml").read_text(encoding="utf-8")
    import tomllib

    dati = tomllib.loads(testo)
    assert dati["database"]["password"] == "PasswordDiProva1"
    assert dati["database"]["porta"] == 5432
    assert dati["web"]["host"] == "0.0.0.0"
    assert dati["web"]["porta"] == 8443
    assert "pg_dump" in dati["backup"]
