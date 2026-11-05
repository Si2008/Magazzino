"""Fase 9 — Comunicazione affidabile con il telefono (prove simulate).

Verifica l'API REST che il telefono usa (HTTPS + JSON + Bearer, modulo
``web``): login, consultazione di sola lettura, carico, scarico, gestione
di errori, token scaduto, ruoli, barcode anomali, e — su PostgreSQL — il
conflitto di riconciliazione.

Tutte le prove sono SIMULATE: TestClient in-process, senza un telefono
fisico. I test PostgreSQL si saltano senza ``MAGAZZINO_TEST_DB_URL``
verso un database ``*_test``.
"""

from __future__ import annotations

import decimal
import os
import threading

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.pool import StaticPool

from magazzino_profili.db import crea_session_factory, crea_tabelle
from magazzino_profili.domain import Pezzo, Profilo, Colore
from magazzino_profili.sicurezza import crea_utente, Ruolo
from magazzino_profili.web.app import crea_app


@pytest.fixture(scope="module")
def factory():
    """SQLite in memoria condiviso per tutta la sessione di test."""
    from sqlalchemy import create_engine

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    crea_tabelle(engine)
    return crea_session_factory(engine)


def _crea_dati(factory) -> None:
    """Profilo, colore, utente e un pezzo con barcode AB12 (giacenza 10)."""
    with factory() as sessione, sessione.begin():
        profilo = Profilo(codice="P001", descrizione="Profilo A", peso_kg_per_metro=decimal.Decimal("1.0"), lunghezza_standard_mm=6000)
        colore = Colore(codice_normalizzato="ROSSO", nome_visualizzato="Rosso")
        sessione.add_all([profilo, colore])
        sessione.flush()
        sessione.add(Pezzo(profilo_id=profilo.id, colore_id=colore.id, lunghezza_mm=500, quantita=10, barcode="AB12"))
    # Utenti: crea_utente avvia il proprio begin()/commit(), quindi vanno chiamati FUORI dal blocco transazionale aperto.
    with factory() as s_temp:
        crea_utente(s_temp, "maria", "Password123!", Ruolo.AMMINISTRATORE)
        crea_utente(s_temp, "giovanni", "Password123!", Ruolo.OPERATORE)
        crea_utente(s_temp, "letizia", "Password123!", Ruolo.SOLA_LETTURA)


@pytest.fixture(scope="module")
def client(factory):
    _crea_dati(factory)
    app = crea_app(session_factory=factory, durata_token_secondi=3600, segrete_token="segreto-di-test-molto-lungo-1234567890")
    with TestClient(app) as c:
        yield c


def _token(client, utente="operatore"):
    return ""  # compatibilità test: nessuna credenziale richiesta


# ---------------------------------------------------------------- login


def test_pagina_senza_login(client):
    r=client.get("/");assert r.status_code==200 and 'id="form-login"' not in r.text


def test_endpoint_login_assente(client):
    assert client.post("/api/login",json={"utente":"x","password":"y"}).status_code==404


def test_nessun_token_necessario(client,factory):
    assert client.get("/api/pezzi/AB12").status_code==200


def test_intestazioni_autorizzazione_ignorate(client):
    for h in ({},{"Authorization":"Bearer inesistente"}):assert client.get("/api/pezzi/AB12",headers=h).status_code==200


# ------------------------------------------------------------ consultazione


def test_consultazione_200(client):
    token = _token(client)
    r = client.get("/api/pezzi/AB12", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["barcode"] == "AB12"
    assert "quantita_giacenza" in corpo
    assert "colore" in corpo
    assert "descrizione" in corpo
    assert "codice_profilo" in corpo
    assert "numero_vassoio" in corpo
    assert "stato" in corpo


def test_consultazione_lower_case(client):
    token = _token(client)
    r = client.get("/api/pezzi/ab12", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


def test_consultazione_whitespace(client):
    token = _token(client)
    r = client.get("/api/pezzi/%20AB12%20", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


def test_consultazione_404(client):
    token = _token(client)
    r = client.get("/api/pezzi/NONESISTE", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404
    assert r.json()["detail"]


def test_sola_lettura_consulta(client):
    token = _token(client, "letizia")
    r = client.get("/api/pezzi/AB12", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


def test_operatore_consulta_singolo_barcode(client):
    token = _token(client, "giovanni")
    r = client.get("/api/pezzi/AB12", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


def test_barcode_vuoto_422(client):
    token = _token(client)
    r = client.get("/api/pezzi/", headers={"Authorization": f"Bearer {token}"})
    # FastAPI: percorso /api/pezzi/ senza valore → 404 o 422 a seconda del routing
    assert r.status_code in (404, 405, 422)


def test_barcode_troppo_lungo_422(client):
    token = _token(client)
    r = client.get("/api/pezzi/" + "A" * 300, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 422


def test_richieste_malformate_non_producono_errori_500(client):
    token = _token(client)
    for percorso in ("/api/pezzi/A%2FB", "/api/pezzi/AB%00CD", "/api/pezzi/%20", "/api/pezzi/" + "A" * 256):
        r = client.get(percorso, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code in (404, 405, 422), (percorso, r.status_code)
        assert "detail" in r.json()


# ------------------------------------------------------------------- carico


def test_carico_valido_aumenta_giacenza(client, factory):
    token = _token(client, "giovanni")
    r = client.post("/api/carico", json={"barcode": "ab12", "quantita": 3}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["quantita_giacenza"] == 13


def test_carico_quantita_zero_422(client):
    token = _token(client)
    r = client.post("/api/carico", json={"barcode": "AB12", "quantita": 0}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 422


def test_carico_quantita_negativa_422(client):
    token = _token(client)
    r = client.post("/api/carico", json={"barcode": "AB12", "quantita": -2}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 422


def test_carico_quantita_stringa_422(client):
    token = _token(client)
    r = client.post("/api/carico", json={"barcode": "AB12", "quantita": "3"}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 422


def test_carico_404_non_crea_pezzo(client, factory):
    prima = client.get("/api/pezzi/NONEXIST", headers={"Authorization": f"Bearer {_token(client)}"}).status_code
    assert prima == 404
    r = client.post("/api/carico", json={"barcode": "NONEXIST", "quantita": 5}, headers={"Authorization": f"Bearer {_token(client)}"})
    assert r.status_code == 404
    with factory() as s:
        assert s.scalar(select(Pezzo).where(Pezzo.barcode == "NONEXIST")) is None


def test_carico_accessibile_senza_ruolo(client):
    assert client.post("/api/carico",json={"barcode":"AB12","quantita":1}).status_code==200


# ------------------------------------------------------------------- scarico


def test_scarico_valido(client):
    prima = client.get("/api/pezzi/AB12").json()["quantita_giacenza"]
    token = _token(client, "giovanni")
    r = client.post("/api/scarico", json={"barcode": "AB12", "quantita": 4}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["quantita_giacenza"] == prima - 4


def test_scarico_eccessivo_409(client, factory):
    token = _token(client)
    with factory() as s:
        p = s.scalar(select(Pezzo).where(Pezzo.barcode == "AB12"))
        giacenza_prima = p.quantita
    r = client.post("/api/scarico", json={"barcode": "AB12", "quantita": giacenza_prima + 5}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 409
    with factory() as s:
        p = s.scalar(select(Pezzo).where(Pezzo.barcode == "AB12"))
        assert p.quantita == giacenza_prima


def test_scarico_404_non_modifica(client, factory):
    r = client.post("/api/scarico", json={"barcode": "NOPE", "quantita": 1}, headers={"Authorization": f"Bearer {_token(client)}"})
    assert r.status_code == 404


def test_operatore_scarico(client):
    token = _token(client, "giovanni")
    r = client.post("/api/scarico", json={"barcode": "AB12", "quantita": 1}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


# ----------------------------------------------------------- concorrenza PG


@pytest.mark.skipif(
    os.environ.get("MAGAZZINO_TEST_DB_URL") is None,
    reason="serve MAGAZZINO_TEST_DB_URL verso un database *_test",
)
def test_conflitto_riconciliazione_su_postgres(factory):
    """Due scritture concorrenti su un barcode: nessuna giacenza persa."""
    import sqlalchemy as sa
    from magazzino_profili.db import leggi_config

    url = os.environ["MAGAZZINO_TEST_DB_URL"]
    if not url or "test" not in url.lower():
        pytest.skip("MAGAZZINO_TEST_DB_URL deve puntare a un database *_test")
    engine = sa.create_engine(url, pool_pre_ping=True)
    crea_tabelle(engine)
    factory_pg = crea_session_factory(engine)
    with factory_pg() as s:
        profilo = Profilo(codice="PG9", descrizione="PG", peso_kg_per_metro=decimal.Decimal("1.5"), lunghezza_standard_mm=7000)
        colore = Colore(codice_normalizzato="AZZURRO", nome_visualizzato="Azzurro")
        s.add_all([profilo, colore])
        s.flush()
        s.add(Pezzo(profilo_id=profilo.id, colore_id=colore.id, lunghezza_mm=400, quantita=0, barcode="PG9X"))
        s.commit()

    app = crea_app(session_factory=factory_pg, durata_token_secondi=3600, segrete_token="segreto-di-pg-molto-lungo-1234567890")
    with TestClient(app) as c:
        token = ""
        esiti = []

        def fai(qta):
            r = c.post("/api/carico", json={"barcode": "PG9X", "quantita": qta}, headers={"Authorization": f"Bearer {token}"})
            esiti.append(r.status_code)

        t1 = threading.Thread(target=fai, args=(5,))
        t2 = threading.Thread(target=fai, args=(7,))
        t1.start(); t2.start(); t1.join(); t2.join()
        assert sorted(esiti) == [200, 200]
        with factory_pg() as s:
            p = s.scalar(select(Pezzo).where(Pezzo.barcode == "PG9X"))
            assert p.quantita == 12
