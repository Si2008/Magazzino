import zipfile,xml.etree.ElementTree as ET,re,pathlib,csv
p=r'C:\Users\Simone\Desktop\SPEZZONI_pulito.ods'; root=ET.fromstring(zipfile.ZipFile(p).read('content.xml'))
ns={'table':'urn:oasis:names:tc:opendocument:xmlns:table:1.0','text':'urn:oasis:names:tc:opendocument:xmlns:text:1.0'}
codes=set()
for tab in root.findall('.//table:table',ns):
 name=tab.get('{urn:oasis:names:tc:opendocument:xmlns:table:1.0}name','')
 if name in ['Riepilogo','GUARNIZIONI']: continue
 for row in tab.findall('table:table-row',ns):
  cells=[]
  for c in row.findall('table:table-cell',ns):
   cells.append(''.join(t.text or '' for t in c.findall('.//text:p',ns)))
  if len(cells)>1 and cells[0].strip().upper() not in ['PROFILO',name.upper()]:
   code=cells[0].strip()
   if re.fullmatch(r'[A-Z]{1,4}\s?\d{2,6}[A-Z]?',code.upper()): codes.add(code.upper().replace(' ',''))
imgs={p.stem.upper() for p in pathlib.Path('Profili_cataloghi').glob('*.png') if not p.stem.startswith('_')}
print('codes',len(codes),'already',len(codes&imgs),'missing',len(codes-imgs))
print(', '.join(sorted(codes-imgs)))
