"""Firma un manifest di rilascio (Fase 13) e produce il manifest firmato.

USO::

    .venv/Scripts/python.exe firme/firma_manifest.py MANIFEST.json [--out MANIFEST.firmato.json]

Il manifest in ingresso è JSON con i campi:
    versione, url_installer, sha256, dimensione, pubblicato, note
(la ``firma`` non va inclusa: viene aggiunta da qui).

La firma è Ed25519 (RFC 8032) sulla forma canonica definita UNICA volta in
``magazzino_profili.services.aggiornamenti.forma_canonica`` — lo strumento di
firma e l'applicazione che verifica condividono la stessa funzione, quindi
non possono divergere.

La chiave privata è ``firme/chiave_privata.pem`` (mai in git, mai
nell'eseguibile).
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cryptography.hazmat.primitives import serialization  # noqa: E402

from magazzino_profili.services.aggiornamenti import forma_canonica  # noqa: E402

CHIAVE_PRIVATA = Path(__file__).resolve().parent / "chiave_privata.pem"


def firma_manifest(dati: dict, percorso_chiave: Path = CHIAVE_PRIVATA) -> dict:
    """Restituisce una COPIA del manifest con il campo ``firma`` (base64)."""
    if not percorso_chiave.is_file():
        raise SystemExit(
            f"Chiave privata non trovata: {percorso_chiave}. Rigenerarla con firme/genera_chiave.py."
        )
    chiave = serialization.load_pem_private_key(
        percorso_chiave.read_bytes(), password=None
    )
    corpo = {k: v for k, v in dati.items() if k != "firma"}
    firma = chiave.sign(forma_canonica(corpo))
    uscita = dict(dati)
    uscita["firma"] = base64.b64encode(firma).decode("ascii")
    return uscita


def main() -> None:
    parser = argparse.ArgumentParser(description="Firma un manifest di rilascio.")
    parser.add_argument("manifest", help="path del manifest JSON (senza firma)")
    parser.add_argument("--out", default=None, help="path di uscita (default: accanto, con suffisso .firmato.json)")
    args = parser.parse_args()

    sorgente = Path(args.manifest)
    if not sorgente.is_file():
        raise SystemExit(f"Manifest non trovato: {sorgente}")
    dati = json.loads(sorgente.read_text(encoding="utf-8"))
    firmato = firma_manifest(dati)

    destinazione = args.out or str(sorgente.with_name(sorgente.stem + ".firmato.json"))
    Path(destinazione).write_text(
        json.dumps(firmato, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Manifest firmato scritto in: {destinazione}")
    print("Firma (base64):", firmato["firma"])


if __name__ == "__main__":
    main()
