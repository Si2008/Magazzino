"""Un'etichetta seriale per ogni pezzo fisico, indipendente dalla quantità."""
from uuid import uuid4
from sqlalchemy import select
from ..db.normalizzazione import normalizza_codice, normalizza_colore
from ..domain import Pezzo, Profilo, TipoMovimento, registra_movimento
from .carico import _colore_o_crea
from .eccezioni import ProfiloNonTrovatoError, PezzoNonTrovatoError
from .pezzi import _testo_opzionale


def _crea_in_transazione(session, codice, colore, lunghezza_mm, quantita, utente, causale,
                        ubicazione=None, numero_vassoio=None, scorta_minima=None, commessa_id=None):
    if isinstance(quantita, bool) or not isinstance(quantita, int) or not 1 <= quantita <= 1000:
        raise ValueError("Inserire da 1 a 1000 pezzi per operazione; ciascuno avrà un barcode distinto")
    if isinstance(lunghezza_mm, bool) or not isinstance(lunghezza_mm, int) or not 1 <= lunghezza_mm <= 2147483647:
        raise ValueError("Lunghezza non valida")
    if scorta_minima is not None and (isinstance(scorta_minima, bool) or not isinstance(scorta_minima, int) or scorta_minima < 0):
        raise ValueError("Scorta minima non valida")
    ubicazione = _testo_opzionale(ubicazione, "L'ubicazione")
    vassoio = _testo_opzionale(numero_vassoio, "Il vassoio")
    codice, colore = normalizza_codice(codice), normalizza_colore(colore)
    if not colore or len(colore) > 64 or any(ord(c) < 32 for c in colore):
        raise ValueError("Codice colore non valido")
    profilo = session.scalar(select(Profilo).where(Profilo.codice == codice))
    if profilo is None:
        raise ProfiloNonTrovatoError(codice)
    colore_db = _colore_o_crea(session, colore)
    pezzi = []
    for _ in range(quantita):
        pezzo = Pezzo(profilo=profilo, colore=colore_db, lunghezza_mm=lunghezza_mm,
                      quantita=0, unitario=True, barcode="MP-" + uuid4().hex.upper(),
                      numero_vassoio=vassoio, ubicazione=ubicazione, scorta_minima=scorta_minima)
        session.add(pezzo)
        registra_movimento(session, pezzo, TipoMovimento.CARICO, 1, causale, utente)
        pezzi.append(pezzo)
    if commessa_id is not None:
        from .archivio_commesse import assegna_in_transazione
        assegna_in_transazione(session,commessa_id,pezzi)
    return pezzi


def crea_pezzi_unitari(session, **dati):
    with session.begin():
        return _crea_in_transazione(session, **dati)


def ricarica_barcode(session, barcode, quantita, utente, causale):
    with session.begin():
        pezzo = session.scalar(select(Pezzo).where(Pezzo.barcode == barcode.strip().upper(),
                              Pezzo.eliminato_il.is_(None)).with_for_update())
        if pezzo is None:
            raise PezzoNonTrovatoError(barcode)
        registra_movimento(session, pezzo, TipoMovimento.CARICO, quantita, causale, utente)
        return pezzo


def piano_conversione(session, massimo=1000):
    """Fotografia da confermare; un lotto non modifica più di 1000 pezzi fisici."""
    if not 1 <= massimo <= 1000:
        raise ValueError("Lotto di conversione da 1 a 1000 pezzi")
    righe = session.execute(select(Pezzo.id, Pezzo.quantita).where(
        Pezzo.unitario.is_(False), Pezzo.quantita > 0, Pezzo.eliminato_il.is_(None)
    ).order_by(Pezzo.id).limit(massimo))
    piano = []
    for id_, quantita in righe:
        n = min(quantita, massimo)
        piano.append((id_, quantita, n))
        massimo -= n
        if massimo == 0:
            break
    return piano


def converti_aggregati(session, piano, utente):
    """Saldo totale invariato; storico aggregato conservato, nuove identità esplicite."""
    if not piano or sum(r[2] for r in piano) > 1000 or len({r[0] for r in piano}) != len(piano):
        raise ValueError("Piano di conversione non valido")
    nuovi = []
    with session.begin():
        for id_, attesa, quantita in sorted(piano):
            p = session.scalar(select(Pezzo).where(Pezzo.id == id_).with_for_update())
            if (p is None or p.unitario or p.eliminato_il is not None or p.quantita != attesa
                    or not 1 <= quantita <= attesa):
                raise ValueError("Giacenze cambiate dopo l'anteprima: conversione annullata, ripetere la verifica")
            causale = f"Conversione in pezzi singoli del barcode storico {p.barcode} (ID {p.id})"
            registra_movimento(session, p, TipoMovimento.RETTIFICA, quantita, causale, utente)
            nuovi.extend(_crea_in_transazione(session, p.profilo.codice, p.colore.codice_normalizzato,
                p.lunghezza_mm, quantita, utente, causale, p.ubicazione, p.numero_vassoio, p.scorta_minima))
    return [p.barcode for p in nuovi]
