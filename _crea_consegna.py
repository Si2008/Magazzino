import csv, re, shutil, zipfile, xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict
ods = Path(r'C:\Users\Simone\Desktop\SPEZZONI_pulito.ods')
src = Path(r'C:\Users\Simone\Desktop\magazzino\Profili_cataloghi')
out = src.parent / 'Profili_ritagliati'
out.mkdir(exist_ok=True)
ns={'table':'urn:oasis:names:tc:opendocument:xmlns:table:1.0','text':'urn:oasis:names:tc:opendocument:xmlns:text:1.0'}
root=ET.fromstring(zipfile.ZipFile(ods).read('content.xml'))
found=defaultdict(set); pat=re.compile(r'[A-Z]{1,4}\s?\d{2,6}[A-Z]?',re.I)
for tab in root.findall('.//table:table',ns):
    sheet=tab.get('{urn:oasis:names:tc:opendocument:xmlns:table:1.0}name','')
    if sheet in {'Riepilogo','GUARNIZIONI'}: continue
    for row in tab.findall('table:table-row',ns):
        cells=[''.join(t.text or '' for t in c.findall('.//text:p',ns)).strip() for c in row.findall('table:table-cell',ns)]
        if cells:
            val=cells[0].upper().replace(' ','')
            if pat.fullmatch(val): found[val].add(sheet)
existing={p.stem.upper():p for p in src.glob('*.png') if not p.stem.startswith('_')}
for code in sorted(found.keys() & existing.keys()): shutil.copy2(existing[code],out/f'{code}.png')
with (out/'Indice_profili.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.writer(f,delimiter=';'); w.writerow(['Codice','Stato immagine','Fogli ODS'])
    for code in sorted(found): w.writerow([code,'Ritaglio presente' if code in existing else 'Da estrarre/verificare',', '.join(sorted(found[code]))])
if (src/'Riepilogo.csv').exists(): shutil.copy2(src/'Riepilogo.csv',out/'Riepilogo_scansione_precedente.csv')
with (out/'LEGGIMI.txt').open('w',encoding='utf-8') as f:
    f.write('RITAGLI PROFILI DA SPEZZONI_pulito.ods\n')
    f.write('Fonte: cataloghi PDF in C:\\Users\\Simone\\Downloads e cartella Profili_cataloghi del progetto magazzino.\n\n')
    f.write(f'Codici strutturali univoci rilevati nei fogli profilo ODS: {len(found)}\nImmagini gia presenti e copiate qui: {len(found.keys() & existing.keys())}\nCodici senza immagine singola nella cartella progetto: {len(found.keys() - existing.keys())}\n\n')
    f.write('I PNG hanno il codice profilo come nome file. Indice_profili.csv elenca tutti i codici e i fogli ODS.\n')
    f.write('Le righe colore, le voci testuali e le guarnizioni non sono profili e non sono incluse. Per i codici senza PNG, il riepilogo precedente indicava che la sezione non era stata estratta con sicurezza: non sono stati creati ritagli ipotetici.\n')
