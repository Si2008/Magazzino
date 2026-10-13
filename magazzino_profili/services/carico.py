"""Servizio di carico: inserimento facilitato della giacenza.

Il carico è un'operazione separata dallo scarico: serve a immettere
merce in magazzino individuando il pezzo per codice profilo e colore.

Concorrenza: il pezzo viene letto con blocco di riga (``FOR UPDATE``),
così due operazioni concorrenti sullo stesso pezzo si susseguono e
nessuna unità viene persa. Creazione di colore e pezzo: se un'altra
transazione li ha creati nel frattempo, si riusa quello creato dall'altra.
"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db.normalizzazione import genera_barcode, normalizza_codice, normalizza_colore
from ..domain import Colore, Pezzo, Profilo, TipoMovimento, registra_movimento
from .eccezioni import PezzoNonTrovatoError, ProfiloNonTrovatoError


def _pezzo_bloccato(session: Session, profilo_id: int, colore_id: int, lunghezza_mm: int):
    """Il pezzo della combinazione, letto con blocco di riga e dati aggiornati."""
    return session.scalar(
        select(Pezzo)
        .where(
            Pezzo.profilo_id == profilo_id,
            Pezzo.colore_id == colore_id,
            Pezzo.lunghezza_mm == lunghezza_mm,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def _colore_o_crea(session: Session, colore_n: str) -> Colore:
    colore = session.scalar(select(Colore).where(Colore.codice_normalizzato == colore_n))
    if colore is not None:
        return colore
    try:
        with session.begin_nested():
            colore = Colore(codice_normalizzato=colore_n, nome_visualizzato=colore_n)
            session.add(colore)
    except IntegrityError:
        # Creato da un'altra transazione nel frattempo: si riusa quello.
        colore = session.scalar(select(Colore).where(Colore.codice_normalizzato == colore_n))
        if colore is None:
            raise
    return colore


def _crea_pezzo(session: Session, profilo: Profilo, colore: Colore,
                lunghezza_mm: int, ubicazione: str | None) -> Pezzo:
    barcode = genera_barcode(profilo, colore, lunghezza_mm)
    try:
        with session.begin_nested():
            pezzo = Pezzo(
                profilo=profilo,
                colore=colore,
                lunghezza_mm=lunghezza_mm,
                quantita=0,
                barcode=barcode,
                ubicazione=ubicazione,
            )
            session.add(pezzo)
    except IntegrityError:
        # Creato da un'altra transazione nel frattempo: si riusa quello.
        pezzo = _pezzo_bloccato(session, profilo.id, colore.id, lunghezza_mm)
        if pezzo is None:
            raise  # conflitto reale (es. barcode già usato da un'altra combinazione)
    return pezzo


def carica(
    session: Session,
    codice: str,
    colore: str,
    lunghezza_mm: int,
    quantita: int,
    utente: str,
    causale: str,
    ubicazione: str | None = None,
    crea_se_mancante: bool = True,
) -> Pezzo:
    """Effettua un carico di magazzino (solo aumento di giacenza).

    - il Profilo deve già esistere in anagrafica (``ProfiloNonTrovatoError``);
    - il Colore, se assente, viene creato con codice normalizzato;
    - se il pezzo per (profilo, colore, lunghezza) non esiste:
      con ``crea_se_mancante=True`` viene creato con giacenza zero;
      con ``False`` si solleva ``PezzoNonTrovatoError`` e nulla viene creato
      (usato dal telefono: il carico remoto non crea pezzi);
    - ``ubicazione`` viene salvata solo se il pezzo non ne ha già una;
    - la quantità viene incrementata con un Movimento CARICO nella stessa
      transazione. Se un passo fallisce, nulla viene salvato.
    """
    ubicazione_n = ubicazione.strip() if isinstance(ubicazione, str) and ubicazione.strip() else None
    codice_n = normalizza_codice(codice)
    colore_n = normalizza_colore(colore)

    with session.begin():
        profilo = session.scalar(select(Profilo).where(Profilo.codice == codice_n))
        if profilo is None:
            raise ProfiloNonTrovatoError(codice_n)

        colore_db = _colore_o_crea(session, colore_n)

        pezzo = _pezzo_bloccato(session, profilo.id, colore_db.id, lunghezza_mm)
        if pezzo is None:
            if not crea_se_mancante:
                raise PezzoNonTrovatoError(
                    f"profilo {codice_n}, colore {colore_n}, lunghezza {lunghezza_mm} mm"
                )
            pezzo = _crea_pezzo(session, profilo, colore_db, lunghezza_mm, ubicazione_n)
        elif ubicazione_n and not (pezzo.ubicazione or "").strip():
            pezzo.ubicazione = ubicazione_n

        registra_movimento(
            session,
            pezzo,
            TipoMovimento.CARICO,
            quantita,
            causale=causale,
            utente=utente,
        )

    return pezzo
