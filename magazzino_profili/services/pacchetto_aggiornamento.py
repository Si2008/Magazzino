"""Installazione completa ZIP firmato in una nuova cartella, mai sopra l'app in uso."""
from pathlib import Path,PurePosixPath
import zipfile,tempfile,hashlib,json,re


def installa_zip(manifest,origine,radice):
    from .aggiornamenti import ErroreAggiornamento
    atteso=(manifest.firmato or {}).get('sha256_eseguibile','')
    if not re.fullmatch('[0-9a-f]{64}',atteso):raise ErroreAggiornamento('Firma del pacchetto priva del checksum dell’eseguibile')
    radice=Path(radice);radice.mkdir(parents=True,exist_ok=True);finale=radice/manifest.versione
    try:
        with tempfile.TemporaryDirectory(prefix='.installazione-',dir=radice) as temp,zipfile.ZipFile(origine) as z:
            destinazione=Path(temp)/'app';destinazione.mkdir()
            if len(z.infolist())>10000 or sum(f.file_size for f in z.infolist())>1_000_000_000:
                raise ErroreAggiornamento('Pacchetto aggiornamento troppo grande')
            nomi=set()
            for f in z.infolist():
                p=PurePosixPath(f.filename)
                if p.is_absolute() or '..' in p.parts or '\\' in f.filename or ':' in f.filename or (f.external_attr>>16)&0o170000==0o120000:
                    raise ErroreAggiornamento('Percorso non consentito nel pacchetto aggiornamento')
                riservati={'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}
                if any(v.endswith((' ','.')) or v.split('.')[0].upper() in riservati for v in p.parts):
                    raise ErroreAggiornamento('Nome Windows non consentito nel pacchetto aggiornamento')
                if f.filename.casefold() in nomi:raise ErroreAggiornamento('File duplicato nel pacchetto aggiornamento')
                nomi.add(f.filename.casefold())
                z.extract(f,destinazione)
            exe=destinazione/'MagazzinoProfili.exe'
            if not exe.is_file() or not (destinazione/'_internal').is_dir() or not (destinazione/'catalogo_immagini').is_dir():
                raise ErroreAggiornamento('Pacchetto incompleto: mancano programma, librerie o immagini')
            with exe.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
            if digest!=atteso:raise ErroreAggiornamento('Eseguibile del pacchetto non corrisponde al manifest firmato')
            (destinazione/'manifest.json').write_text(json.dumps(manifest.firmato,ensure_ascii=False),encoding='utf-8')
            if finale.exists():
                precedente=finale/'manifest.json'
                if not precedente.is_file() or json.loads(precedente.read_text(encoding='utf-8'))!=manifest.firmato:
                    raise ErroreAggiornamento('Esiste già una diversa installazione di questa versione')
                with (finale/'MagazzinoProfili.exe').open('rb') as stream:
                    if hashlib.file_digest(stream,'sha256').hexdigest()!=atteso:raise ErroreAggiornamento('Installazione esistente alterata')
            else:destinazione.rename(finale)
        return finale/'MagazzinoProfili.exe'
    except (OSError,zipfile.BadZipFile) as e:
        raise ErroreAggiornamento('Installazione del pacchetto non riuscita: '+str(e)) from e
