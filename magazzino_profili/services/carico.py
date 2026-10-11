"""Servizio di carico: inserimento facilitato della giacenza.

Il carico è un'operazione separata dallo scarico: serve a immettere
merce in magazzino individuando il pezzo per codice profilo e colore.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.normalizzazione import genera_barcode, normalizza_codice, normalizza_colore
from ..domain import Colore, Pezzo, Profilo, TipoMovimento, registra_movimento
from .eccezioni import ProfiloNonTrovatoError


def carica(
    session: Session,
    codice: str,
    colore: str,
    lunghezza_mm: int,
    quantita: int,
    utente: str,
    causale: str,
    ubicazione: str | None = None,
) -> Pezzo:
    """Effettua un carico di magazzino (solo aumento di giacenza).

    Comportamento:
    - codice e colore vengono normalizzati con le funzioni esistenti;
    - il Profilo deve già esistere in anagrafica per codice
      normalizzato: altrimenti si solleva ``ProfiloNonTrovatoError``
      (il profilo NON viene creato dal carico);
    - se il Colore non esiste, viene creato automaticamente con
      codice normalizzato e nome uguale al codice;
    - se il Pezzo per (profilo, colore, lunghezza) non esiste, viene
      creato automaticamente senza chiedere conferma, con
      ``quantita = 0`` e barcode generato da ``genera_barcode``;
    - infine la quantità viene incrementata con un Movimento di
      tipo CARICO nella stessa transazione;
    - se ``ubicazione`` è fornita (testo non vuoto, ripulito), viene
      salvata: sul pezzo appena creato, o sul pezzo esistente se la sua
      ubicazione è ancora vuota; un'ubicazione già presente non viene
      mai sovrascritta. Senza il parametro il comportamento è identico
      al precedente.

    Se qualunque passo fallisce, la transazione viene annullata e
    nessun dato resta parzialmente modificato.
    """
    ubicazione_n = ubicazione.strip() if isinstance(ubicazione, str) and ubicazione.strip() else None
    codice_n = normalizza_codice(codice)
    colore_n = normalizza_colore(colore)

    with session.begin():
        # 1) Il profilo è obbligatorio: esiste solo se è in anagrafica.
        profilo = session.scalar(select(Profilo).where(Profilo.codice == codice_n))
        if profilo is None:
            raise ProfiloNonTrovatoError(codice_n)

        # 2) Il colore, se assente, viene creato automaticamente.
        colore_db = session.scalar(
            select(Colore).where(Colore.codice_normalizzato == colore_n)
        )
        if colore_db is None:
            colore_db = Colore(
                codice_normalizzato=colore_n,
                nome_visualizzato=colore_n,
            )
            session.add(colore_db)

        # 3) Il pezzo, se assente, viene creato con giacenza zero.
        pezzo = session.scalar(
            select(Pezzo).where(
                Pezzo.profilo_id == profilo.id,
                Pezzo.colore_id == colore_db.id,
                Pezzo.lunghezza_mm == lunghezza_mm,
            )
        )
        if pezzo is None:
            barcode = genera_barcode(profilo, colore_db, lunghezza_mm)
            pezzo = Pezzo(
                profilo=profilo,
                colore=colore_db,
                lunghezza_mm=lunghezza_mm,
                quantita=0,
                barcode=barcode,
                ubicazione=ubicazione_n,
            )
            session.add(pezzo)
        elif ubicazione_n and not (pezzo.ubicazione or "").strip():
            # Pezzo esistente senza ubicazione: la imposta (solo se vuota).
            pezzo.ubicazione = ubicazione_n

        # 4) Incremento + traccia contabile nella stessa transazione.
        registra_movimento(
            session,
            pezzo,
            TipoMovimento.CARICO,
            quantita,
            causale=causale,
            utente=utente,
        )

    return pezzo
