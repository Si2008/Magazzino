"""Cartella LAN, coda locale persistente, pubblicazione atomica e ricevute."""
from pathlib import Path
import json
import re
from .archivio_commesse import documento,pacchetto,contenuto
from ..file_sicuri import blocco_cartella,destinazione_atomica


def cartelle(rete):
    root=Path(rete)
    if not str(rete).strip() or not root.is_dir():
        raise OSError('Cartella di rete non raggiungibile: controllare rete e PC principale. Le commesse locali restano salvate.')
    invii,ricevute=root/'commesse_in_arrivo',root/'ricevute_commesse'
    invii.mkdir(exist_ok=True);ricevute.mkdir(exist_ok=True)
    return invii,ricevute


def invia(archivio,rete):
    invii,ricevute=cartelle(rete);esiti=[]
    with blocco_cartella(invii,attendi=False):
        for doc in archivio.elenco():
            ricevuta=ricevute/(doc.impronta+'.json')
            if ricevuta.exists():
                r=json.loads(ricevuta.read_text(encoding='utf-8'))
                if r.get('stato')!='rifiutata':
                    esiti.append(f'{doc.cognome}: {r.get("stato","ricevuta non valida")}');continue
                with destinazione_atomica(invii/(doc.impronta+'.json')) as tmp:tmp.write_bytes(pacchetto(doc))
                ricevuta.unlink()
                esiti.append(f'{doc.cognome}: invio precedente rifiutato ({r.get("motivo","")}); reinviato, in attesa di accettazione')
                continue
            finale=invii/(doc.impronta+'.json')
            if finale.exists():
                if contenuto(documento(finale.read_bytes()))!=contenuto(doc):raise ValueError('La coda contiene una diversa commessa con la stessa identità')
            else:
                with destinazione_atomica(finale) as tmp:tmp.write_bytes(pacchetto(doc))
            esiti.append(f'{doc.cognome}: inviato, in attesa di accettazione sul principale')
    return esiti


def da_ricevere(rete):
    invii,ricevute=cartelle(rete)
    risultati=[]
    for p in sorted(invii.glob('*.json')):
        r=ricevute/p.name
        if not r.exists() or json.loads(r.read_text(encoding='utf-8')).get('stato','').startswith('in attesa'):
            risultati.append(p)
            if len(risultati)==100:break
    return risultati


def conferma(rete,doc,stato):
    _,ricevute=cartelle(rete)
    with destinazione_atomica(ricevute/(doc.impronta+'.json')) as tmp:
        tmp.write_text(json.dumps({'identita':doc.impronta,'stato':stato},ensure_ascii=False),encoding='utf-8')


def rifiuta(rete,nome,motivo):
    if not re.fullmatch(r'[0-9a-f]{64}\.json',nome):return
    _,ricevute=cartelle(rete)
    with destinazione_atomica(ricevute/nome) as tmp:
        tmp.write_text(json.dumps({'identita':nome[:-5],'stato':'rifiutata','motivo':str(motivo)},ensure_ascii=False),encoding='utf-8')
