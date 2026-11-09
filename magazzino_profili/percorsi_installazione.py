"""Dati e preferenze separati dall'installazione, senza modificare dati legacy."""
from pathlib import Path
import atexit
import json
import os
import re
import shutil
import sys
import tempfile
import tomllib

from .distribuzione import APP_ID, MUTEX_APPLICAZIONE

_mutex = None


def installata():
    if os.environ.get("MAGAZZINO_INSTALLATO") == "1":
        return True
    return bool(getattr(sys, "frozen", False) and
                (Path(sys.executable).parent / "installazione.json").is_file())


def cartella_dati():
    override = os.environ.get("MAGAZZINO_DATI")
    return Path(override).expanduser().resolve() if override else (
        Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "Magazzino Profili")


def dati_legacy():
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "magazzino_profili"


def dati_runtime():
    return cartella_dati() if installata() else dati_legacy()


def config_installata():
    return cartella_dati() / "config.toml"


def preferenze(organizzazione, applicazione):
    """Il costruttore QSettings(org, app) ignora setDefaultFormat: formato esplicito."""
    from PySide6.QtCore import QSettings
    isolata = os.environ.get("MAGAZZINO_PREFERENZE_TEST")
    if installata() or isolata:
        base = Path(isolata) if isolata else cartella_dati()/"preferenze"
        file = base/organizzazione/(applicazione+".ini")
        file.parent.mkdir(parents=True,exist_ok=True)
        return QSettings(str(file),QSettings.IniFormat)
    return QSettings(organizzazione,applicazione)


def _valore_toml(testo, sezione, chiave, valore):
    """Aggiorna una chiave di primo livello senza riscrivere credenziali/altri campi."""
    righe = testo.splitlines(keepends=True)
    inizio = next((i for i,r in enumerate(righe) if r.strip() == f"[{sezione}]"), None)
    nuova = chiave + " = " + json.dumps(str(valore), ensure_ascii=False) + "\n"
    if inizio is None:
        return testo.rstrip() + f"\n\n[{sezione}]\n" + nuova
    fine = next((i for i in range(inizio+1,len(righe)) if righe[i].lstrip().startswith("[")),len(righe))
    indice = next((i for i in range(inizio+1,fine) if re.match(r"\s*"+re.escape(chiave)+r"\s*=",righe[i])),None)
    if indice is None:
        righe.insert(inizio+1,nuova)
    else:
        righe[indice] = nuova
    return "".join(righe)


def importa_config(percorso):
    """Importazione esplicita: origine intatta, copia di sicurezza prima di sostituire il TOML locale."""
    from .db.config import leggi_config
    from .file_sicuri import destinazione_atomica
    origine = Path(percorso).expanduser().resolve()
    leggi_config(origine)
    destinazione = config_installata()
    if origine == destinazione:
        return destinazione
    testo = origine.read_text(encoding="utf-8")
    contenuto = tomllib.loads(testo)
    base = cartella_dati()
    base.mkdir(parents=True,exist_ok=True)
    # I percorsi di lettura del catalogo/certificati restano validi dopo lo spostamento.
    for sezione, chiave in (("immagini","catalogo"),("web","certificato_pem"),("web","chiave_privata"),("backup","pg_dump")):
        valore = contenuto.get(sezione,{}).get(chiave)
        if (sezione,chiave) == ("backup","pg_dump") and isinstance(valore,str) and not any(c in valore for c in ("/","\\")):
            continue  # Un nome di comando resta risolvibile tramite PATH.
        if isinstance(valore,str) and valore and not Path(valore).is_absolute():
            assoluto = (origine.parent/valore).resolve()
            if (sezione,chiave) == ("immagini","catalogo") and not assoluto.exists():
                assoluto = Path(sys.executable).resolve().parent / "catalogo_immagini"
            testo = _valore_toml(testo,sezione,chiave,assoluto)
    testo = _valore_toml(testo,"backup","cartella",base / "backup")
    # Gli upload vengono sempre scritti nella cartella dati, mai nel catalogo distribuito.
    old_images = origine.parent / "immagini_sezioni"
    if old_images.is_dir():
        for vecchia in old_images.glob("*.png"):
            nuova = base / "immagini_sezioni" / vecchia.name
            if nuova.exists():
                import hashlib
                if hashlib.sha256(nuova.read_bytes()).digest() != hashlib.sha256(vecchia.read_bytes()).digest():
                    raise FileExistsError("Immagine omonima già presente nei dati: importazione configurazione sospesa")
            else:
                nuova.parent.mkdir(parents=True,exist_ok=True)
                with destinazione_atomica(nuova) as temporaneo:
                    shutil.copyfile(vecchia,temporaneo)
    tomllib.loads(testo)
    if destinazione.exists():
        from uuid import uuid4
        shutil.copy2(destinazione,base / ("config-precedente-"+uuid4().hex+".toml"))
    with destinazione_atomica(destinazione) as temporaneo:
        temporaneo.write_text(testo,encoding="utf-8")
    return destinazione


def prepara_runtime(*, migra_preferenze=True, attiva_mutex=True):
    """Solo versione installata; nessuna modifica al registro o alla configurazione legacy."""
    global _mutex
    if not installata():
        return
    base = cartella_dati()
    applicazione = Path(sys.executable).resolve().parent
    if base.resolve().is_relative_to(applicazione):
        raise RuntimeError("La cartella dati deve essere separata dalla cartella del programma")
    base.mkdir(parents=True,exist_ok=True)
    marcatore = base / ".magazzino-profili-dati.json"
    if marcatore.exists() and json.loads(marcatore.read_text(encoding="utf-8")).get("app_id") != APP_ID:
        raise RuntimeError("Cartella dati appartenente a un altro programma")
    if not marcatore.exists():
        from .file_sicuri import destinazione_atomica
        with destinazione_atomica(marcatore) as tmp:
            tmp.write_text(json.dumps({"app_id":APP_ID}),encoding="utf-8")
    temporanei = base / "temporanei"
    temporanei.mkdir(exist_ok=True)
    tempfile.tempdir = str(temporanei)
    os.environ["TMP"] = os.environ["TEMP"] = str(temporanei)
    from PySide6.QtCore import QSettings
    precedente = os.environ.get("MAGAZZINO_CONFIG", "")
    migrazione = base / ".preferenze-migrate.json"
    if not migrazione.exists():
        for nome in (("Postazione","Desktop","MagazzinoProfili") if migra_preferenze else ()):
            vecchie = QSettings(QSettings.NativeFormat,QSettings.UserScope,"MagazzinoProfili",nome)
            nuove = QSettings(str(base / "preferenze" / "MagazzinoProfili" / (nome+".ini")),QSettings.IniFormat)
            for chiave in vecchie.allKeys():
                if not nuove.contains(chiave): nuove.setValue(chiave,vecchie.value(chiave))
            nuove.sync()
            if nuove.status() != QSettings.NoError:
                raise OSError("Impossibile salvare le preferenze nella cartella dati")
            if nome == "Postazione" and not precedente:
                precedente = str(vecchie.value("config_database", ""))
        # Mantiene l'archivio delle commesse secondarie senza spostare o
        # sovrascrivere documenti: database e binari PostgreSQL sono esclusi.
        vecchio = dati_legacy() / "commesse_secondario"
        if migra_preferenze and vecchio.is_dir():
            from .file_sicuri import destinazione_atomica
            for fonte in vecchio.rglob("*.json"):
                if fonte.is_symlink(): continue
                nuova = base / "commesse_secondario" / fonte.relative_to(vecchio)
                if not nuova.exists():
                    with destinazione_atomica(nuova) as tmp:
                        shutil.copyfile(fonte,tmp)
                elif nuova.read_bytes() != fonte.read_bytes():
                    raise FileExistsError("Commessa locale omonima differente: archivio originale conservato")
        from .file_sicuri import destinazione_atomica
        with destinazione_atomica(migrazione) as tmp:
            tmp.write_text(json.dumps({"app_id":APP_ID}),encoding="utf-8")
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat,QSettings.UserScope,str(base/"preferenze"))
    if not config_installata().exists() and precedente and Path(precedente).is_file():
        importa_config(precedente)
    os.environ["MAGAZZINO_CONFIG"] = str(config_installata())
    if os.name == "nt" and attiva_mutex and _mutex is None:
        import ctypes
        from ctypes import wintypes
        k = ctypes.WinDLL("kernel32",use_last_error=True)
        k.CreateMutexW.argtypes = (ctypes.c_void_p,wintypes.BOOL,wintypes.LPCWSTR)
        k.CreateMutexW.restype = ctypes.c_void_p
        _mutex = k.CreateMutexW(None,False,MUTEX_APPLICAZIONE)
        if not _mutex: raise OSError("Impossibile registrare l'istanza del Magazzino")
        atexit.register(lambda: k.CloseHandle(ctypes.c_void_p(_mutex)))
