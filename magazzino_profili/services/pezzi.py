"""Servizi di rettifica diretta dei pezzi (scorta minima).

La quantità NON si tocca qui: passa sempre da ``registra_movimento``.
Qui si gestiscono i dati anagrafici della riga di giacenza.
"""

from sqlalchemy.orm import Session

from ..domain import Pezzo


def imposta_scorta_minima(
    session: Session,
    pezzo_id: int,
    scorta_minima: int | None,
) -> Pezzo:
    """Imposta (o cancella) la scorta minima del pezzo indicato.

    - ``scorta_minima=None``: cancella la soglia (campo ``NULL``);
    - valore intero non negativo: nuova soglia;
    - valore negativo: ``ValueError`` (nessun dato modificato).

    Il pezzo deve esistere: altrimenti ``ValueError``.
    Restituisce il pezzo aggiornato.
    """
    if scorta_minima is not None:
        if (
            not isinstance(scorta_minima, int)
            or isinstance(scorta_minima, bool)
            or scorta_minima < 0
        ):
            raise ValueError("La scorta minima deve essere un intero non negativo")

    with session.begin():
        pezzo = session.get(Pezzo, pezzo_id)
        if pezzo is None:
            raise ValueError(f"Pezzo non trovato: id {pezzo_id}")
        pezzo.scorta_minima = scorta_minima

    return pezzo
