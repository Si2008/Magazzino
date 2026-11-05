"""Servizio di scarico: uscita di merce da un pezzo esistente.

Il pezzo si individua ESCLUSIVAMENTE tramite barcode: questo rende
l'operazione univoca e indipendente da codici o colori digitati.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain import Movimento, Pezzo, TipoMovimento, registra_movimento
from .eccezioni import PezzoNonTrovatoError


def scarica(
    session: Session,
    barcode: str,
    quantita: int,
    utente: str,
    causale: str,
) -> Movimento:
    """Effettua uno scarico di magazzino sul pezzo identificato dal barcode.

    Comportamento:
    - se il barcode non corrisponde a nessun pezzo, si solleva
      ``PezzoNonTrovatoError``;
    - se ``quantita`` supera la giacenza, ``registra_movimento``
      solleva ``QuantitaInsufficienteError`` e la transazione viene
      annullata: la giacenza e i movimenti restano invariati;
    - in caso di successo crea un Movimento di tipo SCARICO e
      decrementa la giacenza nella stessa transazione.
    """
    barcode_pulito = barcode.strip().upper()

    with session.begin():
        return _scarica_in_transazione(session, barcode_pulito, quantita, utente, causale)


def _scarica_in_transazione(session, barcode_pulito, quantita, utente, causale):
        # solo pezzi attivi: i barcode eliminati (cancellazione logica)
        # non sono più movimentabili (regola Fase 7)
        pezzo = session.scalar(
            select(Pezzo)
            .where(Pezzo.barcode == barcode_pulito, Pezzo.eliminato_il.is_(None))
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if pezzo is None:
            raise PezzoNonTrovatoError(f"barcode '{barcode_pulito}' non presente in magazzino")

        # Regola anti-sottozero e creazione del movimento in un unico passo;
        # se fallisce, il blocco ``with`` annulla la transazione.
        return registra_movimento(
            session,
            pezzo,
            TipoMovimento.SCARICO,
            quantita,
            causale=causale,
            utente=utente,
        )
