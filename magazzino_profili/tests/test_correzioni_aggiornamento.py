"""Aggiornamento: annullamento sicuro e attivazione solo dopo verifica di firma."""
import base64,hashlib,json,sys,os
from pathlib import Path
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
from magazzino_profili.services import aggiornamenti as ag


def test_versione_stabile_firmata_e_launcher_verifica_checksum(tmp_path,monkeypatch):
    import magazzino_profili
    chiave=Ed25519PrivateKey.generate()
    pubblica=base64.b64encode(chiave.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)).decode()
    exe=tmp_path/"download.exe";exe.write_bytes(b"contenuto sintetico: non eseguire")
    dati=dict(versione=magazzino_profili.__version__,url_installer="https://esempio.invalid/app.exe",
              sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),dimensione=exe.stat().st_size,pubblicato="2026-11-05")
    dati["firma"]=base64.b64encode(chiave.sign(ag.forma_canonica(dati))).decode()
    originale=ag.valida_manifest
    monkeypatch.setattr(ag,"valida_manifest",lambda d:originale(d,pubblica))
    monkeypatch.setenv("LOCALAPPDATA",str(tmp_path/"appdata"))
    monkeypatch.setenv("XDG_DATA_HOME",str(tmp_path/"appdata"))
    manifest=ag.valida_manifest(dati)
    stabile=ag.prepara_versione(manifest,exe)
    assert stabile.read_bytes()==exe.read_bytes() and stabile.parent.name==magazzino_profili.__version__
    monkeypatch.setattr(sys,"frozen",True,raising=False);monkeypatch.setattr(sys,"executable",str(stabile))
    ag.conferma_versione_avviata()
    assert (stabile.parent.parent/"attiva.json").is_file()
    monkeypatch.setattr(magazzino_profili,"__version__","0.1.0")
    eseguiti=[];monkeypatch.setattr(ag,"lancia_aggiornamento",lambda p,n:eseguiti.append(p))
    assert ag.avvia_versione_attiva() and eseguiti==[str(stabile)]
    stabile.write_bytes(b"alterato")
    assert ag.avvia_versione_attiva() is False and len(eseguiti)==1


def test_annullamento_attesa_non_lancia_aggiornamento_piu_tardi(qtbot,tmp_path):
    from magazzino_profili.ui.dialogo_aggiornamento import DialogoAggiornamento
    manifest=ag.Manifest("99.0.0","https://esempio.invalid/app.exe","ab"*32,123)
    lanci,riprese=[],[]
    d=DialogoAggiornamento(manifest,esegui=lanci.append,prima_del_riavvio=lambda:False,
                           ripristina_servizi=lambda:riprese.append(True))
    qtbot.addWidget(d)
    d._on_fine(str(tmp_path/"finto.exe"));d.reject()
    qtbot.wait(1100)
    assert lanci==[] and riprese==[True]


@pytest.mark.skipif(os.name!="nt",reason="Evento nativo disponibile solo su Windows")
def test_arresto_nativo_funziona_senza_console():
    from magazzino_profili.evento_windows import EventoArresto
    proprietario=EventoArresto();lettore=EventoArresto(proprietario.nome)
    try:
        assert lettore.attendi(0) is False
        proprietario.segnala()
        assert lettore.attendi(100) is True
    finally:lettore.chiudi();proprietario.chiudi()
