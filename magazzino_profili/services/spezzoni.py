"""Servizio spezzoni: registrazione degli scarti di taglio e loro
utilizzo in successivi lavori."""

from sqlalchemy.orm import Session

from ..domain import Pezzo, Spezzone
from .eccezioni import PezzoNonTrovatoError, SpezzoneNonTrovatoError


def registra_spezzone(
    session: Session,
    pezzo_origine_id: int,
    lunghezza_mm: int,
    soglia_minima_mm: int,
    utente: str,
) -> Spezzone | None:
    """Registra lo spezzone residuo di un taglio, se è abbastanza lungo.

    Regole:
    - se ``lunghezza_mm < soglia_minima_mm`` lo scarto è troppo corto
      per essere riutilizzato: NON viene creato alcun spezzone e la
      funzione restituisce ``None``;
    - altrimenti viene creato uno ``Spezzone`` con ``utilizzato = False``
      e il campo ``utente`` valorizzato con l'operatore che registra.

    Nota: la registrazione di uno spezzone non modifica la giacenza
    del pezzo di origine (quindi non produce un Movimento): la
    sottrazione della lunghezza tagliata avviene a cura del chiamante
    tramite lo scarico.
    """
    if lunghezza_mm < soglia_minima_mm:
        return None

    with session.begin():
        # Il pezzo di origine deve esistere (vincolo FK).
        if session.get(Pezzo, pezzo_origine_id) is None:
            raise PezzoNonTrovatoError(f"pezzo di origine id {pezzo_origine_id}")

        spezzone = Spezzone(
            pezzo_origine_id=pezzo_origine_id,
            lunghezza_mm=lunghezza_mm,
            utilizzato=False,
            utente=utente,
        )
        session.add(spezzone)

    return spezzone


def utilizza_spezzone(session: Session, spezzone_id: int, utente: str) -> Spezzone:
    """Segna uno spezzone come riutilizzato in un successivo lavoro.

    Scelta documentata (come previsto dalla specifica): NON viene
    creato un Movimento, perché
    - l'entità ``Movimento`` impone ``quantita > 0`` (vincolo CHECK
      nel database): un movimento "a quantità zero" non è ammesso;
    - la giacenza è già stata decresciuta al momento del taglio
      (scarico): l'utilizzo dello spezzone non cambia ulteriormente
      le quantità in magazzino.

    Se lo spezzone non esiste si solleva ``SpezzoneNonTrovatoError``.
    Se è già stato utilizzato, la chiamata è senza effetto (idempotente).
    Il campo ``utente`` registra chi ha effettuato l'utilizzo.
    """
    with session.begin():
        spezzone = session.get(Spezzone, spezzone_id)
        if spezzone is None:
            raise SpezzoneNonTrovatoError(spezzone_id)
        if not spezzone.utilizzato:
            spezzone.utilizzato = True
            # Aggiorna l'operatore che ha riutilizzato lo spezzone.
            spezzone.utente = utente

    return spezzone
