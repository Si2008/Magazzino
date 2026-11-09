"""Associazione automatica per codice, anche per profili storici senza percorso salvato."""
from functools import lru_cache
from pathlib import Path
from .catalogo_immagini import CatalogoImmagini, cartella_catalogo, png_valido
from ..db.config import leggi_sezione


@lru_cache(maxsize=8)
def _catalogo(cartella):
    return CatalogoImmagini(Path(cartella))


@lru_cache(maxsize=1024)
def _leggibile(nome, modifica, dimensione):
    from PIL import Image
    try:
        with Image.open(nome) as immagine:
            if immagine.format != "PNG" or immagine.width * immagine.height > 25_000_000:
                return False
            immagine.verify()
        return True
    except (ValueError, OSError, Image.DecompressionBombError):
        return False


def _png_leggibile(percorso):
    try:
        stat = percorso.stat()
        return png_valido(percorso) and _leggibile(str(percorso), stat.st_mtime_ns, stat.st_size)
    except OSError:
        return False


def immagine_per_codice(codice):
    if not codice or not codice.strip():
        return None
    percorso = _catalogo(str(cartella_catalogo())).trova(codice)
    return percorso if percorso and _png_leggibile(percorso) else None


def immagine_del_profilo(profilo):
    """Il manuale valido prevale; altrimenti il catalogo compare senza editare il DB."""
    salvata = profilo.immagine_sezione
    if salvata:
        percorso = Path(salvata)
        if not percorso.is_absolute():
            _, base = leggi_sezione("immagini")
            percorso = base / percorso
        if _png_leggibile(percorso):
            return percorso
    return immagine_per_codice(profilo.codice)


@lru_cache(maxsize=8)
def _codici_indice(nome, modifica, dimensione):
    """Indice descrittivo originale, senza modificarlo né duplicare i PNG."""
    import csv
    with open(nome, encoding="utf-8-sig", newline="") as fonte:
        return frozenset((r.get("Codice") or "").strip().upper()
                         for r in csv.DictReader(fonte, delimiter=";"))


def dettaglio_immagine(profilo):
    """Percorso leggibile e diagnosi distinta per indice/PNG assente o non valido."""
    codice = (profilo.codice or "").strip().upper()
    percorso = immagine_del_profilo(profilo)
    indice = cartella_catalogo() / "Indice_profili_aggiornato.csv"
    codici = None
    errore_indice = ""
    try:
        stato = indice.stat()
        codici = _codici_indice(str(indice), stato.st_mtime_ns, stato.st_size)
    except FileNotFoundError:
        errore_indice = " Indice CSV non disponibile; ricerca per nome PNG."
    except (OSError, UnicodeError) as errore:
        import logging
        logging.getLogger(__name__).warning("Indice immagini non leggibile: %s", errore)
        errore_indice = " Indice CSV non leggibile; ricerca per nome PNG."
    if percorso:
        nota = "Sezione associata al profilo " + codice
        if codici is not None and codice not in codici:
            nota += ". PNG disponibile ma codice non presente nell’indice CSV."
        return percorso, nota + errore_indice
    if codici is not None and codice in codici:
        return None, f"{codice}: codice presente nell’indice, PNG mancante o illeggibile."
    return None, f"{codice}: immagine di sezione non disponibile." + errore_indice
