"""Piani di prelievo in sola lettura: nessuna prenotazione o movimento implicito."""
from __future__ import annotations

from collections import Counter, defaultdict
from bisect import bisect_left, insort
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone

from sqlalchemy import select
from ..db.normalizzazione import normalizza_codice, normalizza_colore
from ..domain import Pezzo, Profilo, Colore, Spezzone

MAX_TAGLI = 10000


def decimi(valore) -> int:
    """Millimetri, con al massimo una cifra decimale. Mai float nei calcoli."""
    try:
        n = Decimal(str(valore).strip().replace(',', '.')) * 10
        if not n.is_finite() or n != n.to_integral_value() or not 0 < n <= 1000000:
            raise ValueError
        return int(n)
    except (InvalidOperation, ValueError):
        raise ValueError('Misura non valida: usa millimetri positivi, massimo un decimale') from None


def misura(n: int) -> str:
    return str(n // 10) if n % 10 == 0 else f'{n // 10},{n % 10}'


@dataclass(frozen=True)
class RichiestaTaglio:
    profilo: str
    colore: str
    lunghezza: int  # decimi di mm
    quantita: int
    riferimento: str = ''
    barra_intera: bool = False

    def __post_init__(self):
        if not isinstance(self.profilo, str) or not isinstance(self.colore, str):
            raise ValueError('Profilo e colore devono essere testi')
        if not self.profilo or not self.colore or len(self.profilo) > 128 or len(self.colore) > 128:
            raise ValueError('Profilo e colore sono obbligatori (massimo 128 caratteri)')
        if not self.profilo.strip() or not self.colore.strip() or any(ord(c)<32 for c in self.profilo+self.colore):
            raise ValueError('Profilo o colore vuoto o con caratteri di controllo')
        if type(self.lunghezza) is not int or not 0 < self.lunghezza <= 1000000:
            raise ValueError('Lunghezza non valida')
        if type(self.quantita) is not int or not 1 <= self.quantita <= MAX_TAGLI:
            raise ValueError('Quantità non valida: da 1 a 10000')
        if type(self.barra_intera) is not bool:
            raise ValueError('Tipo di richiesta non valido')
        if not isinstance(self.riferimento,str) or len(self.riferimento)>500:
            raise ValueError('Riferimento della riga non valido o troppo lungo')


@dataclass(frozen=True)
class Materiale:
    chiave: str
    profilo: str
    colore: str
    lunghezza: int
    barcode: str
    vassoio: str
    ubicazione: str
    nota: str = ''


@dataclass
class Prelievo:
    materiale: Materiale
    tagli: list[RichiestaTaglio] = field(default_factory=list)
    residuo: int = 0
    chiuso: bool = False


@dataclass
class PianoPrelievo:
    prelievi: list[Prelievo]
    mancanti: list[RichiestaTaglio]
    avvisi: list[str]
    calcolato_il: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def pianifica(righe, materiali, *, consenti_pezzi_lunghi=True):
    """Best fit decrescente. Proposta euristica, non ottimo matematico garantito.

    Confronto delle sole lunghezze nominali; nessun parametro di lavorazione.
    Un pezzo esatto viene assegnato interamente a quella richiesta.
    """
    if not righe or sum(r.quantita for r in righe) > MAX_TAGLI:
        raise ValueError('Inserire da 1 a 10000 pezzi richiesti')
    gruppi = defaultdict(list)
    chiavi = set()
    for m in materiali:
        if m.chiave in chiavi:
            raise ValueError('Materiale duplicato nel piano')
        chiavi.add(m.chiave)
        gruppi[normalizza_codice(m.profilo), normalizza_colore(m.colore)].append(m)
    richieste = defaultdict(list)
    for r in righe:
        richieste[normalizza_codice(r.profilo), normalizza_colore(r.colore)].extend([r] * r.quantita)
    prelievi, mancanti = [], []
    for gruppo, richieste_gruppo in sorted(richieste.items()):
        disponibili = sorted(gruppi[gruppo], key=lambda m: (m.lunghezza, m.chiave))
        lunghezze = [m.lunghezza for m in disponibili]
        aperti = []
        residui = []
        for r in sorted(richieste_gruppo, key=lambda r: (-r.lunghezza, not r.barra_intera, r.riferimento)):
            costo = r.lunghezza
            indice_residuo = bisect_left(residui, (costo, -1))
            if indice_residuo < len(residui) and consenti_pezzi_lunghi and not r.barra_intera:
                _, indice = residui.pop(indice_residuo)
                p = aperti[indice]
                p.tagli.append(r); p.residuo -= costo
                insort(residui, (p.residuo, indice))
                continue
            scelta = bisect_left(lunghezze, r.lunghezza)
            esatto = scelta < len(lunghezze) and lunghezze[scelta] == r.lunghezza
            if not esatto and consenti_pezzi_lunghi:
                scelta = bisect_left(lunghezze, r.lunghezza)
            if scelta >= len(disponibili) or (not consenti_pezzi_lunghi and not esatto):
                mancanti.append(r); continue
            m = disponibili.pop(scelta)
            lunghezze.pop(scelta)
            intero = r.barra_intera or not consenti_pezzi_lunghi or m.lunghezza == r.lunghezza
            p = Prelievo(m, [r], 0 if intero else m.lunghezza - costo, intero)
            aperti.append(p); prelievi.append(p)
            if not intero:
                insort(residui, (p.residuo, len(aperti)-1))
    conteggi = Counter((r.profilo, r.colore, r.lunghezza, r.riferimento, r.barra_intera) for r in mancanti)
    assenti = [RichiestaTaglio(a,b,c,n,d + (' · Nessun materiale disponibile per profilo/finitura' if not gruppi[a,b]
        else ' · Disponibilità insufficiente per quantità e misure richieste'),e) for (a,b,c,d,e),n in conteggi.items()]
    return PianoPrelievo(sorted(prelievi, key=lambda p: (p.materiale.vassoio, p.materiale.profilo, p.materiale.chiave)), assenti, [
        'Proposta non prenotata: aggiorna il piano prima del prelievo. Nessuna giacenza è stata modificata.',
        'Scelta basata sulle misure nominali della commessa e dei pezzi disponibili. Nessun calcolo di lavorazione.'])


def colori_esatti(sessione,righe):
    """Solo codice o nome esatto; nessuna approssimazione RAL e nessuna scelta utente."""
    richiesti={normalizza_colore(r.colore):r.colore for r in righe}
    candidati={k:[] for k in richiesti}
    for c in sessione.scalars(select(Colore)):
        for k in richiesti:
            if k in (normalizza_colore(c.codice_normalizzato),normalizza_colore(c.nome_visualizzato)):
                candidati[k].append(c.codice_normalizzato)
    inverso={}
    for k,codici in candidati.items():
        if len(codici)==1:inverso.setdefault(codici[0],[]).append(richiesti[k])
    return {c:nomi[0] for c,nomi in inverso.items() if len(nomi)==1}


def calcola_prelievo(sessione, righe, *, includi_spezzoni=True, commessa_id=None, **opzioni):
    """Query limitate ai profili richiesti; sessione del chiamante, nessuna scrittura."""
    codici = sorted({normalizza_codice(r.profilo) for r in righe})
    if not codici or len(codici) > 500:
        raise ValueError('La commessa deve contenere da 1 a 500 codici profilo')
    materiali, avvisi = [], []
    corrispondenze=colori_esatti(sessione,righe)
    query = (select(Pezzo.id, Profilo.codice, Colore.codice_normalizzato, Pezzo.lunghezza_mm,
        Pezzo.barcode, Pezzo.numero_vassoio, Pezzo.ubicazione, Pezzo.unitario, Pezzo.quantita)
        .join(Profilo, Pezzo.profilo_id == Profilo.id).join(Colore, Pezzo.colore_id == Colore.id)
        .where(Profilo.codice.in_(codici), Pezzo.eliminato_il.is_(None), Pezzo.quantita > 0,
               Pezzo.stato == 'Caricato').order_by(Pezzo.id))
    legacy = 0
    from ..domain import AssegnazioneCommessa
    riservati=dict(sessione.execute(select(AssegnazioneCommessa.pezzo_id,AssegnazioneCommessa.commessa_id)
        .join(Pezzo,Pezzo.id==AssegnazioneCommessa.pezzo_id).join(Profilo,Profilo.id==Pezzo.profilo_id)
        .where(Profilo.codice.in_(codici))).all())
    for row in sessione.execute(query.execution_options(yield_per=500)):
        ident, profilo, colore, lunghezza, barcode, vassoio, ubicazione, unitario, quantita = row
        if colore not in corrispondenze:continue
        colore=corrispondenze[colore]
        if ident in riservati and riservati[ident]!=commessa_id:continue
        if not unitario or quantita != 1:
            legacy += 1; continue
        materiali.append(Materiale(f'pezzo:{ident}', profilo, colore, lunghezza*10,
            barcode, vassoio or 'Non indicato', ubicazione or ''))
        if len(materiali) > 50000:
            raise ValueError('Troppi pezzi candidati (oltre 50000): suddividere la commessa')
    if legacy:
        avvisi.append(f'{legacy} giacenze aggregate escluse: convertirle in pezzi singoli per un prelievo univoco.')
    if includi_spezzoni:
        q = (select(Spezzone.id, Profilo.codice, Colore.codice_normalizzato, Spezzone.lunghezza_mm,
            Pezzo.barcode, Pezzo.numero_vassoio, Pezzo.ubicazione)
            .join(Pezzo, Spezzone.pezzo_origine_id == Pezzo.id)
            .join(Profilo, Pezzo.profilo_id == Profilo.id).join(Colore, Pezzo.colore_id == Colore.id)
            .where(Profilo.codice.in_(codici), Spezzone.utilizzato.is_(False), Pezzo.quantita == 0)
            .order_by(Spezzone.id))
        for ident, profilo, colore, lunghezza, barcode, vassoio, ubicazione in sessione.execute(q.execution_options(yield_per=500)):
            if colore not in corrispondenze:continue
            colore=corrispondenze[colore]
            materiali.append(Materiale(f'spezzone:{ident}', profilo, colore, lunghezza*10,
                f'SPEZZONE #{ident}', 'Da confermare', ubicazione or '',
                f'Spezzone storico senza etichetta propria; origine {barcode}, vassoio origine {vassoio or "non indicato"}. Verificare la posizione.'))
            if len(materiali) > 50000:
                raise ValueError('Troppi pezzi candidati: suddividere la commessa')
    piano = pianifica(righe, materiali, **opzioni)
    piano.avvisi.extend(avvisi)
    if any(p.materiale.nota for p in piano.prelievi):
        piano.avvisi.append('Gli spezzoni storici non hanno un barcode proprio né un vassoio aggiornato: la posizione va confermata fisicamente.')
    return piano
