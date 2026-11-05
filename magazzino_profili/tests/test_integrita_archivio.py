"""Regressioni backup: immagini mutate o non valide, solo dati sintetici."""
import hashlib
import json
from pathlib import Path
import zipfile

from PIL import Image
import pytest
from sqlalchemy import select

from magazzino_profili.domain import Profilo
from magazzino_profili.reports.archivio import esporta_archivio_dati
from magazzino_profili.tests.test_correzioni_dati import factory


def associa(factory, file):
    with factory() as s, s.begin():
        s.scalar(select(Profilo)).immagine_sezione = str(file)


def test_checksum_corrisponde_ai_byte_archiviati_anche_se_la_fonte_cambia(factory,tmp_path,monkeypatch):
    fonte=tmp_path/'sezione.png'
    Image.new('RGB',(8,8),'red').save(fonte)
    associa(factory,fonte)
    write,writestr=zipfile.ZipFile.write,zipfile.ZipFile.writestr
    mutata=[]
    def cambia():
        if not mutata:
            Image.new('RGB',(8,8),'blue').save(fonte)
            mutata.append(True)
    def scrivi(self,filename,arcname=None,*args,**kwargs):
        esito=write(self,filename,arcname,*args,**kwargs)
        if Path(filename)==fonte:cambia()
        return esito
    def scrivi_byte(self,nome,dati,*args,**kwargs):
        esito=writestr(self,nome,dati,*args,**kwargs)
        if isinstance(nome,str) and nome.startswith('sezioni/'):cambia()
        return esito
    monkeypatch.setattr(zipfile.ZipFile,'write',scrivi)
    monkeypatch.setattr(zipfile.ZipFile,'writestr',scrivi_byte)
    with factory() as s:esporta_archivio_dati(s,tmp_path/'backup.zip')
    assert mutata
    with zipfile.ZipFile(tmp_path/'backup.zip') as z:
        immagine=json.loads(z.read('manifest.json'))['immagini'][0]
        assert immagine['sha256']==hashlib.sha256(z.read(immagine['file'])).hexdigest()


def test_png_non_valido_non_pubblica_backup_e_preserva_precedente(factory,tmp_path,catalogo_isolato):
    fonte=tmp_path/'corrotta.png';fonte.write_bytes(b'non sono una immagine')
    associa(factory,fonte)
    destinazione=tmp_path/'backup.zip';destinazione.write_bytes(b'backup precedente')
    with factory() as s:
        with pytest.raises(ValueError,match='Immagine'):
            esporta_archivio_dati(s,destinazione)
    assert destinazione.read_bytes()==b'backup precedente'
