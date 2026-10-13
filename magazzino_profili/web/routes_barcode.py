"""Endpoint API per la scansione dal telefono: login, carico, scarico.

Il modulo web NON riduplica la logica di magazzino: richiama i servizi
già esistenti (``services.carico.carica`` e ``services.scarico.scarica``),
che gestiscono transazione, regola anti-sottozero e traccia contabile.

Regola aggiuntiva specifica dell'uso remoto (vincolo di progetto):
il **carico via barcode non crea mai pezzi nuovi**. Se il barcode non
corrisponde a nessun pezzo esistente, la risposta è 404: la creazione
di pezzi resta una funzione del programma desktop, per evitare pezzi
creati per errore da remoto.

Codici di errore restituiti:
- 401 non autenticato / token scaduto;
- 403 ruolo non autorizzato (es. SOLA_LETTURA);
- 404 pezzo non trovato (barcode inesistente);
- 409 quantità richiesta superiore alla giacenza;
- 422 dati non validi (es. quantità non intera o non positiva).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from sqlalchemy import select

from ..domain import Pezzo
from ..domain.pezzo import QuantitaInsufficienteError
from ..services.carico import carica
from ..services.eccezioni import PezzoNonTrovatoError, ProfiloNonTrovatoError
from ..services.scarico import scarica
from .auth import (
    UtenteAutenticato,
    crea_dipendenza_utente,
    crea_token,
    prova_login,
    verifica_permesso,
)


class CadenzeLogin(BaseModel):
    """Credenziali per il login (stesso modello di utenti del desktop)."""

    utente: str = Field(min_length=1, description="Nome utente")
    password: str = Field(min_length=1, description="Password")


class RichiestaMovimento(BaseModel):
    """Dati di una richiesta di carico o scarico da telefono."""

    barcode: str = Field(min_length=1, max_length=255, description="Barcode del pezzo")
    quantita: int = Field(gt=0, description="Quantità, numero intero positivo")
    causale: str | None = Field(
        default=None,
        max_length=512,
        description="Causale (facoltativa) per la traccia contabile",
    )


def _dettagli_pezzo(pezzo: Pezzo, esito: str) -> dict:
    """Corpo di risposta di successo: esito + dettagli del pezzo.

    Da leggere con la sessione ancora aperta (relazioni caricate).
    """
    return {
        "dettaglio": esito,
        "barcode": pezzo.barcode,
        "codice_profilo": pezzo.profilo.codice,
        "descrizione": pezzo.profilo.descrizione,
        "colore": pezzo.colore.nome_visualizzato,
        "lunghezza_mm": pezzo.lunghezza_mm,
        "quantita_giacenza": pezzo.quantita,
    }


def crea_router(
    session_factory,
    segrete_token: bytes,
    durata_token_secondi: int,
) -> APIRouter:
    """Costruisce il router ``/api`` con i servizi iniettati.

    ``session_factory`` è il factory di sessioni SQLAlchemy sullo stesso
    PostgreSQL dell'app desktop (o un altro engine, nei test).
    """

    router = APIRouter(prefix="/api")
    utente_autenticato = crea_dipendenza_utente(segrete_token, session_factory)

    @router.post("/login")
    def login(credenziali: CadenzeLogin) -> dict:
        """Verifica le credenziali e restituisce un token con scadenza.

        Credenziali errate o utente assente: HTTP 401.
        """
        with session_factory() as session:
            utente = prova_login(session, credenziali.utente, credenziali.password)
        if utente is None:
            raise HTTPException(status_code=401, detail="Credenziali non valide.")
        token = crea_token(
            utente.username, utente.ruolo, durata_token_secondi, segrete_token
        )
        return {
            "dettaglio": "Accesso effettuato.",
            "token": token,
            "utente": utente.username,
            "ruolo": utente.ruolo,
        }

    @router.post("/carico")
    def api_carico(
        payload: RichiestaMovimento,
        utente: UtenteAutenticato = Depends(utente_autenticato),
    ) -> dict:
        """Registra un carico sul pezzo identificato dal barcode.

        Il pezzo deve già esistere (creato dal programma desktop):
        barcode inesistente → 404, nessun pezzo viene creato.
        """
        verifica_permesso(utente, "carico")
        barcode = payload.barcode.strip().upper()

        # 1) Pre-verifica in una propria transazione: il barcode deve
        #    corrispondere a un pezzo già presente in magazzino.
        with session_factory() as session:
            trovato = session.scalar(select(Pezzo).where(Pezzo.barcode == barcode))
            if trovato is None:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        f"Pezzo non trovato: il barcode '{barcode}' non corrisponde a "
                        "nessun pezzo in magazzino. Il pezzo va prima creato dal "
                        "programma desktop."
                    ),
                )
            # Campi copiati ora (sessione poi chiusa): servono al servizio.
            codice_profilo = trovato.profilo.codice
            codice_colore = trovato.colore.codice_normalizzato
            lunghezza_mm = trovato.lunghezza_mm

        # 2) Carico vero e proprio: servizio esistente, transazione a parte.
        #    Il pezzo esiste già, quindi il servizio si limita ad
        #    incrementare la giacenza e a registrare il movimento.
        with session_factory() as session:
            try:
                pezzo = carica(
                    session,
                    codice=codice_profilo,
                    colore=codice_colore,
                    lunghezza_mm=lunghezza_mm,
                    quantita=payload.quantita,
                    utente=utente.username,
                    causale=payload.causale or "Carico da telefono",
                    crea_se_mancante=False,
                )
            except (ProfiloNonTrovatoError, PezzoNonTrovatoError) as errore:
                # Cancellato nel frattempo dal desktop: si risponde 404, nulla viene creato.
                raise HTTPException(status_code=404, detail=str(errore)) from errore
            return _dettagli_pezzo(pezzo, "Carico registrato.")

    @router.post("/scarico")
    def api_scarico(
        payload: RichiestaMovimento,
        utente: UtenteAutenticato = Depends(utente_autenticato),
    ) -> dict:
        """Registra uno scarico sul pezzo identificato dal barcode.

        Barcode inesistente → 404; quantità superiore alla giacenza →
        409 con giacenza e movimenti invariati (transazione annullata).
        """
        verifica_permesso(utente, "scarico")
        barcode = payload.barcode.strip().upper()

        with session_factory() as session:
            try:
                movimento = scarica(
                    session,
                    barcode=barcode,
                    quantita=payload.quantita,
                    utente=utente.username,
                    causale=payload.causale or "Scarico da telefono",
                )
            except PezzoNonTrovatoError as errore:
                raise HTTPException(status_code=404, detail=str(errore)) from errore
            except QuantitaInsufficienteError as errore:
                raise HTTPException(status_code=409, detail=str(errore)) from errore
            return _dettagli_pezzo(movimento.pezzo, "Scarico registrato.")

    return router
