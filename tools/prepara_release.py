"""Pacchetto Windows completo e manifest Ed25519: mai dati, backup o credenziali."""
import argparse,base64,hashlib,json,re,zipfile,sys
from datetime import datetime,timezone
from pathlib import Path


def prepara(cartella,destinazione,chiave):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from magazzino_profili import __version__
    from magazzino_profili.services.aggiornamenti import CHIAVE_PUBBLICA_ED25519_B64,forma_canonica
    from cryptography.hazmat.primitives.serialization import load_pem_private_key,Encoding,PublicFormat
    cartella=Path(cartella);destinazione=Path(destinazione)
    if destinazione.exists():raise ValueError('Destinazione release già esistente')
    privata=load_pem_private_key(Path(chiave).read_bytes(),password=None)
    pubblica=base64.b64encode(privata.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)).decode()
    if pubblica!=CHIAVE_PUBBLICA_ED25519_B64:raise ValueError('La chiave privata non corrisponde alla chiave pubblica dell’app')
    exe=cartella/'MagazzinoProfili.exe'
    if not exe.is_file() or not (cartella/'_internal').is_dir():raise ValueError('Distribuzione incompleta')
    files=[f for f in cartella.rglob('*') if f.is_file()]
    for f in files:
        if f.name.lower()=='config.toml' or f.suffix.lower() in ('.dump','.db','.sqlite','.sqlite3','.pem','.key'):
            raise ValueError('Dati o credenziali non pubblicabili nella distribuzione: '+f.name)
    destinazione.mkdir(parents=True)
    pacchetto=destinazione/f'MagazzinoProfili-{__version__}-windows-x64.zip'
    with zipfile.ZipFile(pacchetto,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for f in sorted(files):z.write(f,f.relative_to(cartella).as_posix())
    with pacchetto.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
    with exe.open('rb') as f:sha_exe=hashlib.file_digest(f,'sha256').hexdigest()
    dati=dict(versione=__version__,url_installer=f'https://github.com/Si2008/Magazzino/releases/download/v{__version__}/{pacchetto.name}',sha256=sha,
        sha256_eseguibile=sha_exe,dimensione=pacchetto.stat().st_size,pubblicato=datetime.now(timezone.utc).isoformat(),
        note='Commesse persistenti per cognome, colori originali, invio tra PC e aggiornamento completo.')
    dati['firma']=base64.b64encode(privata.sign(forma_canonica(dati))).decode()
    (destinazione/'manifest.json').write_text(json.dumps(dati,ensure_ascii=False,indent=2),encoding='utf-8')
    return pacchetto


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cartella',required=True);p.add_argument('--destinazione',required=True);p.add_argument('--chiave',required=True)
    a=p.parse_args();print(prepara(a.cartella,a.destinazione,a.chiave))
