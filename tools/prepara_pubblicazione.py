"""Copia esplicita dei sorgenti pubblicabili in un checkout separato, senza dati utenti."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

RADICE=Path(__file__).resolve().parents[1]
ROOT_FILES={'.gitignore','.gitattributes','MagazzinoApp.py','MagazzinoProfili.spec','icona.ico','config.example.toml',
 'conftest.py','setup_database.py','importa_ods.py','README.md','requirements.txt','requirements.lock.txt',
 'package.json','vercel.json','magazzino-mockup-grande.html','anteprima-telefono.html'}
SUFFISSI={'.py','.mjs','.cjs','.js','.html','.css','.txt','.sql','.ps1','.md','.json','.cs','.bat','.iss'}
SEGRETI=[re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
         re.compile(r'gh[pousr]_[A-Za-z0-9]{30,}'),re.compile(r'AKIA[A-Z0-9]{16}')]


def file_pubblicabili():
    files={RADICE/p for p in ROOT_FILES if (RADICE/p).is_file()}
    for directory in ('magazzino_profili','migrations','tools','installer','api','public','catalogo_immagini','docs'):
        for p in (RADICE/directory).rglob('*'):
            if p.name=='PACCHETTO_SORGENTI_2.4.6.json':continue
            if not p.is_file() or any(x.startswith('.') or x=='__pycache__' for x in p.relative_to(RADICE/directory).parts):continue
            if directory=='catalogo_immagini':ok=p.suffix.lower() in ('.png','.csv')
            elif directory=='docs':ok=p.suffix.lower() in ('.md','.json','.css') or (p.suffix.lower()=='.png' and p.parent.name.startswith('schermate-spazi-'))
            else:ok=p.suffix.lower() in SUFFISSI
            if ok:files.add(p)
    return sorted(files)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkout',type=Path,required=True)
    a=parser.parse_args();dest=a.checkout.resolve()
    if dest==RADICE or not (dest/'.git').is_dir():raise SystemExit('Serve un checkout Git separato')
    remote=subprocess.check_output(['git','remote','get-url','origin'],cwd=dest,text=True).strip()
    if remote!='https://github.com/Si2008/Magazzino.git':raise SystemExit('Repository di destinazione diverso da Si2008/Magazzino')
    files=file_pubblicabili();impronte={}
    for p in files:
        if p.is_symlink() or p.is_junction():raise SystemExit('Collegamento escluso: '+str(p))
        if p.name=='config.toml' or p.suffix.lower() in ('.dump','.db','.pem','.key','.sqlite'):
            raise SystemExit('Dato non pubblicabile: '+str(p))
        if p.suffix.lower() not in ('.png','.ico'):
            testo=p.read_text(encoding='utf-8-sig')
            if any(r.search(testo) for r in SEGRETI):raise SystemExit('Possibile segreto, revisione necessaria: '+str(p.relative_to(RADICE)))
        rel=p.relative_to(RADICE);nuovo=dest/rel
        if not nuovo.resolve().is_relative_to(dest):raise SystemExit('Percorso esterno al checkout')
        nuovo.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,nuovo)
        impronte[rel.as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    # Riflette le sole rimozioni dei moduli applicativi gia eliminate nel sorgente.
    for nome in subprocess.check_output(['git','ls-files','magazzino_profili'],cwd=dest,text=True).splitlines():
        if not (RADICE/nome).exists():
            p=(dest/nome).resolve()
            if not p.is_relative_to(dest):raise SystemExit('Rimozione esterna al checkout')
            if p.is_file():p.unlink()
    manifest=RADICE/'docs/PACCHETTO_SORGENTI_2.4.6.json'
    manifest.write_text(json.dumps({'repository':remote,'file':impronte,
       'esclusi':['configurazioni reali','database e backup','chiavi private','Documenti personali','PDF commesse','cache e build','vecchi screenshot non attestati sintetici','script locali fuori dalla lista']},ensure_ascii=False,indent=2),encoding='utf-8')
    shutil.copy2(manifest,dest/'docs'/manifest.name)
    print('File copiati e controllati:',len(files))


if __name__=='__main__':main()
