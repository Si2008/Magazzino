"""Lettura locale PDF Blitz: testo + OCR Windows delle quote raster, con revisione."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from dataclasses import asdict
from pathlib import Path
import json
import os
import re
import subprocess
import tempfile
import hashlib

from .commesse import RichiestaTaglio, decimi


@dataclass
class DocumentoCommessa:
    nome: str
    righe: list[RichiestaTaglio]
    avvisi: list[str] = field(default_factory=list)
    barre_originali: int = 0
    cognome: str = ''
    impronta: str = ''


def estrai_cognome(testo):
    for etichetta in (r'Cognome\s*:', r'Rif(?:erimento)?(?:\.|\s*:)' ):
        m = re.search(r'(?im)\b'+etichetta+r'[^\S\r\n]*([^\r\n]*)', testo)
        if m and not m[1].strip():raise ValueError('Commessa rifiutata: cognome vuoto')
        if m and m[1].strip():
            valore = m[1].strip()
            if len(valore)>200: raise ValueError('Cognome troppo lungo nella commessa')
            return valore
    raise ValueError('Commessa rifiutata: cognome mancante o vuoto (campo Cognome o Rif.)')


def pulisci_quota(immagine, riga):
    """Formato Blitz 1200 px: isolare quote e togliere bordi connessi lunghi."""
    from PIL import ImageOps
    top = riga * 63
    fascia = immagine.convert('L').crop((0, top+29, 1200, top+52))
    pix = fascia.load()
    for x in range(1200):
        if sum(pix[x,y] < 160 for y in range(23)) >= 22:
            for y in range(23):
                pix[x,y] = 255
    punti = {(x,y) for y in range(23) for x in range(1200) if pix[x,y] < 180}
    while punti:
        p = punti.pop(); pila = [p]; componente = [p]
        while pila:
            x,y = pila.pop()
            for vicino in ((x-1,y),(x+1,y),(x,y-1),(x,y+1),(x-1,y-1),(x+1,y-1),(x-1,y+1),(x+1,y+1)):
                if vicino in punti:
                    punti.remove(vicino); pila.append(vicino); componente.append(vicino)
        ascisse = [x for x,y in componente]
        if max(ascisse)-min(ascisse) > 18:
            for x,y in componente:
                pix[x,y] = 255
    return ImageOps.expand(fascia.resize((3600,69)), 30, 255).convert('RGB')


def esegui_ocr(cartella):
    if os.name != 'nt':
        raise RuntimeError('OCR locale disponibile su Windows 10/11; inserire o correggere le misure manualmente')
    powershell = Path(os.environ.get('WINDIR', 'C:/Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe'
    risultato = subprocess.run([str(powershell), '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
        '-File', str(Path(__file__).with_name('ocr_commessa.ps1')), '-Cartella', str(cartella)],
        capture_output=True, timeout=120, creationflags=subprocess.CREATE_NO_WINDOW)
    if risultato.returncode:
        raise RuntimeError('OCR Windows non disponibile o lingua OCR mancante. Puoi usare le barre intere o inserire i tagli manualmente.')
    return {r['file']: r['testo'] for r in json.loads(risultato.stdout.decode('utf-8-sig'))}


def quote_da_testo(testo):
    testo = re.sub(r'(?<=\d)[.,]\s+(?=\d\b)', '.', testo).replace('_', ' ').strip()
    if not testo or re.search(r'[^\d.,\s]', testo):
        raise ValueError('Quote OCR non riconosciute')
    return [decimi(t) for t in testo.split()]


def leggi_commessa_pdf(percorso, *, riconoscitore=esegui_ocr):
    from pypdf import PdfReader
    percorso = Path(percorso)
    if not percorso.is_file() or percorso.stat().st_size > 30_000_000:
        raise ValueError('Scegliere un PDF esistente, massimo 30 MB')
    lettore = PdfReader(percorso)
    if lettore.is_encrypted:
        raise ValueError('Il PDF è protetto: usare una copia non protetta')
    if not 1 <= len(lettore.pages) <= 100:
        raise ValueError('Il PDF deve contenere da 1 a 100 pagine')
    intestazione=lettore.pages[0].extract_text() or ''
    cognome = estrai_cognome(intestazione)
    ordine=re.search(r'(?im)^Ordine\s*:[^\S\r\n]*([^\r\n]*)',intestazione)
    ordine=' '.join(ordine[1].casefold().split()) if ordine else ''
    avvisi, blocchi, barre = [], [], []
    corrente, attivo, attendi, pendente = None, False, None, None
    with tempfile.TemporaryDirectory(prefix='magazzino-commessa-') as temporanea:
        cartella = Path(temporanea)
        immagini_salvate = {}
        for pagina_n, pagina in enumerate(lettore.pages, 1):
            eventi = []
            def testo(t, *_):
                if t.strip(): eventi.append(('testo', t.strip()))
            def operazione(op, argomenti, *_):
                if op == b'Do': eventi.append(('immagine', str(argomenti[0])))
            pagina.extract_text(visitor_text=testo, visitor_operand_before=operazione)
            for tipo, valore in eventi:
                if tipo == 'testo':
                    if 'LISTA OTTIMIZZATA' in valore.upper(): attivo = True
                    if not attivo: continue
                    if valore == 'Profilo': attendi = 'profilo'; continue
                    if attendi == 'profilo':
                        corrente = dict(profilo=valore, colore='', attese=None)
                        blocchi.append(corrente); attendi = None; continue
                    if valore == 'Colore': attendi = 'colore'; continue
                    if attendi == 'colore' and corrente is not None:
                        if valore in ('Qt. Sp.','Profilo','Colore'):
                            raise ValueError('Commessa rifiutata: colore mancante nel documento')
                        corrente['colore'] = valore; attendi = None; continue
                    quantita = re.fullmatch(r'(\d+)\s+Ut\.', valore)
                    if quantita and corrente is not None:
                        corrente['attese'] = int(quantita[1])
                    elif pendente is not None and re.fullmatch(r'\d+(?:[.,]\d+)?', valore):
                        pendente['numeri'].append(decimi(valore))
                        if len(pendente['numeri']) == 2: pendente = None
                elif attivo and corrente and corrente['colore']:
                    # Non interpretare loghi, disegni delle sezioni o pagine scannerizzate.
                    immagine = pagina.images[valore].image
                    if immagine.width != 1200 or immagine.height not in (56,119): continue
                    chiave = f'{pagina_n}_{valore[1:]}'
                    if chiave not in immagini_salvate:
                        nomi = []
                        for riga in range(1 if immagine.height == 56 else 2):
                            nome = f'{chiave}_{riga}.png'; nomi.append(nome)
                            pulisci_quota(immagine, riga).save(cartella/nome)
                        immagini_salvate[chiave] = nomi
                    pendente = dict(blocco=corrente, numeri=[], immagini=immagini_salvate[chiave], pagina=pagina_n)
                    barre.append(pendente)
                    if len(barre) > 1000: raise ValueError('Troppi diagrammi: suddividere la commessa (massimo 1000 barre)')
        if not barre:
            raise ValueError('Formato PDF non riconosciuto: serve la Lista ottimizzata Blitz con testo. Puoi inserire le righe manualmente.')
        for blocco in blocchi:
            trovate = sum(b['blocco'] is blocco for b in barre)
            if blocco['attese'] is None or trovate != blocco['attese']:
                raise ValueError(f"{blocco['profilo']}: barre lette {trovate}, dichiarate {blocco['attese']}. Importazione interrotta per evitare righe mancanti.")
        try:
            letture = riconoscitore(cartella)
        except (RuntimeError, OSError, subprocess.TimeoutExpired, ValueError) as errore:
            raise ValueError('Commessa non importata: '+str(errore)) from errore
        richieste = []
        non_lette = 0
        for n, barra in enumerate(barre, 1):
            if len(barra['numeri']) != 2:
                raise ValueError(f'Barra {n}: lunghezza originale/utilizzata non leggibile; importazione interrotta')
            base, usato = barra['numeri']
            codice, colore = barra['blocco']['profilo'], barra['blocco']['colore']
            riferimento = f'Pagina {barra["pagina"]}, barra {n}'
            try:
                quote = [q for nome in barra['immagini'] for q in quote_da_testo(letture.get(nome,''))]
                # Coerenza con la lunghezza utilizzata stampata: niente correzioni indovinate.
                if not quote or sum(quote) > usato+20 or usato-sum(quote) > len(quote)*300+100 or usato > base:
                    raise ValueError('Somma quote incoerente')
                richieste.extend(RichiestaTaglio(codice, colore, q, 1, riferimento) for q in quote)
            except ValueError:
                raise ValueError(f'Commessa non importata: misure non affidabili, {riferimento}, profilo {codice}. Verificare il PDF.') from None
        if non_lette:
            avvisi.append(f'{non_lette} barre con quote non affidabili: viene richiesta la barra originale intera. Correggere le misure per cercare pezzi più corti.')
        avvisi.append('Controllare tutte le misure lette dal PDF, inclusi decimali e quantità.')
        # Non moltiplicare per le quantità dell'abaco: i diagrammi sono già ripetuti.
        conteggi = Counter((r.profilo,r.colore,r.lunghezza,r.barra_intera) for r in richieste)
        righe = [RichiestaTaglio(p,c,l,n,'Lista ottimizzata PDF',b) for (p,c,l,b),n in sorted(conteggi.items())]
        # I metadati PDF e il nome del file non devono creare duplicati.
        impronta=hashlib.sha256(json.dumps([cognome.casefold(),ordine,[asdict(r) for r in righe]],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        return DocumentoCommessa(percorso.stem, righe, avvisi, len(barre), cognome, impronta)
