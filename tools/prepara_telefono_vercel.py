"""Prepara solo la pagina pubblica: nessun database o segreto viene copiato."""
import argparse
import json
from pathlib import Path
import shutil


def prepara(destinazione):
    radice=Path(__file__).resolve().parents[1]
    destinazione=Path(destinazione)
    if destinazione.exists():raise ValueError("Scegliere una destinazione nuova")
    destinazione.mkdir(parents=True)
    web=radice/'magazzino_profili/web'
    shutil.copy2(web/'templates/scansione.html',destinazione/'index.html')
    shutil.copytree(web/'static',destinazione/'static')
    shutil.copytree(web/'vercel/api',destinazione/'api')
    shutil.copy2(web/'vercel/package.json',destinazione/'package.json')
    config={'version':2,'headers':[
        {'source':'/(.*)','headers':[
            {'key':'X-Content-Type-Options','value':'nosniff'},
            {'key':'Referrer-Policy','value':'no-referrer'},
            {'key':'Permissions-Policy','value':'camera=(self)'},
            {'key':'Cache-Control','value':'no-store'}]}]}
    config['crons']=[{'path':'/api/ponte?modo=pulisci','schedule':'0 3 * * *'}]
    (destinazione/'vercel.json').write_text(json.dumps(config,indent=2),encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--destinazione',required=True)
    prepara(p.parse_args().destinazione)
