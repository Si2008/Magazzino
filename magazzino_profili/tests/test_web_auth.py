"""Test dell'autenticazione web: login e token (firma, scadenza, integrità).

Si usa un database SQLite in memoria condiviso da tutte le sessioni
(StaticPool), così l'app FastAPI e i test leggono gli stessi dati.
"""

import time

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from magazzino_profili.db import crea_session_factory, crea_tabelle
from magazzino_profili.sicurezza import Ruolo, crea_utente
from magazzino_profili.web.app import crea_app
from magazzino_profili.web.auth import crea_token

SEGRET0_TEST = "segreto-di-test-molto-lungo-1234567890"


def _app_con_utente(durata_token_secondi: int = 3600) -> tuple[TestClient, object]:
    """App con un utente OPERATORE in un database di test in memoria."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    crea_tabelle(engine)
    factory = crea_session_factory(engine)
    with factory() as session:
        crea_utente(session, "maria", "segreta", Ruolo.OPERATORE)

    app = crea_app(
        session_factory=factory,
        durata_token_secondi=durata_token_secondi,
        segrete_token=SEGRET0_TEST,
    )
    return TestClient(app), factory


def test_login_con_credenziali_corrette_restituisce_token() -> None:
    client, _ = _app_con_utente()
    risposta = client.post(
        "/api/login", json={"utente": "maria", "password": "segreta"}
    )
    assert risposta.status_code == 200
    corpo = risposta.json()
    assert corpo["token"]
    assert corpo["utente"] == "maria"
    assert corpo["ruolo"] == "OPERATORE"

    # Il token appena ottenuto è accettato su un endpoint protetto:
    # con un barcode inesistente ci si aspetta 404 (non 401).
    risposta2 = client.post(
        "/api/carico",
        json={"barcode": "INE-SESTE-0001", "quantita": 1},
        headers={"Authorization": f"Bearer {corpo['token']}"},
    )
    assert risposta2.status_code == 404


def test_login_con_password_errata_restituisce_401() -> None:
    client, _ = _app_con_utente()
    risposta = client.post(
        "/api/login", json={"utente": "maria", "password": "sbagliata"}
    )
    assert risposta.status_code == 401
    assert "detail" in risposta.json()


def test_login_con_utente_inesistente_restituisce_401() -> None:
    client, _ = _app_con_utente()
    risposta = client.post(
        "/api/login", json={"utente": "nobody", "password": "qualsiasi"}
    )
    assert risposta.status_code == 401
    assert "detail" in risposta.json()


def test_token_scaduto_viene_rifiutato() -> None:
    # Durata di 1 secondo: dopo l'attesa il token non è più valido.
    client, _ = _app_con_utente(durata_token_secondi=1)
    token = client.post(
        "/api/login", json={"utente": "maria", "password": "segreta"}
    ).json()["token"]
    assert token

    # Subito dopo il login il token è ancora valido (404, non 401).
    risposta = client.post(
        "/api/carico",
        json={"barcode": "INE-SESTE-0001", "quantita": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert risposta.status_code == 404

    time.sleep(1.1)
    risposta2 = client.post(
        "/api/carico",
        json={"barcode": "INE-SESTE-0001", "quantita": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert risposta2.status_code == 401
    assert "detail" in risposta2.json()


def test_token_ritoccato_viene_rifiutato() -> None:
    client, _ = _app_con_utente()
    token = client.post(
        "/api/login", json={"utente": "maria", "password": "segreta"}
    ).json()["token"]
    risposta = client.post(
        "/api/carico",
        json={"barcode": "X", "quantita": 1},
        headers={"Authorization": f"Bearer {token}xx"},
    )
    assert risposta.status_code == 401


def test_token_firmato_con_segrete_diversa_viene_rifiutato() -> None:
    client, _ = _app_con_utente()
    token = crea_token("maria", "OPERATORE", 3600, b"segrete-avversaria")
    risposta = client.post(
        "/api/carico",
        json={"barcode": "X", "quantita": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert risposta.status_code == 401
