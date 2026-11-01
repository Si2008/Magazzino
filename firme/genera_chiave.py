"""Rigenera la coppia di chiavi Ed25519 del publisher "Magazzino Profili".

USO (raro: solo per ruotare la firma)::

    .venv/Scripts/python.exe firme/genera_chiave.py

Stampa la chiave PUBBLICA (base64) da incollare in
``magazzino_profili/services/aggiornamenti.py`` (CHIAVE_PUBBLICA_ED25519_B64)
e scrive la chiave PRIVATA in ``firme/chiave_privata.pem``.

REGOLE DI CUSTODIA
------------------
- La chiave privata NON deve mai finire in git, nell'eseguibile o nel feed.
- Chi ha la chiave privata può pubblicare un "aggiornamento" credibile:
  conservarla come un segreto (disco cifrato / password manager).
- Dopo la rotazione: rifirmare il manifest e ricondizionare l'eseguibile,
  altrimenti i vecchi client rifiutano il nuovo feed (è il comportamento
  CORRETTO: non accettano firme di chiavi non note).
"""

from __future__ import annotations

import base64
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def main() -> None:
    chiave = Ed25519PrivateKey.generate()
    cartella = Path(__file__).resolve().parent
    privata = cartella / "chiave_privata.pem"
    pem = chiave.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    privata.write_bytes(pem)
    try:
        privata.chmod(0o600)
    except OSError:
        pass  # su file system che non supportano i permessi
    pubblica = base64.b64encode(
        chiave.public_key().public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
        )
    ).decode("ascii")
    print("Chiave privata scritta in:", privata)
    print()
    print("Incollare in magazzino_profili/services/aggiornamenti.py:")
    print(f"CHIAVE_PUBBLICA_ED25519_B64 = \"{pubblica}\"")


if __name__ == "__main__":
    main()
