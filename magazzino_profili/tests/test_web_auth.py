"""Accesso libero: nessuna tabella utenti necessaria per usare le API."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from magazzino_profili.domain import Base
from magazzino_profili.db import crea_session_factory
from magazzino_profili.web.app import crea_app

@pytest.fixture
def client():
    e=create_engine("sqlite://",poolclass=StaticPool,connect_args={"check_same_thread":False})
    Base.metadata.create_all(e)
    with TestClient(crea_app(session_factory=crea_session_factory(e))) as c:yield c
    e.dispose()

def test_pagina_diretta_senza_credenziali(client):
    r=client.get("/")
    assert r.status_code==200 and 'id="form-login"' not in r.text and 'type="password"' not in r.text

def test_login_non_esposto(client):
    assert client.post("/api/login",json={}).status_code==404

def test_api_senza_token_o_utenti(client):
    assert client.get("/api/salute").status_code==200
    assert client.post("/api/scansione",json={"barcode":"TEST-1"}).status_code==200
    assert client.post("/api/telefono/ping",json={}).status_code==200

def test_dati_invalidi_rifiutati_anche_senza_login(client):
    assert client.post("/api/scansione",json={"barcode":""}).status_code==422
    assert client.post("/api/scarico",json={"barcode":"TEST-1","quantita":0}).status_code==422
