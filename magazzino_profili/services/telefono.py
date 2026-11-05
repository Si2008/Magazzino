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


def registra_scansione(session: Session, barcode: str, utente: str, destinatario: str | None = None) -> int:
    """Accoda una scansione del telefono. Restituisce l'id. ``ValueError`` se il barcode è vuoto."""
    codice = (barcode or "").strip().upper()
    if not codice:
        raise ValueError("Il barcode non può essere vuoto.")
    with session.begin():
        riga = ScansioneTelefono(barcode=codice, utente=utente, destinatario=destinatario)
        session.add(riga)
        session.flush()
        return riga.id


def registra_ping(session: Session, adesso: datetime | None = None, destinatario: str | None = None) -> None:
    """Segna che il telefono è vivo in questo momento (upsert su ``impostazioni``)."""
    adesso = adesso or datetime.now(timezone.utc)
    with session.begin():
        chiave = "telefono_ping_" + destinatario if destinatario else CHIAVE_PING
        _scrivi_presenza(session, chiave, adesso)


def _scrivi_presenza(session, chiave, adesso):
    """Upsert atomico: due ping contemporanei non violano la chiave primaria."""
    if session.get_bind().dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    session.execute(insert(Impostazione).values(chiave=chiave, valore=adesso.isoformat())
                    .on_conflict_do_update(index_elements=[Impostazione.chiave],
                                          set_={"valore": adesso.isoformat()}))


def pc_collegato(session, destinatario, adesso=None):
    if not destinatario:
        return False
    riga = session.get(Impostazione, "pc_ping_" + destinatario)
    try:
        ultimo = _aware(datetime.fromisoformat(riga.valore)) if riga else None
    except ValueError:
        return False
    return ultimo is not None and timedelta(0) <= ((adesso or datetime.now(timezone.utc)) - ultimo) <= timedelta(seconds=15)


def telefono_collegato(session: Session, adesso: datetime | None = None, destinatario: str | None = None) -> bool:
    """True se l'ultimo ping del telefono è più recente di ``FINESTRA_COLLEGATO_S`` secondi."""
    riga = session.get(Impostazione, "telefono_ping_" + destinatario if destinatario else CHIAVE_PING)
    if riga is None:
        return False
    try:
        ultimo = _aware(datetime.fromisoformat(riga.valore))
    except ValueError:
        return False
    adesso = adesso or datetime.now(timezone.utc)
    return timedelta(0) <= (adesso - ultimo) <= timedelta(seconds=FINESTRA_COLLEGATO_S)


def scarta_arretrate(session: Session, adesso: datetime | None = None) -> int:
    """Segna come lette tutte le scansioni in coda e pulisce quelle vecchie. Restituisce quante ne ha scartate."""
    adesso = adesso or datetime.now(timezone.utc)
    with session.begin():
        scartate = session.execute(
            update(ScansioneTelefono).where(ScansioneTelefono.letta.is_(False),
                                           ScansioneTelefono.destinatario.is_(None)).values(letta=True)
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
            .where(ScansioneTelefono.destinatario.is_(None))
            .order_by(ScansioneTelefono.id)
            .with_for_update(skip_locked=True)
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


def prendi_scansioni(session, destinatario, adesso=None):
    """Claim atomico per PC. Una consegna interrotta non viene rieseguita alla cieca."""
    adesso = adesso or datetime.now(timezone.utc)
    with session.begin():
        _scrivi_presenza(session, "pc_ping_" + destinatario, adesso)
        session.execute(update(ScansioneTelefono).where(
            ScansioneTelefono.destinatario == destinatario,
            ScansioneTelefono.letta.is_(False),
            ScansioneTelefono.presa_il < adesso - timedelta(minutes=5)
        ).values(letta=True, esito="incerto", dettaglio="Consegna interrotta: controllare la giacenza prima di ripetere"))
        righe = list(session.scalars(select(ScansioneTelefono).where(
            ScansioneTelefono.destinatario == destinatario,
            ScansioneTelefono.letta.is_(False), ScansioneTelefono.presa_il.is_(None)
        ).order_by(ScansioneTelefono.id).limit(10).with_for_update(skip_locked=True)))
        risultati = []
        for riga in righe:
            if _aware(riga.creata_il) < adesso - timedelta(seconds=ETA_MASSIMA_SCANSIONE_S):
                riga.letta = True
                riga.esito = "scaduta"
                riga.dettaglio = "Scansione scaduta prima della consegna al PC"
            else:
                riga.presa_il = adesso
                risultati.append((riga.id, riga.barcode))
        return risultati


def conferma_scansione(session, id_, destinatario, esito, dettaglio):
    if esito not in ("completata", "compilata", "rifiutata", "incerto"):
        raise ValueError("Esito scansione non valido")
    with session.begin():
        risultato = session.execute(update(ScansioneTelefono).where(
            ScansioneTelefono.id == id_, ScansioneTelefono.destinatario == destinatario,
            ScansioneTelefono.letta.is_(False)
        ).values(letta=True, esito=esito, dettaglio=str(dettaglio)[:512]))
        return risultato.rowcount == 1


def valida_url_pubblico(url):
    from urllib.parse import urlsplit
    import ipaddress
    p = urlsplit(url.strip())
    if p.scheme != "https" or not p.hostname or p.username or p.password or p.fragment or p.query or p.path not in ("", "/"):
        raise ValueError("Inserisci un indirizzo HTTPS senza credenziali, parametri o frammenti")
    if p.hostname.lower() in ("localhost", "0.0.0.0", "::"):
        raise ValueError("L'indirizzo deve essere raggiungibile dal telefono; localhost non va bene")
    try:
        indirizzo = ipaddress.ip_address(p.hostname)
    except ValueError:
        indirizzo = None
    if indirizzo and indirizzo.is_loopback:
        raise ValueError("L'indirizzo di loopback non è raggiungibile dal telefono")
    try:
        p.port
    except ValueError as errore:
        raise ValueError("Porta non valida nell'indirizzo") from errore
    return url.strip().rstrip("/") + "/"
