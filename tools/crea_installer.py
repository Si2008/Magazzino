"""Build verificata PyInstaller -> Inno Setup. Nessuna installazione sul PC di sviluppo."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

RADICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RADICE))
from magazzino_profili import __version__
from magazzino_profili.distribuzione import APP_ID, EDITORE, MUTEX_APPLICAZIONE
from magazzino_profili.db.migrazioni import schema_atteso, versione_schema_attesa


def controlla_payload(cartella):
    if not (cartella / "MagazzinoProfili.exe").is_file():
        raise ValueError("Eseguibile PyInstaller assente")
    for p in cartella.rglob("*"):
        if p.is_symlink() or p.is_junction():
            raise ValueError("Collegamento nel payload: " + str(p))
        if not p.is_file(): continue
        nome = p.name.lower()
        if (nome == "config.toml" or p.suffix.lower() in (".dump", ".db", ".sqlite", ".sqlite3", ".key")
                or "privata" in nome or "private_key" in nome):
            raise ValueError("Dato o segreto vietato nel payload: " + str(p.relative_to(cartella)))
    for risorsa in ("_internal/migrations", "catalogo_immagini/Indice_profili_aggiornato.csv",
                    "_internal/magazzino_profili/web/templates/scansione.html", "config.example.toml"):
        if not (cartella / risorsa).exists():
            raise ValueError("Risorsa necessaria assente: " + risorsa)


def scrivi_manifest(setup, destinazione, chiave):
    from cryptography.hazmat.primitives.serialization import load_pem_private_key, Encoding, PublicFormat
    from magazzino_profili.services.aggiornamenti import CHIAVE_PUBBLICA_ED25519_B64, forma_canonica, valida_manifest
    privata = load_pem_private_key(chiave.read_bytes(), password=None)
    pubblica = base64.b64encode(privata.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()
    if pubblica != CHIAVE_PUBBLICA_ED25519_B64:
        raise ValueError("La chiave non corrisponde alla chiave pubblica del programma")
    with setup.open("rb") as f: sha = hashlib.file_digest(f, "sha256").hexdigest()
    dati = {"versione": __version__, "tipo": "setup",
            "url_installer": f"https://github.com/Si2008/Magazzino/releases/download/v{__version__}/{setup.name}",
            "sha256": sha,
            "dimensione": setup.stat().st_size,
            "pubblicato": datetime.now(timezone.utc).isoformat(),
            "note": "Installazione Windows per utente; dati conservati durante aggiornamento."}
    dati["firma"] = base64.b64encode(privata.sign(forma_canonica(dati))).decode()
    valida_manifest(dati)
    (destinazione / "manifest.json").write_text(json.dumps(dati, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--destinazione", required=True, type=Path)
    p.add_argument("--iscc", type=Path, default=Path(os.environ.get("ISCC_PATH", RADICE / "dist/strumenti-installer/inno-7.1.1/ISCC.exe")))
    p.add_argument("--chiave-manifest", type=Path, help="Firma Ed25519 per aggiornamenti online, distinta da Authenticode")
    p.add_argument("--certificato", help="Thumbprint certificato Authenticode nel certificati utente; opzionale")
    p.add_argument("--signtool", default="signtool.exe")
    a = p.parse_args()
    destinazione = a.destinazione.resolve()
    if destinazione.exists(): raise SystemExit("Scegli una destinazione nuova: nessun output esistente viene sovrascritto")
    if not a.iscc.is_file(): raise SystemExit("ISCC non trovato: indica --iscc oppure ISCC_PATH")
    destinazione.mkdir(parents=True)
    subprocess.run([sys.executable, "-B", str(RADICE / "tools/compila_windows.py"),
                    "--destinazione", str(destinazione / "build")], check=True, cwd=RADICE)
    payload = destinazione / "build" / ("MagazzinoProfili-" + __version__)
    controlla_payload(payload)
    identita = {"app_id": APP_ID, "versione": __version__, "schema": versione_schema_attesa(), "migrazioni": schema_atteso()}
    (payload / "installazione.json").write_text(json.dumps(identita, ensure_ascii=False, indent=2), encoding="utf-8")
    def firma(file):
        if a.certificato:
            subprocess.run([a.signtool, "sign", "/sha1", a.certificato, "/fd", "SHA256", "/tr",
                            "http://timestamp.digicert.com", "/td", "SHA256", str(file)], check=True)
    firma(payload / "MagazzinoProfili.exe")
    with (destinazione / "inno-setup.log").open("w", encoding="utf-8") as log:
        subprocess.run([str(a.iscc.resolve()), "/DAppVersion=" + __version__, "/DAppIdFisso=" + APP_ID,
                        "/DMutexApp=" + MUTEX_APPLICAZIONE, "/DEditore=" + EDITORE,
                        "/DPayload=" + str(payload), "/DOutput=" + str(destinazione),
                        str(RADICE / "installer/MagazzinoProfili.iss")], check=True, stdout=log, stderr=subprocess.STDOUT)
    versione = destinazione / f"MagazzinoProfili-{__version__}-setup.exe"
    if not versione.is_file() or not versione.stat().st_size: raise SystemExit("Inno non ha creato il setup")
    firma(versione)
    setup = destinazione / "setup.exe"
    shutil.copy2(versione, setup)
    with setup.open("rb") as f: sha = hashlib.file_digest(f, "sha256").hexdigest()
    (destinazione / "SHA256SUMS.txt").write_text(sha + "  setup.exe\n" + sha + "  " + versione.name + "\n", encoding="ascii")
    if a.chiave_manifest: scrivi_manifest(versione, destinazione, a.chiave_manifest)
    print("Setup generato e NON installato:", setup)
    print("SHA-256:", sha)


if __name__ == "__main__":
    main()
