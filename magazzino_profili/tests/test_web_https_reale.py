"""Fase 9 — prova HTTPS reale: una connessione TLS vera verso 127.0.0.1.

Genera un certificato auto-firmato (solo per la prova locale), avvia il
server web con uvicorn su una porta locale e fa richieste con un client
reale. Serve ``cryptography`` (per generare il certificato) e ``httpx``
(o ``httpx2``). Nessun telefono fisico.
"""

from __future__ import annotations

import ipaddress
import ssl
import socket
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

try:
    import httpx
except ImportError:  # pragma: no cover - dipende dall'ambiente
    import httpx2 as httpx

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from magazzino_profili.db import crea_session_factory, crea_tabelle
from magazzino_profili.sicurezza import crea_utente, Ruolo
from magazzino_profili.web.app import crea_app


def _porta_libera() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    porta = s.getsockname()[1]
    s.close()
    return porta


def _certificato_autofirmato(cartella: Path) -> tuple[str, str]:
    """Certificato auto-firmato per 127.0.0.1, valido un giorno (solo prova)."""
    chiave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")])
    adesso = datetime.now(timezone.utc)
    certificato = (
        x509.CertificateBuilder()
        .subject_name(nome)
        .issuer_name(nome)
        .public_key(chiave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(adesso)
        .not_valid_after(adesso + timedelta(days=1))
        .add_extension(
        x509.SubjectAlternativeName([x509.IPAddress(ipaddress.IPv4Address("127.0.0.1"))]),
        critical=False,
    )
        .sign(chiave, hashes.SHA256())
    )
    pem = cartella / "cert.pem"
    key = cartella / "chiave.pem"
    pem.write_bytes(certificato.public_bytes(serialization.Encoding.PEM))
    key.write_bytes(
        chiave.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return str(pem), str(key)


@pytest.fixture()
def server_https(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    import uvicorn

    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    crea_tabelle(engine)
    factory = crea_session_factory(engine)
    with factory() as session:
        crea_utente(session, "remoto", "Password123!", Ruolo.AMMINISTRATORE)
        session.commit()

    app = crea_app(session_factory=factory, durata_token_secondi=3600, segrete_token="segreto-di-https-molto-lungo-1234567890")
    pem, chiave = _certificato_autofirmato(tmp_path)
    porta = _porta_libera()

    config = uvicorn.Config(app, host="127.0.0.1", port=porta, ssl_certfile=pem, ssl_keyfile=chiave, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(200):
        if server.started:
            break
        time.sleep(0.05)
    assert server.started, "il server HTTPS non è partito"
    yield {"base": f"https://127.0.0.1:{porta}", "pem": pem}
    server.should_exit = True
    thread.join(timeout=5)


def test_https_reale_login_e_consultazione(server_https):
    base = server_https["base"]
    client = httpx.Client(verify=ssl.create_default_context(cafile=server_https["pem"]), timeout=5)
    r = client.post(f"{base}/api/login", json={"utente": "remoto", "password": "Password123!"})
    assert r.status_code == 200
    token = r.json()["token"]

    # il percorso HTTP in chiaro NON deve essere servito
    with pytest.raises(Exception):
        httpx.Client(verify=False, timeout=2).get(base.replace("https://", "http://"))

    # senza token: 401 (prova che il server risponde in HTTPS)
    r2 = client.get(f"{base}/api/pezzi/X")
    assert r2.status_code == 401

    # con token ma barcode inesistente: 404 (server raggiungibile in HTTPS)
    r3 = client.get(f"{base}/api/pezzi/X", headers={"Authorization": f"Bearer {token}"})
    assert r3.status_code == 404
