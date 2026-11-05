"""Sistema di aggiornamento (Fase 13 completa).

Valori dei nove prerequisiti (decisi dal proprietario, 31/10/2026):

- URL feed:        ``https://<host>:<porta-web>/update/manifest.json``
  (valore concreto in ``[update] feed_url`` di config.toml; il feed è
  servito dal server web dell'app: ``web/routes_update.py``);
- publisher:       "Magazzino Profili";
- manifest:        JSON con ``versione``, ``url_installer``, ``sha256``,
  ``dimensione``, ``pubblicato``, ``note`` e ``firma`` (base64);
- versione installata: ``magazzino_profili.__version__``;
- algoritmo firma: Ed25519 (RFC 8032) sul manifest in forma canonica
  (JSON a chiavi ordinate); integrità dell'installer con SHA-256 preso
  dal manifest firmato;
- certificato:     coppia Ed25519 autofirmata; la chiave PRIVATA sta in
  ``firme/chiave_privata.pem`` (mai inside l'eseguibile, esclusa da git),
  la chiave PUBBLICA è incorporata qui sotto (è pubblica per costruzione);
- installer:       l'eseguibile PyInstaller one-file stesso, prodotto con
  ``pyinstaller MagazzinoProfili.spec``;
- URL installer:   ``https://<host>:<porta-web>/update/MagazzinoProfili-<X.Y.Z>.exe``;
- recovery:        l'eseguibile in esecuzione non viene MAI modificato;
  il download avviene in ``%LOCALAPPDATA%\\magazzino_profili\\aggiornamenti``;
  a ogni errore il file parziale è eliminato e l'app continua a funzionare
  (procedura testuale in :func:`testo_recupero`).

Qui c'è: confronto versioni, download su file temporaneo, controllo di
dimensione e checksum, verifica di firma, un solo download alla volta,
nessun file "pubblico" prima della verifica, riavvio controllato.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Callable, ContextManager, Iterator

_VERSIONE = re.compile(r"([0-9]+)\.([0-9]+)\.([0-9]+)")
_SHA256 = re.compile(r"[0-9a-f]{64}")
DIMENSIONE_BLOCCO = 64 * 1024
GITHUB_FEED = 'https://github.com/Si2008/Magazzino/releases/latest/download/manifest.json'


class ErroreAggiornamento(Exception):
    """Messaggio sempre in italiano, mostrabile all'utente così com'è."""


@dataclass(frozen=True)
class Manifest:
    """Forma NORMALIZZATA: il parser del feed reale deve produrre questa."""

    versione: str
    url_installer: str
    sha256: str  # esadecimale minuscolo
    dimensione: int  # byte
    note: str | None = None  # testo facoltativo mostrato all'utente
    firmato: dict | None = field(default=None, compare=False, repr=False)

    def __post_init__(self) -> None:
        parse_versione(self.versione)
        _url_installer_accettabile(self.url_installer)
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


def _url_installer_accettabile(url: str) -> None:
    """HTTPS obbligatorio; ``http`` solo per localhost (server locale di test)."""
    if isinstance(url, str) and url.startswith("https://"):
        return
    if isinstance(url, str) and url.startswith("http://"):
        host = url[len("http://") :].split("/")[0].split(":")[0]
        if host in ("localhost", "127.0.0.1"):
            return
    raise ErroreAggiornamento(
        "L'indirizzo dell'installer deve usare HTTPS (http solo per localhost)."
    )


# Chiave PUBBLICA Ed25519 (base64) del publisher "Magazzino Profili".
# È pubblica per costruzione: va bene che sia dentro l'eseguibile.
# La chiave privata corrispondente è in firme/chiave_privata.pem (mai qui).
# Per ruotare la firma: rigenerare la coppia, incollare il nuovo valore,
# rifirmare il manifest e ricondizionare l'eseguibile (vedi firme/README.md).
CHIAVE_PUBBLICA_ED25519_B64 = "1mX8/jUbj2hsffLxSpv2T12qbJbFjht/gDzW87WB8KU="


def forma_canonica(dati: dict) -> bytes:
    """Forma canonica del manifest firmata: chiavi ordinate, JSON compatto, UTF-8."""
    return json.dumps(dati, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def firma_valida(
    dati: dict,
    firma_base64: str,
    chiave_pubblica_b64: str = CHIAVE_PUBBLICA_ED25519_B64,
) -> bool:
    """Verifica la firma Ed25519 sul manifest (senza la chiave: solo la PUBBLICA)."""
    import base64

    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError:
        # Libreria di crittografia non installata: rifiuto (fail-closed).
        return False

    try:
        chiave = Ed25519PublicKey.from_public_bytes(
            base64.b64decode(chiave_pubblica_b64)
        )
        chiave.verify(base64.b64decode(firma_base64), forma_canonica(dati))
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def valida_manifest(
    dati: object,
    chiave_pubblica_b64: str = CHIAVE_PUBBLICA_ED25519_B64,
) -> Manifest:
    """Dai dati grezzi del feed al :class:`Manifest` verificato.

    Ordine: campi presenti -> FIRMA valida (prova che i campi non sono stati
    alterati) -> validazione dei singoli campi. Solleva ``ErroreAggiornamento``.
    """
    if not isinstance(dati, dict):
        raise ErroreAggiornamento("Manifest non valido: atteso un oggetto JSON.")
    for campo in ("versione", "url_installer", "sha256", "dimensione", "firma"):
        if campo not in dati:
            raise ErroreAggiornamento(f"Manifest incompleto: manca {campo!r}.")
    firma = dati["firma"]
    corpo = {k: v for k, v in dati.items() if k != "firma"}
    if not firma_valida(corpo, firma, chiave_pubblica_b64):
        raise ErroreAggiornamento(
            "Firma del manifest non valida: l'aggiornamento non è autentico e non verrà installato."
        )
    return Manifest(
        versione=str(dati["versione"]),
        url_installer=str(dati["url_installer"]),
        sha256=str(dati["sha256"]),
        dimensione=dati["dimensione"],
        note=dati.get("note"),
        firmato=dict(dati),
    )


@dataclass(frozen=True)
class ConfigAggiornamento:
    """Sezione ``[update]`` di config.toml (default: disabilitato)."""

    abilitato: bool = False
    feed_url: str | None = None


def leggi_config_aggiornamento(percorso: str | Path | None = None) -> ConfigAggiornamento:
    """Legge la sezione ``[update]`` (assente o illeggibile → disabilitato).

    La sezione è opzionale: la sua assenza non deve mai impedire l'avvio
    dell'app (il feed assente equivale a "nessun aggiornamento").
    """
    import tomllib

    from ..db.config import _candidati_config

    file = next(
        (p for p in _candidati_config(Path(percorso) if percorso is not None else None) if p.is_file()),
        None,
    )
    if file is None:
        return ConfigAggiornamento(True,GITHUB_FEED)
    try:
        with open(file, "rb") as fonte:
            sezione = tomllib.load(fonte).get("update", {})
    except (OSError, tomllib.TOMLDecodeError):
        return ConfigAggiornamento()
    from urllib.parse import urlsplit
    if sezione.get('sorgente')!='personalizzata' and (not sezione.get('feed_url') or urlsplit(sezione.get('feed_url','')).hostname in ('localhost','127.0.0.1')):
        return ConfigAggiornamento(bool(sezione.get('abilitato',True)),GITHUB_FEED)
    return ConfigAggiornamento(
        abilitato=bool(sezione.get("abilitato", False)),
        feed_url=sezione.get("feed_url"),
    )


def leggi_feed(
    feed_url: str,
    apri: Apri | None = None,
    timeout: int = 15,
    chiave_pubblica_b64: str = CHIAVE_PUBBLICA_ED25519_B64,
) -> Manifest:
    """Scarica e verifica il manifest dal feed.

    ``apri`` è iniettato nei test; in produzione usa ``urllib`` con la
    verifica dei certificati ATTIVA (comportamento predefinito). HTTPS
    obbligatorio, tranne localhost (server locale).
    """
    if not isinstance(feed_url, str) or not feed_url.startswith(("https://", "http://")):
        raise ErroreAggiornamento("Indirizzo del feed non valido (atteso http/https).")
    if feed_url.startswith("http://"):
        host = feed_url[len("http://") :].split("/")[0].split(":")[0]
        if host not in ("localhost", "127.0.0.1"):
            raise ErroreAggiornamento("Il feed deve usare HTTPS (http solo per localhost).")

    def _apri_reale(url: str) -> ContextManager[BinaryIO]:
        import urllib.error
        import urllib.request

        @contextmanager
        def _ctx():
            try:
                risposta = urllib.request.urlopen(url, timeout=timeout)
                yield risposta
            except urllib.error.URLError as errore:  # type: ignore[attr-defined]
                raise ErroreAggiornamento(
                    f"Impossibile raggiungere il feed degli aggiornamenti: {errore.reason}"
                ) from errore
            except (OSError, ValueError) as errore:
                raise ErroreAggiornamento(
                    "Errore di rete durante la lettura del feed degli aggiornamenti."
                ) from errore

        return _ctx()

    apri_effettiva = apri if apri is not None else _apri_reale
    try:
        with apri_effettiva(feed_url) as risposta:
            corpo = risposta.read()
    except ErroreAggiornamento:
        raise
    except (OSError, ValueError) as errore:
        raise ErroreAggiornamento("Errore di rete durante la lettura del feed degli aggiornamenti.") from errore
    try:
        dati = json.loads(corpo.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as errore:
        raise ErroreAggiornamento("Manifest non valido: contenuto non è JSON.") from errore
    return valida_manifest(dati, chiave_pubblica_b64)


def apri_url(url: str, timeout: int = 30):
    """Apre una URL (urllib, verifica dei certificati ATTIVA) in un context manager.

    Usato dal worker di download del popup; i test lo sostituiscono con un
    finto. Solleva ``ErroreAggiornamento`` se la rete non risponde.
    """
    import urllib.request

    @contextmanager
    def _ctx():
        try:
            yield from _apri_urllib(url, timeout)
        except (OSError, ValueError) as errore:
            raise ErroreAggiornamento(
                "Errore di rete durante il download dell'installer."
            ) from errore

    return _ctx()


def _apri_urllib(url: str, timeout: int):
    import urllib.request

    risposta = urllib.request.urlopen(url, timeout=timeout)
    try:
        yield risposta
    finally:
        risposta.close()


def cartella_cache() -> Path:
    """Cartella (scrivibile, per utente) in cui si scarica l'installer."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "magazzino_profili" / "aggiornamenti"


def comando_riavvio(percorso_exe: str, attesa_secondi: int = 2) -> list[str]:
    """Comando che riavvia la nuova versione DOPO che la vecchia si è chiusa.

    L'attesa (breve) lascia tempo al processo vecchio di rilasciare il
    database locale: la nuova istanza non parte in competizione con essa.
    """
    if not isinstance(percorso_exe, str) or not percorso_exe.strip():
        raise ErroreAggiornamento("Percorso della nuova versione non valido.")
    if isinstance(attesa_secondi, bool) or not isinstance(attesa_secondi, int) or attesa_secondi < 0:
        raise ErroreAggiornamento("Attesa di riavvio non valida.")
    if sys.platform == "win32":
        letterale = percorso_exe.replace("'", "''")
        return ["powershell.exe", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command",
                f"Start-Sleep -Seconds {attesa_secondi}; Start-Process -FilePath '{letterale}' -WindowStyle Normal"]
    return ["sh", "-c", f"sleep {attesa_secondi}; exec {shlex.quote(percorso_exe)}"]


def lancia_aggiornamento(
    percorso_exe: str,
    attesa_secondi: int = 2,
    esegui: Callable[[list[str]], object] | None = None,
) -> list[str]:
    """Avvia il comando di riavvio in un processo staccato e restituisce il comando.

    ``esegui`` è iniettato nei test (default: ``subprocess.Popen`` staccato).
    """
    comando = comando_riavvio(percorso_exe, attesa_secondi)
    if esegui is not None:
        esegui(comando)
        return comando
    from ..db.config import trova_config
    configurazione = trova_config()
    ambiente = os.environ.copy()
    if configurazione is not None:
        ambiente["MAGAZZINO_CONFIG"] = str(configurazione)
    if sys.platform == "win32":
        Popen = subprocess.Popen  # type: ignore[misc]
        Popen(
            comando,
            close_fds=True,
            env=ambiente,
            cwd=str(configurazione.parent) if configurazione else None,
            creationflags=0x00000008 | 0x00000200,  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        )
    else:
        subprocess.Popen(comando, close_fds=True, start_new_session=True, env=ambiente,
                         cwd=str(configurazione.parent) if configurazione else None)
    return comando


def _cartella_versioni():
    return cartella_cache().parent / "versioni"


def prepara_versione(manifest, eseguibile):
    """Versione stabile verificata; non sostituisce né cancella quella in uso."""
    from ..file_sicuri import destinazione_atomica
    import shutil
    if manifest.firmato is None:
        raise ErroreAggiornamento("Manifest firmato assente: installazione automatica rifiutata")
    verificato = valida_manifest(manifest.firmato)
    origine = Path(eseguibile)
    with origine.open("rb") as file:
        digest = hashlib.file_digest(file, "sha256").hexdigest()
    if origine.stat().st_size != verificato.dimensione or digest != verificato.sha256:
        raise ErroreAggiornamento("Eseguibile modificato dopo il download")
    from urllib.parse import urlsplit
    if urlsplit(verificato.url_installer).path.lower().endswith('.zip'):
        from .pacchetto_aggiornamento import installa_zip
        return installa_zip(verificato,origine,_cartella_versioni())
    cartella = _cartella_versioni() / verificato.versione
    cartella.mkdir(parents=True, exist_ok=True)
    finale = cartella / "MagazzinoProfili.exe"
    if origine.resolve() != finale.resolve():
        with destinazione_atomica(finale) as temporaneo:
            shutil.copy2(origine, temporaneo)
    with destinazione_atomica(cartella / "manifest.json") as temporaneo:
        temporaneo.write_text(json.dumps(manifest.firmato, ensure_ascii=False), encoding="utf-8")
    return finale


def conferma_versione_avviata():
    """Attiva il launcher solo dopo l'apertura riuscita della nuova UI."""
    if not getattr(sys, "frozen", False):
        return
    from .. import __version__
    from ..file_sicuri import destinazione_atomica
    propria = Path(sys.executable).resolve()
    attesa = (_cartella_versioni() / __version__ / "MagazzinoProfili.exe").resolve()
    if propria != attesa:
        return
    dati = json.loads(propria.with_name("manifest.json").read_text(encoding="utf-8"))
    manifest = valida_manifest(dati)
    if manifest.versione != __version__:
        raise ErroreAggiornamento("La versione avviata non corrisponde al manifest firmato")
    with destinazione_atomica(_cartella_versioni() / "attiva.json") as temporaneo:
        temporaneo.write_text(json.dumps(dati, ensure_ascii=False), encoding="utf-8")


def avvia_versione_attiva():
    """Il collegamento originale resta valido. --versione-originale consente il recupero."""
    if not getattr(sys, "frozen", False) or "--versione-originale" in sys.argv or "--server-telefono" in sys.argv:
        return False
    from .. import __version__
    file = _cartella_versioni() / "attiva.json"
    if not file.is_file():
        return False
    try:
        dati = json.loads(file.read_text(encoding="utf-8"))
        manifest = valida_manifest(dati)
        if not esiste_aggiornamento(manifest.versione, __version__):
            return False
        exe = _cartella_versioni() / manifest.versione / "MagazzinoProfili.exe"
        with exe.open("rb") as contenuto:
            digest = hashlib.file_digest(contenuto, "sha256").hexdigest()
        atteso = (manifest.firmato or {}).get('sha256_eseguibile',manifest.sha256)
        if digest != atteso or ('sha256_eseguibile' not in (manifest.firmato or {}) and exe.stat().st_size != manifest.dimensione):
            return False
        lancia_aggiornamento(str(exe), 0)
        return True
    except (OSError, ValueError, ErroreAggiornamento):
        import logging
        logging.getLogger(__name__).exception("Versione attiva non disponibile: avvio la versione originale")
        return False


def testo_recupero() -> str:
    """Procedura di recovery (mostrata all'utente a ogni errore)."""
    return (
        "Recupero: l'applicazione in uso non è stata modificata e continua a funzionare.\n"
        "1) Chiudere e riaprire l'applicazione: la verifica verrà ripetuta.\n"
        "2) Se il problema persiste, verificare la connessione al server degli"
        " aggiornamenti.\n"
        "3) Installazione manuale: scaricare l'eseguibile dalla cartella\n"
        "   %LOCALAPPDATA%\\magazzino_profili\\aggiornamenti (se presente) o dalla"
        " cartella release del server, e avviarlo al posto di quello attuale.\n"
        "4) Nessun dato dell'applicazione (database, impostazioni, file utente)"
        " viene toccato dall'aggiornamento."
    )


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
    try:
        from ..file_sicuri import blocco_cartella
        try:
            with blocco_cartella(cartella, attendi=False):
                yield
        except (BlockingIOError, PermissionError) as errore:
            raise ErroreAggiornamento("Un altro processo sta già scaricando un aggiornamento") from errore
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
    da eseguire. La cartella di destinazione viene creata se mancante.
    """
    Path(cartella).mkdir(parents=True, exist_ok=True)
    cartella = Path(cartella)
    cartella.mkdir(parents=True, exist_ok=True)
    from urllib.parse import urlsplit
    estensione='.zip' if urlsplit(manifest.url_installer).path.lower().endswith('.zip') else '.exe'
    nome = f"Installer-{manifest.versione}{estensione}"
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
