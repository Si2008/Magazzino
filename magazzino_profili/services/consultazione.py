"""Consultazioni di sola lettura per la UI: inventario e avvisi.

La UI non contiene logica di business: le query restano qui.
"""

import re

from sqlalchemy import Float, and_, case, cast, func, or_, select
from sqlalchemy.orm import Session, selectinload

from ..domain import Colore, Movimento, Pezzo, Profilo
from ..db.normalizzazione import normalizza_codice, normalizza_colore

from .impostazioni import MOLTIPLICATORE_ESAURIMENTO


def _opzioni_pezzo():
    """Carica subito profilo e colore: la UI usa i relaz. a sessione chiusa."""
    return (
        selectinload(Pezzo.profilo),
        selectinload(Pezzo.colore),
    )


def _limite_sotto_scorta(soglia_globale: int | None):
    """Espressione SQL: quantità massima (inclusa) considerata "sotto scorta".

    - pezzo con scorta_minima: ``scorta_minima - 1`` (significato storico: quantita < scorta_minima);
    - pezzo senza scorta_minima: ``soglia_globale`` ("fino a N pezzi");
    - ``soglia_globale=None``: comportamento storico, i pezzi senza scorta_minima danno NULL
      (nessun avviso), quindi ``quantita <= NULL`` non seleziona nulla.
    """
    if soglia_globale is None:
        return Pezzo.scorta_minima - 1
    return func.coalesce(Pezzo.scorta_minima - 1, soglia_globale)


def lista_pezzi(session: Session) -> list[Pezzo]:
    """Tutti i pezzi in giacenza, ordinati per barcode."""
    return list(
        session.scalars(
            select(Pezzo).options(*_opzioni_pezzo()).order_by(Pezzo.barcode)
        )
    )


def lista_colori(session: Session) -> list[Colore]:
    """Tutti i colori, ordinati per codice (per i filtri della UI)."""
    return list(session.scalars(select(Colore).order_by(Colore.codice_normalizzato)))


def lista_profilo(session: Session) -> list[Profilo]:
    """Tutti i profili in anagrafica, ordinati per codice."""
    return list(session.scalars(select(Profilo).order_by(Profilo.codice)))


def pezzi_sotto_scora(session: Session, soglia_globale: int | None = None) -> list[Pezzo]:
    """Pezzi con scorta minima definita e giacenza al di sotto di essa.

    Con ``soglia_globale`` i pezzi senza scorta_minima entrano in avviso
    fino a (inclusi) ``soglia_globale`` pezzi.
    """
    return list(
        session.scalars(
            select(Pezzo)
            .options(*_opzioni_pezzo())
            .where(
                Pezzo.quantita <= _limite_sotto_scorta(soglia_globale),
            )
        )
    )


def _like_escapato(testo: str) -> str:
    """Testo utente come pattern LIKE: ``%`` e ``_`` diventano letterali."""
    escapato = testo.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escapato}%"


def cerca_pezzi(
    session: Session,
    testo: str = "",
    colore_id: int | None = None,
    stato: str | None = None,
    profilo_id: int | None = None,
    ubicazione: str | None = None,
    soglia_globale: int | None = None,
) -> list[Pezzo]:
    """Cerca pezzi per testo libero, colori, profilo, ubicazione e stato scorta.

    - ``testo``: può contenere più parole separate da spazi; ogni parola
      deve comparire (senza distinzione maiuscole/minuscole) in uno dei
      campi barcode, codice profilo, descrizione profilo, nome colore
      o ubicazione (AND tra le parole, OR tra i campi);
    - ``colore_id`` / ``profilo_id``: se forniti, limitano al colore /
      profilo indicato;
    - ``ubicazione``: uguaglianza (case-insensitive, spazi ai bordi
      ignorati) dell'ubicazione;
    - ``stato``: ``"sotto"`` = sotto scorta minima, ``"ok"`` = non
      sotto scorta, ``"esaurito"`` = giacenza zero, ``"riordino"`` =
      esaurito o sotto scorta, ``None`` = tutti.
    """
    condizioni = []

    for parola in testo.split():
        parola = parola.strip()
        if not parola:
            continue
        like = _like_escapato(parola.upper())
        condizioni.append(
            or_(
                Pezzo.barcode.ilike(like, escape="\\"),
                Pezzo.profilo.has(Profilo.codice.ilike(like, escape="\\")),
                Pezzo.profilo.has(Profilo.descrizione.ilike(like, escape="\\")),
                Pezzo.colore.has(Colore.nome_visualizzato.ilike(like, escape="\\")),
                Pezzo.ubicazione.ilike(like, escape="\\"),
            )
        )

    if colore_id is not None:
        condizioni.append(Pezzo.colore_id == colore_id)

    if profilo_id is not None:
        condizioni.append(Pezzo.profilo_id == profilo_id)

    if ubicazione and ubicazione.strip():
        condizioni.append(
            func.upper(func.trim(Pezzo.ubicazione)) == ubicazione.strip().upper()
        )

    if stato == "sotto":
        condizioni.append(Pezzo.quantita <= _limite_sotto_scorta(soglia_globale))
    elif stato == "ok":
        condizioni.append(
            or_(
                _limite_sotto_scorta(soglia_globale).is_(None),
                Pezzo.quantita > _limite_sotto_scorta(soglia_globale),
            )
        )
    elif stato == "esaurito":
        condizioni.append(Pezzo.quantita <= 0)
    elif stato == "riordino":
        condizioni.append(
            or_(
                Pezzo.quantita <= 0,
                Pezzo.quantita <= _limite_sotto_scorta(soglia_globale),
            )
        )

    return list(
        session.scalars(
            select(Pezzo)
            .options(*_opzioni_pezzo())
            .where(*condizioni)
            .order_by(Pezzo.barcode)
        )
    )


def stato_scorta(pezzo: Pezzo, soglia_globale: int | None = None) -> str:
    """Stato scorta di un pezzo: ``"ok"``, ``"sotto"`` o ``"esaurito"``.

    ``soglia_globale`` vale solo per i pezzi senza ``scorta_minima`` ("fino a N pezzi").
    Funzione pura: non tocca la sessione.
    """
    if pezzo.quantita is None or pezzo.quantita <= 0:
        return "esaurito"
    if pezzo.scorta_minima is not None:
        return "sotto" if pezzo.quantita < pezzo.scorta_minima else "ok"
    if soglia_globale is not None and pezzo.quantita <= soglia_globale:
        return "sotto"
    return "ok"


def peso_unitario_kg(pezzo: Pezzo) -> float:
    """Peso di un singolo pezzo in kg (peso lineare × lunghezza).

    Funzione pura; restituisce ``0.0`` se il peso lineare o la
    lunghezza non sono validi (assenti, nulli o non positivi).
    """
    peso_lineare = getattr(getattr(pezzo, "profilo", None), "peso_kg_per_metro", None)
    if peso_lineare is None:
        return 0.0
    try:
        peso = float(peso_lineare)
    except (TypeError, ValueError):
        return 0.0
    lunghezza = getattr(pezzo, "lunghezza_mm", None)
    if not isinstance(lunghezza, int) or isinstance(lunghezza, bool) or lunghezza <= 0:
        return 0.0
    if peso <= 0:
        return 0.0
    return peso * (lunghezza / 1000.0)


def peso_totale_kg(pezzo: Pezzo) -> float:
    """Peso totale della giacenza del pezzo in kg (unitario × quantità).

    Funzione pura; quantità nulla o non positiva trattata come zero.
    """
    quantita = getattr(pezzo, "quantita", None)
    if not isinstance(quantita, int) or isinstance(quantita, bool) or quantita <= 0:
        return 0.0
    return peso_unitario_kg(pezzo) * quantita


def riepilogo_inventario(session: Session, soglia_globale: int | None = None) -> dict:
    """Contatori dell'inventario in un unico dict (card KPI globali).

    Chiavi richieste dalle card KPI: ``pezzi_totali`` (somma delle
    quantità), ``referenze`` (righe di giacenza), ``peso_kg`` (somma del
    peso totale di tutti i pezzi), ``da_riordinare`` (esauriti + sotto
    scorta, coerente con :func:`stato_scorta`).

    Chiavi extra: ``pezzi`` (alias di ``pezzi_totali``), ``profili``,
    ``colori``, ``barcodes_unici``.
    """
    da_riordinare = or_(
        Pezzo.quantita <= 0,
        and_(Pezzo.scorta_minima.is_not(None), Pezzo.quantita < Pezzo.scorta_minima),
    )
    peso = case(
        (
            and_(Pezzo.quantita > 0, Pezzo.lunghezza_mm > 0, Profilo.peso_kg_per_metro > 0),
            cast(Profilo.peso_kg_per_metro, Float) * (Pezzo.lunghezza_mm / 1000.0) * Pezzo.quantita,
        ),
        else_=0.0,
    )
    riga = session.execute(
        select(
            func.count(Pezzo.id),
            func.coalesce(func.sum(Pezzo.quantita), 0),
            func.count(func.distinct(Pezzo.profilo_id)),
            func.count(func.distinct(Pezzo.colore_id)),
            func.count(func.distinct(Pezzo.barcode)),
            func.coalesce(func.sum(peso), 0.0),
            func.coalesce(func.sum(case((da_riordinare, 1), else_=0)), 0),
        ).select_from(Pezzo).join(Profilo, Pezzo.profilo_id == Profilo.id)
    ).one()
    pezzi_totali = int(riga[1] or 0)
    return {
        "pezzi_totali": pezzi_totali, "pezzi": pezzi_totali,
        "referenze": int(riga[0] or 0), "peso_kg": float(riga[5] or 0.0),
        "da_riordinare": int(riga[6] or 0), "profili": int(riga[2] or 0),
        "colori": int(riga[3] or 0), "barcodes_unici": int(riga[4] or 0),
    }


def pezzo_per_barcode(session: Session, barcode: str | None) -> Pezzo | None:
    """Il pezzo con il barcode dato (strip, case-insensitive), o ``None``.

    Le relazioni profilo/colore sono caricate eager: accessibili anche
    dopo la chiusura della sessione.
    """
    valore = (barcode or "").strip().upper()
    if not valore:
        return None
    return session.scalar(
        select(Pezzo).options(*_opzioni_pezzo()).where(Pezzo.barcode == valore)
    )


def pezzo_per_combinazione(
    session: Session,
    codice: str,
    colore: str,
    lunghezza_mm: int,
) -> Pezzo | None:
    """Il pezzo per (codice profilo normalizzato, colore normalizzato,
    lunghezza), o ``None``. Relazioni caricate eager."""
    codice_n = normalizza_codice(codice)
    colore_n = normalizza_colore(colore)
    if not codice_n or not colore_n:
        return None
    if not isinstance(lunghezza_mm, int) or isinstance(lunghezza_mm, bool) or lunghezza_mm <= 0:
        return None
    return session.scalar(
        select(Pezzo)
        .options(*_opzioni_pezzo())
        .join(Profilo, Pezzo.profilo_id == Profilo.id)
        .join(Colore, Pezzo.colore_id == Colore.id)
        .where(
            Profilo.codice == codice_n,
            Colore.codice_normalizzato == colore_n,
            Pezzo.lunghezza_mm == lunghezza_mm,
        )
    )


def candidati_da_barcode(session: Session, barcode: str) -> list[tuple[str, str, int]]:
    """Scomposizioni possibili di ``CODICE-COLORE-LUNGHEZZA`` con codice in anagrafica.

    Restituisce tuple ``(codice, colore, lunghezza)`` per ogni punto di taglio
    in cui il prefisso è un codice profilo esistente. Un barcode con codici
    che contengono ``-`` può avere più scomposizioni valide.
    """
    parti = barcode.split("-")
    if len(parti) < 3 or not parti[-1].isdigit():
        return []
    lunghezza = int(parti[-1])
    risultati: list[tuple[str, str, int]] = []
    for taglio in range(1, len(parti) - 1):
        codice = normalizza_codice("-".join(parti[:taglio]))
        colore = normalizza_colore("-".join(parti[taglio:-1]))
        if not codice or not colore:
            continue
        esiste = session.scalar(select(Profilo.id).where(Profilo.codice == codice))
        if esiste is not None:
            risultati.append((codice, colore, lunghezza))
    return risultati


def _chiave_naturale(testo: str):
    """Chiave di ordinamento naturale: 'Vassoio 2' < 'Vassoio 10'."""
    parti = re.split(r"(\d+)", testo or "")
    return [int(p) if p.isdigit() else p.lower() for p in parti if p]


def lista_ubicazioni(session: Session) -> list[str]:
    """Ubicazioni distinte e non vuote, in ordine naturale (Vassoio 2 < Vassoio 10)."""
    valori = session.scalars(
        select(Pezzo.ubicazione)
        .where(Pezzo.ubicazione.is_not(None), Pezzo.ubicazione != "")
        .distinct()
    ).all()
    return sorted({v.strip() for v in valori if v and v.strip()}, key=_chiave_naturale)


def ultimi_movimenti(
    session: Session,
    limite: int = 8,
    pezzo_id: int | None = None,
) -> list[Movimento]:
    """Ultimi movimenti (data_ora decrescente), opzionalmente solo di un pezzo.

    Il pezzo (e le sue relazioni) è caricato eager: la UI può usarlo
    anche dopo la chiusura della sessione.
    """
    query = (
        select(Movimento)
        .options(
            selectinload(Movimento.pezzo).selectinload(Pezzo.profilo),
            selectinload(Movimento.pezzo).selectinload(Pezzo.colore),
        )
        .order_by(Movimento.data_ora.desc(), Movimento.id.desc())
    )
    if pezzo_id is not None:
        query = query.where(Movimento.pezzo_id == pezzo_id)
    return list(session.scalars(query.limit(max(1, int(limite)))).all())


def lista_profili_con_giacenza(session: Session) -> list[tuple[Profilo, int]]:
    """Coppie ``(profilo, totale_pezzi)`` per tutti i profili in anagrafica.

    I profili senza pezzi hanno totale ``0`` (outer join).
    Ordinati per codice profilo.
    """
    righe = session.execute(
        select(Profilo, func.coalesce(func.sum(Pezzo.quantita), 0))
        .outerjoin(Pezzo, Pezzo.profilo_id == Profilo.id)
        .group_by(Profilo.id)
        .order_by(Profilo.codice)
    ).all()
    return [(profilo, int(totale or 0)) for profilo, totale in righe]


def lista_colori_con_conteggio(session: Session) -> list[tuple[Colore, int, int]]:
    """Per ogni colore (anche senza pezzi): ``(colore, referenze, pezzi_totali)``.

    ``referenze`` = numero di righe Pezzo di quel colore;
    ``pezzi_totali`` = somma delle loro quantità (0 se nessuna).
    Ordinati per ``codice_normalizzato`` crescente.
    """
    righe = session.execute(
        select(
            Colore,
            func.count(Pezzo.id),
            func.coalesce(func.sum(Pezzo.quantita), 0),
        )
        .outerjoin(Pezzo, Pezzo.colore_id == Colore.id)
        .group_by(Colore.id)
        .order_by(Colore.codice_normalizzato)
    ).all()
    return [(colore, int(referenze or 0), int(pezzi or 0)) for colore, referenze, pezzi in righe]


def pezzi_da_riordinare(session: Session, soglia_globale: int | None = None) -> list[Pezzo]:
    """Pezzi esauriti o sotto la scorta minima, per giacenza crescente."""
    return list(
        session.scalars(
            select(Pezzo)
            .options(*_opzioni_pezzo())
            .where(
                or_(
                    Pezzo.quantita <= 0,
                    Pezzo.quantita <= _limite_sotto_scorta(soglia_globale),
                )
            )
            .order_by(Pezzo.quantita.asc(), Pezzo.barcode)
        )
    )


def livello_scorta(pezzo: Pezzo, soglia_globale: int | None = None) -> str:
    """Come :func:`stato_scorta` ma con il quarto livello ``"esaurimento"``.

    ``"esaurimento"``: pezzo non sotto scorta ma con giacenza entro 3 volte il riferimento
    (``scorta_minima`` se presente, altrimenti la soglia globale).
    """
    base = stato_scorta(pezzo, soglia_globale)
    if base != "ok":
        return base
    riferimento = pezzo.scorta_minima if pezzo.scorta_minima is not None else soglia_globale
    if riferimento is not None and pezzo.quantita <= riferimento * MOLTIPLICATORE_ESAURIMENTO:
        return "esaurimento"
    return "ok"


def pezzi_avvisi(session: Session, soglia_globale: int | None = None) -> list[Pezzo]:
    """Pezzi per la scheda Avvisi: esauriti, sotto scorta e in esaurimento, per giacenza crescente."""
    riferimento = func.coalesce(Pezzo.scorta_minima, soglia_globale) if soglia_globale is not None else Pezzo.scorta_minima
    return list(
        session.scalars(
            select(Pezzo)
            .options(*_opzioni_pezzo())
            .where(
                or_(
                    Pezzo.quantita <= 0,
                    Pezzo.quantita <= riferimento * MOLTIPLICATORE_ESAURIMENTO,
                )
            )
            .order_by(Pezzo.quantita.asc(), Pezzo.barcode)
        )
    )
