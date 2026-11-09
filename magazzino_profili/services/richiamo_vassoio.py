"""Controlli fail-closed per un richiamo ICON; nessun movimento HTTP da Python."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import json
import re
import sys
from datetime import datetime, timezone

from ..db.config import leggi_sezione
from .consultazione import pezzo_per_barcode


@dataclass(frozen=True)
class Candidato:
    barcode: str
    codice: str
    descrizione: str
    uds: str
    ident: int


def configurazione():
    sezione, _ = leggi_sezione('icon')
    modo = sezione.get('modalita', 'simulazione')
    if modo not in ('simulazione', 'icon'):
        raise ValueError('Modalità ICON non valida')
    origine = str(sezione.get('origine', 'http://localhost')).rstrip('/')
    from urllib.parse import urlsplit
    url = urlsplit(origine)
    try:
        porta = url.port
    except ValueError as errore:
        raise ValueError('Porta ICON non valida') from errore
    if (url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password
            or url.path or url.query or url.fragment or (porta is not None and porta <= 0)):
        raise ValueError('Origine ICON non valida')
    return modo, origine


def codice_uds(vassoio: str, mappa: dict[str, str] | None = None) -> str:
    valore = (vassoio or '').strip()
    mappato = bool(mappa and valore in mappa)
    if mappa and valore in mappa:
        valore = mappa[valore]
    # Nessun padding implicito: 1 e 0001 non sono equivalenti senza mappa.
    if (not isinstance(valore, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,32}', valore)
            or valore.lower() in ('non_indicato', 'da_confermare', 'incerto')
            or (valore.isdigit() and len(valore) < 4 and not mappato)):
        raise ValueError('Vassoio mancante o incerto: serve un codice UDS esatto')
    return valore


def candidato(factory, barcode: str, *, chiave: str | None = None) -> Candidato:
    with factory() as sessione:
        pezzo = pezzo_per_barcode(sessione, barcode)
        if pezzo is None:
            raise ValueError('Barcode non trovato tra i pezzi attivi')
        if chiave is not None and chiave != f'pezzo:{pezzo.id}':
            raise ValueError('La riga selezionata è cambiata')
        if pezzo.quantita <= 0 or pezzo.stato == 'Scaricato':
            raise ValueError('Il pezzo non è più disponibile in magazzino')
        if not (pezzo.numero_vassoio or '').strip():
            raise ValueError('Nessun vassoio associato a questo barcode. Nei dettagli della riga, usa «Imposta vassoio» e inserisci il codice UDS esatto di ICON.')
        sezione, _ = leggi_sezione('icon')
        mappa = sezione.get('mappa_vassoi', {})
        if not isinstance(mappa, dict):
            raise ValueError('Mappa vassoi ICON non valida')
        uds = codice_uds(pezzo.numero_vassoio, mappa)
        return Candidato(pezzo.barcode, pezzo.profilo.codice,
                         pezzo.profilo.descrizione or '', uds, pezzo.id)


def credenziale_windows():
    if sys.platform != 'win32':
        return None
    class CREDENTIAL(ctypes.Structure):
        _fields_ = [('Flags', wintypes.DWORD), ('Type', wintypes.DWORD),
                    ('TargetName', wintypes.LPWSTR), ('Comment', wintypes.LPWSTR),
                    ('LastWritten', wintypes.FILETIME), ('CredentialBlobSize', wintypes.DWORD),
                    ('CredentialBlob', ctypes.c_void_p), ('Persist', wintypes.DWORD),
                    ('AttributeCount', wintypes.DWORD), ('Attributes', ctypes.c_void_p),
                    ('TargetAlias', wintypes.LPWSTR), ('UserName', wintypes.LPWSTR)]
    api = ctypes.WinDLL('Advapi32.dll')
    ptr = ctypes.POINTER(CREDENTIAL)()
    read = api.CredReadW
    read.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                     ctypes.POINTER(ctypes.POINTER(CREDENTIAL))]
    read.restype = wintypes.BOOL
    free = api.CredFree
    free.argtypes = [ctypes.c_void_p]
    if not read('MagazzinoProfili/ICON', 1, 0, ctypes.byref(ptr)):
        return None
    try:
        c = ptr.contents
        raw = ctypes.string_at(c.CredentialBlob, c.CredentialBlobSize)
        return c.UserName, raw.decode('utf-16-le')
    finally:
        free(ptr)


def script_login_icon(origine: str, utente: str, password: str) -> str:
    dati = json.dumps(dict(origine=origine, utente=utente, password=password))
    return f'''(() => {{
      const dati = {dati};
      if (location.origin !== dati.origine) return false;
      const form = document.querySelector("#_login_Form");
      if (!(form instanceof HTMLFormElement) || form.method !== "post") return false;
      const action = new URL(form.action, location.href);
      if (action.origin !== dati.origine || action.pathname !== "/Account/Login") return false;
      const utente = form.querySelector("#hiddenUsername");
      const password = form.querySelector("#hiddenPassword");
      if (!utente || !password) return false;
      utente.value = dati.utente;
      password.value = dati.password;
      HTMLFormElement.prototype.submit.call(form);
      return true;
    }})()'''


def registra(origine: str, uds: str, silo: str, modo: str, esito: str, durata: float):
    from ..percorsi_installazione import dati_runtime
    base = dati_runtime()
    base.mkdir(parents=True, exist_ok=True)
    with (base / 'richiami_vassoio.jsonl').open('a', encoding='utf-8') as file:
        file.write(json.dumps(dict(data=datetime.now(timezone.utc).isoformat(),
            origine=origine, uds=uds, silo=silo, modalita=modo,
            esito=esito, durata_secondi=round(durata, 2))) + '\n')
