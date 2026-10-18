"""Telefono come lettore barcode: coda delle scansioni e stato del collegamento."""

from __future__ import annotations

import tomllib
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from ..db import config as _config_db
from ..domain import Impostazione, ScansioneTelefono

CHIAVE_PING = "telefono_ultimo_ping"
FINESTRA_COLLEGATO_S = 30       # telefono "collegato" se l'ultimo ping è più recente di così
ETA_MASSIMA_SCANSIONE_S = 120   # scansioni più vecchie non vengono consegnate
CONSERVA_LETTE_GIORNI = 1       # le scansioni già lette si cancellano dopo un giorno


def _aware(momento: datetime) -> datetime:
    """SQLite restituisce datetime senza fuso: si assume UTC."""
    return momento if momento.tzinfo is not None else momento.replace(tzinfo=timezone.utc)


def registra_scansione(session: Session, barcode: str, utente: str) -> int:
    """Accoda una scansione del telefono. Restituisce l'id. ``ValueError`` se il barcode è vuoto."""
    codice = (barcode or "").strip().upper()
    if not codice:
        raise ValueError("Il barcode non può essere vuoto.")
    with session.begin():
        riga = ScansioneTelefono(barcode=codice, utente=utente)
        session.add(riga)
        session.flush()
        return riga.id


def registra_ping(session: Session, adesso: datetime | None = None) -> None:
    """Segna che il telefono è vivo in questo momento (upsert su ``impostazioni``)."""
    adesso = adesso or datetime.now(timezone.utc)
    with session.begin():
        riga = session.get(Impostazione, CHIAVE_PING)
        if riga is None:
            session.add(Impostazione(chiave=CHIAVE_PING, valore=adesso.isoformat()))
        else:
            riga.valore = adesso.isoformat()


def telefono_collegato(session: Session, adesso: datetime | None = None) -> bool:
    """True se l'ultimo ping del telefono è più recente di ``FINESTRA_COLLEGATO_S`` secondi."""
    riga = session.get(Impostazione, CHIAVE_PING)
    if riga is None:
        return False
    try:
        ultimo = _aware(datetime.fromisoformat(riga.valore))
    except ValueError:
        return False
    adesso = adesso or datetime.now(timezone.utc)
    return (adesso - ultimo) <= timedelta(seconds=FINESTRA_COLLEGATO_S)


def scarta_arretrate(session: Session, adesso: datetime | None = None) -> int:
    """Segna come lette tutte le scansioni in coda e pulisce quelle vecchie. Restituisce quante ne ha scartate."""
    adesso = adesso or datetime.now(timezone.utc)
    with session.begin():
        scartate = session.execute(
            update(ScansioneTelefono).where(ScansioneTelefono.letta.is_(False)).values(letta=True)
        ).rowcount
        session.execute(
            delete(ScansioneTelefono).where(
                ScansioneTelefono.letta.is_(True),
                ScansioneTelefono.creata_il < adesso - timedelta(days=CONSERVA_LETTE_GIORNI),
            )
        )
    return int(scartate or 0)


def preleva_scansioni(session: Session, adesso: datetime | None = None) -> list[str]:
    """Barcode non ancora consegnati, in ordine di arrivo. Li segna come letti.

    Quelli più vecchi di ``ETA_MASSIMA_SCANSIONE_S`` vengono segnati letti ma NON restituiti.
    """
    adesso = adesso or datetime.now(timezone.utc)
    limite = adesso - timedelta(seconds=ETA_MASSIMA_SCANSIONE_S)
    validi: list[str] = []
    with session.begin():
        righe = session.scalars(
            select(ScansioneTelefono)
            .where(ScansioneTelefono.letta.is_(False))
            .order_by(ScansioneTelefono.id)
        ).all()
        for riga in righe:
            riga.letta = True
            if _aware(riga.creata_il) >= limite:
                validi.append(riga.barcode)
    return validi


def leggi_url_pubblico(percorso: str | Path | None = None) -> str | None:
    """``[web] url_pubblico`` di ``config.toml`` (indirizzo HTTPS da aprire sul telefono) o ``None``.

    Legge il file con le stesse regole di ricerca di ``db/config.py`` senza importare il server web.
    """
    candidati = _config_db._candidati_config(Path(percorso) if percorso is not None else None)
    file = next((p for p in candidati if p.is_file()), None)
    if file is None:
        return None
    with open(file, "rb") as fonte:
        dati = tomllib.load(fonte)
    url = str(dati.get("web", {}).get("url_pubblico") or "").strip()
    return url or None
