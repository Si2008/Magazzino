# Firma dei rilasci — "Magazzino Profili"

## I nove valori della Fase 13 (decisi dal proprietario)

| # | Valore | Scelta |
|---|--------|--------|
| 1 | URL del feed | `https://<host>:<porta-web>/update/manifest.json` — valore concreto in `[update] feed_url` di `config.toml`; il feed è servito dal server web dell'app (`web/routes_update.py`) |
| 2 | Publisher | **Magazzino Profili** |
| 3 | Formato del manifest | JSON: `versione` (X.Y.Z), `url_installer`, `sha256`, `dimensione`, `pubblicato`, `note`, `firma` (base64) — esempio in `release/manifest.json` |
| 4 | Versione installata | `magazzino_profili.__version__` |
| 5 | Algoritmo di firma | **Ed25519 (RFC 8032)** sul manifest in forma canonica (JSON chiavi ordinate); integrità installer con **SHA-256** preso dal manifest firmato |
| 6 | Certificato/chiave | Coppia Ed25519 autofirmata: privata in `firme/chiave_privata.pem` (mai in git, mai nell'eseguibile), pubblica incorporata in `services/aggiornamenti.py` (`CHIAVE_PUBBLICA_ED25519_B64`) |
| 7 | Installer | L'eseguibile **PyInstaller one-file** stesso; produzione: `.venv/Scripts/python.exe -m PyInstaller MagazzinoProfili.spec --noconfirm` |
| 8 | URL installer | `https://<host>:<porta-web>/update/MagazzinoProfili-<X.Y.Z>.exe` |
| 9 | Recupero | L'eseguibile in uso non è mai modificato; download in `%LOCALAPPDATA%\magazzino_profili\aggiornamenti`; su errore il file parziale è eliminato e l'app continua a funzionare; installazione manuale = avviare l'eseguibile scaricato al posto del vecchio |

## Custodia della chiave privata

- `firme/chiave_privata.pem` è esclusa da git (`.gitignore`) e mai incrostata
  nell'eseguibile.
- Chi la possiede può pubblicare aggiornamenti "credibili": trattarla come un
  segreto (disco cifrato / password manager).
- **Rotazione**: `python firme/genera_chiave.py` → incollare la nuova chiave
  pubblica in `services/aggiornamenti.py` → rifirmare il manifest →
  ricondizionare l'eseguibile. I client con la vecchia chiave pubblica
  rifiuteranno il nuovo feed: è il comportamento corretto.

## Procedura di rilascio (checklist)

1. `magazzino_profili/__init__.py`: alzare `__version__` (X.Y.Z).
2. Build: `.venv/Scripts/python.exe -m PyInstaller MagazzinoProfili.spec --noconfirm`.
3. Firma Authenticode (se disponibile signtool/pyauthenticode): vedere
   `firma_eseguibile.py` in questa cartella.
4. Copiare l'eseguibile in `release/MagazzinoProfili-<X.Y.Z>.exe`.
5. Calcolare `sha256sum` e dimensione; scrivere `release/manifest.json`
   (senza `firma`) con `url_installer` https del punto 8.
6. `python firme/firma_manifest.py release/manifest.json --out release/manifest.json`
   (o sovrascrivere: il feed serve `release/manifest.json`).
7. Pubblicare la cartella `release/` sul server web (TLS): il server
   dell'app la serve già su `/update/...` se `[update] cartella_rilasci`
   punta ad essa.
8. Verifica da un client: l'app mostra il popup, scarica, verifica
   dimensione + SHA-256 + firma e si riapre con la nuova versione.
