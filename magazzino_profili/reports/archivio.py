"""Archivio portabile delle anagrafiche, giacenze, storico e immagini.

Le credenziali non entrano in un documento condivisibile. Il dump PostgreSQL
separato resta il backup per utenti, impostazioni e code tecniche.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import hashlib
import zipfile
from io import BytesIO
from sqlalchemy import select
from ..domain import Profilo
from ..file_sicuri import destinazione_atomica
from .snapshot import sessione_snapshot
from .backup_excel import esporta_backup_logico_excel


def _leggi_immagine_validata(origine, codice):
    """Uno snapshot dei byte: verifica, ZIP e checksum usano lo stesso contenuto."""
    from PIL import Image
    try:
        with origine.open("rb") as file:
            contenuto = file.read(30_000_001)
        if len(contenuto) > 30_000_000:
            raise ValueError("dimensione superiore a 30 MB")
        with Image.open(BytesIO(contenuto)) as img:
            if img.format != "PNG" or img.width * img.height > 25_000_000:
                raise ValueError("richiesto PNG con massimo 25 milioni di pixel")
            img.verify()
    except (OSError, ValueError, Image.DecompressionBombError) as errore:
        raise ValueError(f"Immagine non valida per {codice}: archivio annullato ({errore})") from errore
    return contenuto


def esporta_archivio_dati(sessione, destinazione):
    with TemporaryDirectory(prefix="magazzino-archivio-") as tmp:
        cartella = Path(tmp)
        with sessione_snapshot(sessione) as lettura:
            # Il wrapper XLSX mantiene a sua volta uno snapshot: qui usa la stessa
            # connessione già in REPEATABLE READ per includere i riferimenti immagini.
            from .backup_excel import _esporta_backup_logico_excel
            xlsx = _esporta_backup_logico_excel(lettura, cartella / "dati.xlsx")
            profili = list(lettura.scalars(select(Profilo).order_by(Profilo.id)))
            with destinazione_atomica(destinazione) as provvisorio, zipfile.ZipFile(provvisorio, "w", zipfile.ZIP_DEFLATED) as z:
                z.write(xlsx, "dati.xlsx")
                manifest = {"versione": 1, "immagini": []}
                for profilo in profili:
                    from ..services.immagini import immagine_del_profilo
                    effettiva = immagine_del_profilo(profilo)
                    if not profilo.immagine_sezione and not effettiva:
                        continue
                    origine = effettiva or Path(profilo.immagine_sezione)
                    if not origine.is_file():
                        raise FileNotFoundError(f"Immagine mancante per {profilo.codice}: archivio annullato")
                    nome = f"sezioni/{profilo.id}.png"
                    contenuto = _leggi_immagine_validata(origine, profilo.codice)
                    z.writestr(nome, contenuto)
                    digest = hashlib.sha256(contenuto).hexdigest()
                    manifest["immagini"].append(dict(profilo_id=profilo.id, file=nome, sha256=digest))
                z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    return Path(destinazione)


def ripristina_archivio_dati(sessione, percorso, *, modalita, cartella_immagini=None):
    """Restore portabile: valida tutto prima di scrivere il DB, mai estrarre percorsi liberi."""
    from types import MappingProxyType
    from PIL import Image
    from ..db.config import leggi_sezione
    from ..file_sicuri import blocco_cartella
    from .backup_excel import BackupValidato, valida_backup_logico_excel, ripristina_backup_logico_excel
    if cartella_immagini is None:
        _, base = leggi_sezione("database")
        cartella_immagini = base / "immagini_sezioni"
    destinazione = Path(cartella_immagini).resolve()
    with TemporaryDirectory(prefix="magazzino-ripristino-") as tmp, zipfile.ZipFile(percorso) as z:
        info = z.infolist()
        nomi = [i.filename for i in info]
        if len(nomi) != len(set(nomi)) or not {"manifest.json", "dati.xlsx"}.issubset(nomi):
            raise ValueError("Archivio incompleto o con file duplicati")
        if sum(i.file_size for i in info) > 512 * 1024 * 1024 or len(info) > 10000:
            raise ValueError("Archivio troppo grande: limite 512 MB e 10000 file")
        if z.getinfo("manifest.json").file_size > 2_000_000:
            raise ValueError("Manifest troppo grande")
        manifest = json.loads(z.read("manifest.json"))
        if manifest.get("versione") != 1 or not isinstance(manifest.get("immagini"), list):
            raise ValueError("Versione archivio non supportata")
        xlsx = Path(tmp) / "dati.xlsx"
        xlsx.write_bytes(z.read("dati.xlsx"))
        backup = valida_backup_logico_excel(xlsx)
        ids = {r["id"] for r in backup.tabelle["Profili"]}
        immagini = {}
        for riga in manifest["immagini"]:
            id_ = riga["profilo_id"]
            nome = f"sezioni/{id_}.png"
            if type(id_) is not int or id_ not in ids or id_ in immagini or riga["file"] != nome:
                raise ValueError("Riferimento immagine non valido")
            if z.getinfo(nome).file_size > 30_000_000:
                raise ValueError("Immagine troppo grande")
            contenuto = z.read(nome)
            digest = hashlib.sha256(contenuto).hexdigest()
            if digest != riga["sha256"]:
                raise ValueError("Immagine modificata: checksum non valido")
            temporaneo = Path(tmp) / f"{id_}.png"
            temporaneo.write_bytes(contenuto)
            with Image.open(temporaneo) as img:
                if img.format != "PNG":
                    raise ValueError("Immagine non PNG")
                img.verify()
            immagini[id_] = (temporaneo, destinazione / f"{id_}-{digest}.png")
        for profilo in backup.tabelle["Profili"]:
            if profilo["immagine_sezione"] and profilo["id"] not in immagini:
                raise ValueError("L'archivio non contiene un'immagine referenziata")
        with blocco_cartella(destinazione):
            for origine, finale in immagini.values():
                if finale.exists():
                    if hashlib.sha256(finale.read_bytes()).hexdigest() != finale.stem.split("-")[-1]:
                        raise ValueError("Conflitto con un'immagine locale: ripristino annullato")
                else:
                    with destinazione_atomica(finale) as temporaneo:
                        temporaneo.write_bytes(origine.read_bytes())
        tabelle = dict(backup.tabelle)
        profili = []
        for originale in tabelle["Profili"]:
            riga = dict(originale)
            riga["immagine_sezione"] = str(immagini[riga["id"]][1]) if riga["id"] in immagini else None
            if riga["immagine_sezione"] and len(riga["immagine_sezione"]) > 512:
                raise ValueError("Percorso di ripristino immagini troppo lungo")
            profili.append(MappingProxyType(riga))
        tabelle["Profili"] = tuple(profili)
        ripristina_backup_logico_excel(sessione, BackupValidato(backup.versione, backup.esportato_il,
                                      MappingProxyType(tabelle), backup.soglia_scorta), modalita=modalita)
