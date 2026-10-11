"""Pacchetto web: scansione barcode dal telefono, accesso solo remoto.

Il server web è un processo SEPARATO dall'app desktop PySide6: gira con
``python -m magazzino_profili.web.app`` e condivide lo stesso database
PostgreSQL, richiamando i servizi già esistenti (``carica``/``scarica``).

Regole di sicurezza del modulo:
- HTTPS obbligatorio: il server non accetta connessioni HTTP in chiaro;
  certificato e chiave si leggono da ``config.toml`` (sezione ``[web]``);
- autenticazione obbligatoria su ogni endpoint di scansione: login con
  utente/password (riuso di ``sicurezza/utenti.py``) che restituisce un
  token con scadenza, da inviare come ``Authorization: Bearer <token>``;
- nessuna presunzione di rete locale: il telefono si collega via
  internet (rete dati mobile), quindi l'esposizione del PC su internet
  (port forwarding o tunnel) è una configurazione di RETE esterna a
  questo modulo.
"""

from .app import crea_app, leggi_sezione_web

__all__ = ["crea_app", "leggi_sezione_web"]
