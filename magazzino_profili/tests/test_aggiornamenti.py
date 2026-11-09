"""Fase 13 completa — download, firma Ed25519 del manifest, feed, riavvio.

I test di firma generano una coppia di chiavi Ed25519 DI TEST (non usano
mai la chiave privata del publisher: quella è in firme/ e non è in git).
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import threading
from contextlib import contextmanager

import pytest

from magazzino_profili.services import aggiornamenti as ag

try:  # la firma usa ``cryptography`` (dichiarata in requirements.txt)
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    _HA_CRIPTOGRAFIA = True
except ImportError:  # pragma: no cover
    _HA_CRIPTOGRAFIA = False

ESIGNE = pytest.mark.skipif(not _HA_CRIPTOGRAFIA, reason="cryptography non installata")


def _coppia_test():
    """Nuova coppia Ed25519 di TEST + firma su forma canonica (chiave pubblica in b64)."""
    privata = Ed25519PrivateKey.generate()
    pubblica = base64.b64encode(
        privata.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
    ).decode()

    def firma(dati: dict) -> str:
        corpo = {k: v for k, v in dati.items() if k != "firma"}
        return base64.b64encode(privata.sign(ag.forma_canonica(corpo))).decode()

    return pubblica, firma

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
    assert sorted(p.name for p in (p for p in tmp_path.iterdir() if p.name != ".magazzino.lock")) == ["Installer-1.2.0.exe"]  # niente .part né .lock


def test_download_troncato(tmp_path):
    with pytest.raises(ag.ErroreAggiornamento, match="incompleto"):
        ag.scarica_e_verifica(manifest(), tmp_path, apri_con(DATI[:-10]), OK)
    assert list((p for p in tmp_path.iterdir() if p.name != ".magazzino.lock")) == []


def test_rete_interrotta_a_meta(tmp_path):
    with pytest.raises(ag.ErroreAggiornamento, match="rete"):
        ag.scarica_e_verifica(manifest(), tmp_path, apri_con(DATI, errore_dopo=1000), OK)
    assert list((p for p in tmp_path.iterdir() if p.name != ".magazzino.lock")) == []


def test_file_piu_grande_del_previsto(tmp_path):
    with pytest.raises(ag.ErroreAggiornamento, match="più grande"):
        ag.scarica_e_verifica(manifest(), tmp_path, apri_con(DATI + b"x" * 200000), OK)
    assert list((p for p in tmp_path.iterdir() if p.name != ".magazzino.lock")) == []


def test_checksum_errato(tmp_path):
    corrotto = bytearray(DATI)
    corrotto[5] ^= 1
    with pytest.raises(ag.ErroreAggiornamento, match="corrotto"):
        ag.scarica_e_verifica(manifest(), tmp_path, apri_con(bytes(corrotto)), OK)
    assert list((p for p in tmp_path.iterdir() if p.name != ".magazzino.lock")) == []


def test_firma_errata_non_rende_disponibile_nulla(tmp_path):
    with pytest.raises(ag.ErroreAggiornamento, match="autentico"):
        ag.scarica_e_verifica(manifest(), tmp_path, apri_con(DATI), firma_errata)
    assert list((p for p in tmp_path.iterdir() if p.name != ".magazzino.lock")) == []


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


def test_file_lock_residuo_non_blocca_dopo_crash(tmp_path):
    (tmp_path / ".magazzino.lock").write_text("0")
    file=ag.scarica_e_verifica(manifest(),tmp_path,apri_con(DATI),OK)
    assert file.read_bytes()==DATI
    assert (tmp_path / ".magazzino.lock").exists()


# ---------------------------------------------------------------------------
# Fase 13 completa: firma Ed25519, feed, riavvio
# ---------------------------------------------------------------------------


def test_forma_canonica_deterministica_chiavi_in_ordine_diverso():
    a = {"b": 1, "a": [1, {"d": 1, "c": 2}]}
    b = {"a": [1, {"c": 2, "d": 1}], "b": 1}
    assert ag.forma_canonica(a) == ag.forma_canonica(b)


@ESIGNE
def test_firma_valida_con_chiave_corrispondente():
    pubblica, firma = _coppia_test()
    corpo = {"versione": "1.0.0", "nota": "test"}
    assert ag.firma_valida(corpo, firma(corpo), pubblica) is True


@ESIGNE
def test_firma_valida_rifiuta_chiave_diversa():
    pubblica, firma = _coppia_test()
    pubblica_altra, _ = _coppia_test()
    corpo = {"versione": "1.0.0"}
    assert ag.firma_valida(corpo, firma(corpo), pubblica_altra) is False


@ESIGNE
def test_firma_valida_rifiuta_corpo_alterato_dopo_la_firma():
    pubblica, firma = _coppia_test()
    corpo = {"versione": "1.0.0", "url": "https://x/i.exe"}
    f = firma(corpo)
    assert ag.firma_valida(dict(corpo, url="https://altro/i.exe"), f, pubblica) is False


@ESIGNE
def test_firma_valida_chiave_non_ed25519_rifiutata_senza_eccezioni():
    brutta = base64.b64encode(b"\x01" * 32).decode()
    assert ag.firma_valida({"versione": "1"}, "AAAA", brutta) is False


def _manifest_firmato(pubblica, firma, **k):
    base = dict(
        versione="2.0.0",
        url_installer="https://esempio.invalid/i.exe",
        sha256="ab" * 32,
        dimensione=123,
        pubblicato="2026-10-31",
    )
    base.update(k)
    out = dict(base)
    out["firma"] = firma(out)
    return pubblica, out


@ESIGNE
def test_valida_manifest_accetta_firma_valida():
    pubblica, out = _manifest_firmato(*_coppia_test())
    m = ag.valida_manifest(out, pubblica)
    assert (m.versione, m.note, m.dimensione) == ("2.0.0", None, 123)


@ESIGNE
def test_valida_manifest_accetta_note_opzionale():
    pubblica, out = _manifest_firmato(*_coppia_test(), note="correzione bug")
    assert ag.valida_manifest(out, pubblica).note == "correzione bug"


@ESIGNE
def test_valida_manifest_rifiuta_corpo_alterato_dopo_la_firma():
    pubblica, out = _manifest_firmato(*_coppia_test())
    out["sha256"] = "cd" * 32
    with pytest.raises(ag.ErroreAggiornamento, match="non è autentico"):
        ag.valida_manifest(out, pubblica)


@ESIGNE
@pytest.mark.parametrize("campo", ["versione", "url_installer", "sha256", "dimensione", "firma"])
def test_valida_manifest_rifiuta_campo_mancante(campo):
    pubblica, out = _manifest_firmato(*_coppia_test())
    del out[campo]
    with pytest.raises(ag.ErroreAggiornamento, match="manca"):
        ag.valida_manifest(out, pubblica)


@ESIGNE
def test_valida_manifest_rifiuta_chiave_pubblica_errata():
    _, firma = _coppia_test()
    pubblica_altra, _ = _coppia_test()
    out = dict(versione="2.0.0", url_installer="https://esempio.invalid/i.exe",
               sha256="ab" * 32, dimensione=1)
    out["firma"] = firma(out)
    with pytest.raises(ag.ErroreAggiornamento, match="non è autentico"):
        ag.valida_manifest(out, pubblica_altra)


def test_manifest_note_opzionale_default():
    assert manifest().note is None
    assert manifest(note="x").note == "x"


def _feed_finto(dati: bytes):
    @contextmanager
    def apri(url: str):
        class R:
            def read(s, n=-1):
                return dati

        yield R()

    return apri


@ESIGNE
def test_leggi_feed_ok_con_apri_finto():
    pubblica, out = _manifest_firmato(*_coppia_test())
    corpo = json.dumps(out, ensure_ascii=False).encode("utf-8")
    m = ag.leggi_feed("https://esempio.invalid/update/manifest.json",
                      apri=_feed_finto(corpo), chiave_pubblica_b64=pubblica)
    assert m.versione == "2.0.0"


def test_leggi_feed_json_non_valido():
    with pytest.raises(ag.ErroreAggiornamento, match="non è JSON"):
        ag.leggi_feed("https://esempio.invalid/m.json", apri=_feed_finto(b"non-JSON"))


def test_leggi_feed_indirizzo_non_http_rifiutato():
    with pytest.raises(ag.ErroreAggiornamento, match="http/https"):
        ag.leggi_feed("ftp://esempio.invalid/m.json")


def test_leggi_feed_http_remoto_rifiutato():
    with pytest.raises(ag.ErroreAggiornamento, match="HTTPS"):
        ag.leggi_feed("http://remoto.invalid/m.json")


@ESIGNE
def test_leggi_feed_http_localhost_accettato():
    pubblica, out = _manifest_firmato(*_coppia_test())
    corpo = json.dumps(out).encode("utf-8")
    m = ag.leggi_feed("http://localhost:8443/update/manifest.json",
                      apri=_feed_finto(corpo), chiave_pubblica_b64=pubblica)
    assert m.versione == "2.0.0"


def test_comando_riavvio_contiene_percorso_e_attesa():
    c = ag.comando_riavvio("C:/prova/Nuova.exe", 3)
    assert "C:/prova/Nuova.exe" in " ".join(c) and "3" in " ".join(c)


@pytest.mark.parametrize("percorso,attesa", [("", 2), ("x", -1), ("x", True), (None, 2)])
def test_comando_riavvio_argomenti_invalidi(percorso, attesa):
    with pytest.raises(ag.ErroreAggiornamento):
        ag.comando_riavvio(percorso, attesa)


def test_lancia_aggiornamento_con_esegui_finto():
    visti = []
    comando = ag.lancia_aggiornamento("C:/prova/Nuova.exe", 1, esegui=visti.append)
    assert visti == [comando] and len(visti[0]) >= 2


def test_lancia_aggiornamento_percorso_invalido():
    with pytest.raises(ag.ErroreAggiornamento):
        ag.lancia_aggiornamento("", esegui=lambda c: None)


def test_testo_recupero_in_italiano():
    testo = ag.testo_recupero()
    assert "Recupero" in testo and "non è stata modificata" in testo
