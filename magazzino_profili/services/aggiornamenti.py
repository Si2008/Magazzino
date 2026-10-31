"""Nucleo SICURO del download di un aggiornamento (Fase 13, parte verificabile).

Non contiene URL, chiavi, nomi di publisher né il parser del manifest: quelli
dipendono dai valori che il proprietario deve fornire (tabella dei nove
prerequisiti). Qui c'è solo ciò che vale per qualunque feed: confronto
versioni, download su file temporaneo, controllo di dimensione e checksum,
verifica di autenticità INIETTATA, un solo download alla volta, nessun file
"pubblico" prima della verifica.

Resto della Fase 13 in ATTESA dei nove valori:
- URL del feed, publisher, formato del manifest, versione installata,
  algoritmo di firma, chiave/certificato, installer, URL dell'installer,
  procedura di recovery;
- parser del feed reale, popup, installazione e riavvio.
"""

from __future__ import annotations

import hashlib
import os
import re
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Callable, ContextManager, Iterator

_VERSIONE = re.compile(r"([0-9]+)\.([0-9]+)\.([0-9]+)")
_SHA256 = re.compile(r"[0-9a-f]{64}")
DIMENSIONE_BLOCCO = 64 * 1024


class ErroreAggiornamento(Exception):
    """Messaggio sempre in italiano, mostrabile all'utente così com'è."""


@dataclass(frozen=True)
class Manifest:
    """Forma NORMALIZZATA: il parser del feed reale deve produrre questa."""

    versione: str
    url_installer: str
    sha256: str  # esadecimale minuscolo
    dimensione: int  # byte

    def __post_init__(self) -> None:
        parse_versione(self.versione)
        if not self.url_installer.lower().startswith("https://"):
            raise ErroreAggiornamento("L'indirizzo dell'installer deve usare HTTPS.")
        if not _SHA256.fullmatch(self.sha256):
            raise ErroreAggiornamento("Checksum del manifest non valido.")
        if (
            isinstance(self.dimensione, bool)
            or not isinstance(self.dimensione, int)
            or self.dimensione < 1
        ):
            raise ErroreAggiornamento("Dimensione dell'installer non valida.")


def parse_versione(testo: str) -> tuple[int, int, int]:
    """Converte ``"X.Y.Z"`` in una tupla confrontabile; solleva se non valido."""
    m = _VERSIONE.fullmatch(testo.strip()) if isinstance(testo, str) else None
    if m is None:
        raise ErroreAggiornamento(
            f"Numero di versione non valido: {testo!r} (atteso X.Y.Z)."
        )
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def esiste_aggiornamento(disponibile: str, installata: str) -> bool:
    """True solo se la versione disponibile è STRETTAMENTE più recente."""
    return parse_versione(disponibile) > parse_versione(installata)


# Un'unica "apertura" astratta: la rete reale (con verifica dei certificati
# ATTIVA, comportamento predefinito di ``urllib``) la fornisce il chiamante;
# nei test è un finto.
Apri = Callable[[str], ContextManager[BinaryIO]]
# Verifica di autenticità INIETTATA: la scrive chi possiede la chiave
# pubblica; solleva ErroreAggiornamento se il file non è autentico.
VerificaAutenticita = Callable[[Path], None]  # noqa: E305

_blocco_processo = threading.Lock()


@contextmanager
def _un_solo_download(cartella: Path) -> Iterator[None]:
    """Blocca download concorrenti: stesso processo (lock) e tra processi (file esclusivo)."""
    if not _blocco_processo.acquire(blocking=False):
        raise ErroreAggiornamento("Un download è già in corso.")
    percorso = cartella / ".aggiornamento.lock"
    try:
        try:
            fd = os.open(percorso, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise ErroreAggiornamento(
                "Un altro processo sta già scaricando un aggiornamento."
            ) from None
        try:
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            yield
        finally:
            percorso.unlink(missing_ok=True)
    finally:
        _blocco_processo.release()


def scarica_e_verifica(
    manifest: Manifest,
    cartella: Path,
    apri: Apri,
    verifica_autenticita: VerificaAutenticita,
    avanzamento: Callable[[int, int], None] = lambda fatti, totali: None,
) -> Path:
    """Scarica in ``<nome>.part`` e restituisce il percorso finale SOLO se tutto è verificato.

    Ordine: dimensione -> checksum -> autenticità -> ``os.replace`` (atomico).
    In qualunque errore il file parziale viene eliminato e non resta nulla
    da eseguire.
    """
    cartella = Path(cartella)
    cartella.mkdir(parents=True, exist_ok=True)
    nome = f"Installer-{manifest.versione}.exe"
    finale, parziale = cartella / nome, cartella / (nome + ".part")
    with _un_solo_download(cartella):
        try:
            sha = hashlib.sha256()
            ricevuti = 0
            try:
                with apri(manifest.url_installer) as risposta, open(parziale, "wb") as uscita:
                    while True:
                        blocco = risposta.read(DIMENSIONE_BLOCCO)
                        if not blocco:
                            break
                        ricevuti += len(blocco)
                        if ricevuti > manifest.dimensione:
                            raise ErroreAggiornamento(
                                "Il file ricevuto è più grande del previsto: scaricamento annullato."
                            )
                        sha.update(blocco)
                        uscita.write(blocco)
                        avanzamento(ricevuti, manifest.dimensione)
                    uscita.flush()
                    os.fsync(uscita.fileno())
            except ErroreAggiornamento:
                raise
            except OSError as errore:
                raise ErroreAggiornamento(
                    "Errore di rete o di scrittura durante il download."
                ) from errore
            if ricevuti != manifest.dimensione:
                raise ErroreAggiornamento("Download incompleto: riprovare.")
            if sha.hexdigest() != manifest.sha256:
                raise ErroreAggiornamento(
                    "Il file scaricato è corrotto (checksum diverso): non verrà installato."
                )
            verifica_autenticita(parziale)
            os.replace(parziale, finale)
            return finale
        finally:
            parziale.unlink(missing_ok=True)
