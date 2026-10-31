"""Fase 13 — nucleo del download di aggiornamento: 17 test (solo libreria standard).

Il resto della fase (feed, firma, installer, popup) resta in ATTESA dei
nove valori forniti dal proprietario; questi test coprono solo ciò che è
verificabile senza di essi.
"""

from __future__ import annotations

import hashlib
import io
import threading
from contextlib import contextmanager

import pytest

from magazzino_profili.services import aggiornamenti as ag

DATI = b"installer-finto" * 1000
SHA = hashlib.sha256(DATI).hexdigest()


def manifest(**k) -> ag.Manifest:
    base = dict(versione="1.2.0", url_installer="https://esempio.invalid/i.exe", sha256=SHA, dimensione=len(DATI))
    base.update(k)
    return ag.Manifest(**base)


def apri_con(dati: bytes, errore_dopo: int | None = None):
    @contextmanager
    def apri(url: str):
        class R:
            def __init__(s):
                s.f = io.BytesIO(dati)
                s.n = 0

            def read(s, n):
                if errore_dopo is not None and s.n >= errore_dopo:
                    raise ConnectionResetError("rete")
                b = s.f.read(n)
                s.n += len(b)
                return b

        yield R()

    return apri


OK = lambda p: None


def firma_errata(p):
    raise ag.ErroreAggiornamento("Firma non valida: l'aggiornamento non è autentico.")


def test_versioni():
    assert ag.esiste_aggiornamento("1.2.0", "1.1.9") and ag.esiste_aggiornamento("1.10.0", "1.9.0")  # non confronto testuale
    assert not ag.esiste_aggiornamento("1.2.0", "1.2.0") and not ag.esiste_aggiornamento("1.1.0", "1.2.0")
    for brutta in ["", "1.2", "v1.2.0", "1.2.0-beta", "a.b.c", None]:
        with pytest.raises(ag.ErroreAggiornamento):
            ag.parse_versione(brutta)


@pytest.mark.parametrize(
    "campo,valore",
    [
        ("url_installer", "http://x/i.exe"),
        ("url_installer", "ftp://x"),
        ("sha256", "abc"),
        ("sha256", SHA.upper()),
        ("dimensione", 0),
        ("dimensione", True),
        ("versione", "x"),
    ],
)
def test_manifest_non_valido(campo, valore):
    with pytest.raises(ag.ErroreAggiornamento):
        manifest(**{campo: valore})


def test_download_riuscito_e_avanzamento(tmp_path):
    visti = []
    f = ag.scarica_e_verifica(manifest(), tmp_path, apri_con(DATI), OK, lambda a, t: visti.append((a, t)))
    assert f.read_bytes() == DATI and visti[-1] == (len(DATI), len(DATI))
    assert sorted(p.name for p in tmp_path.iterdir()) == ["Installer-1.2.0.exe"]  # niente .part né .lock


def test_download_troncato(tmp_path):
    with pytest.raises(ag.ErroreAggiornamento, match="incompleto"):
        ag.scarica_e_verifica(manifest(), tmp_path, apri_con(DATI[:-10]), OK)
    assert list(tmp_path.iterdir()) == []


def test_rete_interrotta_a_meta(tmp_path):
    with pytest.raises(ag.ErroreAggiornamento, match="rete"):
        ag.scarica_e_verifica(manifest(), tmp_path, apri_con(DATI, errore_dopo=1000), OK)
    assert list(tmp_path.iterdir()) == []


def test_file_piu_grande_del_previsto(tmp_path):
    with pytest.raises(ag.ErroreAggiornamento, match="più grande"):
        ag.scarica_e_verifica(manifest(), tmp_path, apri_con(DATI + b"x" * 200000), OK)
    assert list(tmp_path.iterdir()) == []


def test_checksum_errato(tmp_path):
    corrotto = bytearray(DATI)
    corrotto[5] ^= 1
    with pytest.raises(ag.ErroreAggiornamento, match="corrotto"):
        ag.scarica_e_verifica(manifest(), tmp_path, apri_con(bytes(corrotto)), OK)
    assert list(tmp_path.iterdir()) == []


def test_firma_errata_non_rende_disponibile_nulla(tmp_path):
    with pytest.raises(ag.ErroreAggiornamento, match="autentico"):
        ag.scarica_e_verifica(manifest(), tmp_path, apri_con(DATI), firma_errata)
    assert list(tmp_path.iterdir()) == []


def test_la_verifica_vede_il_file_parziale_e_non_quello_finale(tmp_path):
    visti = []

    def v(p):
        visti.append((p.name, (tmp_path / "Installer-1.2.0.exe").exists()))

    ag.scarica_e_verifica(manifest(), tmp_path, apri_con(DATI), v)
    assert visti == [("Installer-1.2.0.exe.part", False)]


def test_download_concorrenti_rifiutati(tmp_path):
    fermo, via, esiti = threading.Event(), threading.Event(), []

    @contextmanager
    def lento(url):
        class R:
            def read(s, n):
                via.set()
                fermo.wait(5)
                return b""

        yield R()

    def _prova(p, apri):
        try:
            ag.scarica_e_verifica(manifest(), p, apri, OK)
        except ag.ErroreAggiornamento as e:
            return "incompleto" if "incompleto" in str(e) else str(e)
        return "ok"

    t = threading.Thread(target=lambda: esiti.append(_prova(tmp_path, lento)))
    t.start()
    via.wait(5)
    with pytest.raises(ag.ErroreAggiornamento, match="già in corso"):
        ag.scarica_e_verifica(manifest(), tmp_path, apri_con(DATI), OK)
    fermo.set()
    t.join()
    assert esiti == ["incompleto"]
    ag.scarica_e_verifica(manifest(), tmp_path, apri_con(DATI), OK)  # dopo la fine il blocco è libero


def test_blocco_tra_processi_file_lock(tmp_path):
    (tmp_path / ".aggiornamento.lock").write_text("1234")
    with pytest.raises(ag.ErroreAggiornamento, match="altro processo"):
        ag.scarica_e_verifica(manifest(), tmp_path, apri_con(DATI), OK)
    assert (tmp_path / ".aggiornamento.lock").exists()  # il lock altrui NON viene cancellato
