import hashlib,json,zipfile
from types import SimpleNamespace
import pytest
from magazzino_profili.services.pacchetto_aggiornamento import installa_zip
from magazzino_profili.services.aggiornamenti import ErroreAggiornamento


def pacchetto(tmp_path,extra=None):
    p=tmp_path/'app.zip';exe=b'MZ-eseguibile-di-prova'
    with zipfile.ZipFile(p,'w') as z:
        z.writestr('MagazzinoProfili.exe',exe)
        z.writestr('_internal/libreria.dll',b'prova')
        z.writestr('catalogo_immagini/AA1.png',b'PNG-sintetico')
        if extra:z.writestr(extra,b'non ammesso')
    return p,SimpleNamespace(versione='99.1.0',firmato={'sha256_eseguibile':hashlib.sha256(exe).hexdigest(),'versione':'99.1.0'})


def test_installa_tutta_la_cartella_e_non_sovrascrive(tmp_path):
    p,m=pacchetto(tmp_path)
    exe=installa_zip(m,p,tmp_path/'versioni')
    assert (exe.parent/'_internal/libreria.dll').read_bytes()==b'prova'
    assert installa_zip(m,p,tmp_path/'versioni')==exe
    exe.write_bytes(b'alterato')
    with pytest.raises(ErroreAggiornamento):installa_zip(m,p,tmp_path/'versioni')


@pytest.mark.parametrize('nome',['../uscita.txt','/assoluto.txt','C:/file.txt','..\\file.txt'])
def test_zip_non_esce_dalla_destinazione(tmp_path,nome):
    p,m=pacchetto(tmp_path,nome)
    with pytest.raises(ErroreAggiornamento):installa_zip(m,p,tmp_path/'versioni')
    assert not (tmp_path/'uscita.txt').exists()


def test_manca_checksum_firmato(tmp_path):
    p,m=pacchetto(tmp_path);m.firmato={}
    with pytest.raises(ErroreAggiornamento):installa_zip(m,p,tmp_path/'versioni')
