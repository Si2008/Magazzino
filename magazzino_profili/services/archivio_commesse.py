"""Identità stabile, archivio ufficiale e formato di scambio delle commesse."""
from dataclasses import asdict
from pathlib import Path
import hashlib
import json
import re
import unicodedata
from sqlalchemy import select, text
from ..domain import Commessa, RigaCommessa, AssegnazioneCommessa, Pezzo
from .commesse import RichiestaTaglio, MAX_TAGLI
from .lettura_commessa import DocumentoCommessa
from ..db.normalizzazione import normalizza_codice,normalizza_colore


class CognomePresente(ValueError):
    pass


def chiave_cognome(cognome):
    if not isinstance(cognome,str) or not cognome.strip() or len(cognome)>200 or any(ord(c)<32 for c in cognome):
        raise ValueError('Commessa rifiutata: cognome mancante, vuoto o non valido')
    return ' '.join(unicodedata.normalize('NFKC',cognome).casefold().split())


def pacchetto(doc):
    chiave_cognome(doc.cognome)
    if not isinstance(doc.nome,str) or not 1<=len(doc.nome)<=250:
        raise ValueError('Nome commessa non valido')
    if not doc.righe or len(doc.righe)>1000 or sum(r.quantita for r in doc.righe)>MAX_TAGLI:
        raise ValueError('Commessa vuota o troppo grande (massimo 1000 misure e 10000 pezzi)')
    if not re.fullmatch(r'[0-9a-f]{64}',doc.impronta or ''):
        raise ValueError('Identità del documento assente: reimportare il PDF originale')
    corpo=dict(formato=1,identita=doc.impronta,cognome=doc.cognome,nome=doc.nome,
               righe=[asdict(r) for r in doc.righe])
    dati=json.dumps(corpo,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
    if len(dati)>2_000_000: raise ValueError('Commessa troppo grande per lo scambio')
    return dati


def documento(dati):
    if len(dati)>2_000_000: raise ValueError('File commessa troppo grande')
    try:
        p=json.loads(dati)
        if not isinstance(p,dict) or type(p.get('formato')) is not int or p['formato']!=1:
            raise ValueError('Formato commessa non supportato: file mantenuto senza modifiche')
        righe=[RichiestaTaglio(**r) for r in p['righe']]
        doc=DocumentoCommessa(p['nome'],righe,[],0,p['cognome'],p['identita'])
        pacchetto(doc)
        return doc
    except (KeyError,TypeError,json.JSONDecodeError,UnicodeDecodeError,RecursionError) as e:
        raise ValueError('Commessa malformata o incompleta: nessun dato importato') from e


def leggi_file(percorso):
    with Path(percorso).open('rb') as f:return documento(f.read(2_000_001))


def contenuto(doc):
    # Il nome del file può cambiare senza cambiare l'identità del PDF.
    return (chiave_cognome(doc.cognome),[asdict(r) for r in doc.righe])


def elenco(factory):
    with factory() as s:
        return list(s.scalars(select(Commessa).order_by(Commessa.cognome_chiave,Commessa.id)))


def carica(factory,identita):
    with factory() as s:
        c=s.scalar(select(Commessa).where(Commessa.identita==identita))
        if c is None: raise ValueError('Commessa non trovata')
        righe=list(s.scalars(select(RigaCommessa).where(RigaCommessa.commessa_id==c.id).order_by(RigaCommessa.id)))
        return DocumentoCommessa(c.nome,[RichiestaTaglio(r.profilo,r.colore,r.lunghezza,r.quantita,r.riferimento,r.barra_intera) for r in righe],[],0,c.cognome,c.identita)


def importa(factory,doc,*,accetta_omonimo=False):
    documento(pacchetto(doc))  # validare tutto prima di aprire una transazione
    chiave=chiave_cognome(doc.cognome)
    with factory() as s,s.begin():
        if s.get_bind().dialect.name=='postgresql':
            locks=sorted({int.from_bytes(hashlib.sha256(k.encode()).digest()[:8],'big',signed=True) for k in [chiave,doc.impronta]})
            for k in locks:s.execute(text('SELECT pg_advisory_xact_lock(:id)'),{'id':k})
        precedente=s.scalar(select(Commessa).where(Commessa.identita==doc.impronta))
        if precedente:
            righe=list(s.scalars(select(RigaCommessa).where(RigaCommessa.commessa_id==precedente.id).order_by(RigaCommessa.id)))
            prima=DocumentoCommessa(precedente.nome,[RichiestaTaglio(r.profilo,r.colore,r.lunghezza,r.quantita,r.riferimento,r.barra_intera) for r in righe],cognome=precedente.cognome,impronta=precedente.identita)
            if contenuto(prima)!=contenuto(doc):raise ValueError('Identità già presente con contenuto diverso: importazione rifiutata')
            return precedente,False
        if not accetta_omonimo and s.scalar(select(Commessa.id).where(Commessa.cognome_chiave==chiave).limit(1)):
            raise CognomePresente(f'Esiste già una commessa per {doc.cognome}. Aggiungere questo documento distinto nello stesso gruppo?')
        c=Commessa(identita=doc.impronta,cognome=doc.cognome,cognome_chiave=chiave,nome=doc.nome)
        s.add(c);s.flush()
        s.add_all([RigaCommessa(commessa_id=c.id,**asdict(r)) for r in doc.righe])
        return c,True


def nomi_per_pezzi(sessione,ids):
    ids=list(ids)
    if not ids:return {}
    return dict(sessione.execute(select(AssegnazioneCommessa.pezzo_id,Commessa.cognome)
        .join(Commessa,Commessa.id==AssegnazioneCommessa.commessa_id)
        .where(AssegnazioneCommessa.pezzo_id.in_(ids))).all())


def assegna_in_transazione(sessione,commessa_id,pezzi):
    c=sessione.get(Commessa,commessa_id)
    if c is None:raise ValueError('Commessa non trovata')
    ids=[p.id for p in pezzi]
    sessione.execute(select(Pezzo.id).where(Pezzo.id.in_(ids)).order_by(Pezzo.id).with_for_update()).all()
    attuali=dict(sessione.execute(select(AssegnazioneCommessa.pezzo_id,AssegnazioneCommessa.commessa_id).where(AssegnazioneCommessa.pezzo_id.in_(ids))).all())
    righe=list(sessione.scalars(select(RigaCommessa).where(RigaCommessa.commessa_id==commessa_id)))
    richieste={(normalizza_codice(r.profilo),normalizza_colore(r.colore)) for r in righe}
    from .commesse import colori_esatti
    colori=colori_esatti(sessione,righe)
    for pezzo in pezzi:
        if (pezzo.profilo.codice,normalizza_colore(colori.get(pezzo.colore.codice_normalizzato,''))) not in richieste:
            raise ValueError('Profilo o colore del pezzo non presente nella commessa')
        attuale=attuali.get(pezzo.id)
        if attuale and attuale!=commessa_id:
            raise ValueError(f'Il pezzo {pezzo.barcode} appartiene già a un’altra commessa')
        if not attuale:sessione.add(AssegnazioneCommessa(commessa_id=commessa_id,pezzo_id=pezzo.id))


def assegna_piano(factory,identita,piano):
    if piano.mancanti:raise ValueError('La commessa ha misure mancanti: completare il piano prima di associare')
    ids=[]
    for p in piano.prelievi:
        if not p.materiale.chiave.startswith('pezzo:'):raise ValueError('Etichettare gli spezzoni storici prima di associarli')
        ids.append(int(p.materiale.chiave.split(':')[1]))
    with factory() as s,s.begin():
        c=s.scalar(select(Commessa).where(Commessa.identita==identita))
        if c is None:raise ValueError('Salvare prima la commessa')
        pezzi=list(s.scalars(select(Pezzo).where(Pezzo.id.in_(ids)).order_by(Pezzo.id).with_for_update()))
        if len(pezzi)!=len(ids) or any(p.quantita!=1 or p.stato!='Caricato' or p.eliminato_il for p in pezzi):
            raise ValueError('Disponibilità cambiata: ricalcolare la lista di prelievo')
        assegna_in_transazione(s,c.id,pezzi)


class ArchivioLocale:
    """Copia di lavoro secondaria; non contiene né modifica il magazzino."""
    def __init__(self,cartella):
        self.cartella=Path(cartella)

    def elenco(self):
        if not self.cartella.exists():return []
        return [leggi_file(p) for p in sorted(self.cartella.glob('*.json'))]

    def salva(self,doc,*,accetta_omonimo=False):
        from ..file_sicuri import blocco_cartella,destinazione_atomica
        dati=pacchetto(doc)
        with blocco_cartella(self.cartella):
            finale=self.cartella/(doc.impronta+'.json')
            if finale.exists():
                if contenuto(documento(finale.read_bytes()))!=contenuto(doc):raise ValueError('Identità locale già presente con dati diversi')
                return False
            if not accetta_omonimo and any(chiave_cognome(d.cognome)==chiave_cognome(doc.cognome) for d in self.elenco()):
                raise CognomePresente(f'Esiste già {doc.cognome}: aggiungere la nuova commessa distinta allo stesso gruppo?')
            with destinazione_atomica(finale) as tmp:tmp.write_bytes(dati)
        return True
