"""Test degli endpoint barcode da telefono (login escluso: vedi test_web_auth).

Il database di test è SQLite in memoria condiviso (StaticPool) con
l'app; i dati sono un profilo, un colore e un pezzo con giacenza 5.
"""

import pytest

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.pool import StaticPool

from magazzino_profili.db import crea_session_factory, crea_tabelle
from magazzino_profili.domain import Colore, Movimento, Pezzo, Profilo, TipoMovimento
from magazzino_profili.sicurezza import Ruolo, crea_utente
from magazzino_profili.web.app import crea_app

SEGRET0_TEST = "segreto-di-test-molto-lungo-1234567890"
BARCODE = "AB12-AN007-6000"
GIACENZA_INIZIALE = 5


def _app_con_dati() -> tuple[TestClient, object]:
    """App con un pezzo esistente e due utenti (OPERATORE, SOLA_LETTURA)."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    crea_tabelle(engine)
    factory = crea_session_factory(engine)
    with factory() as session:
        crea_utente(session, "maria", "segreta", Ruolo.OPERATORE)
        crea_utente(session, "osservatore", "segreta", Ruolo.SOLA_LETTURA)
        profilo = Profilo(
            codice="AB12",
            descrizione="Profilo di prova",
            peso_kg_per_metro=Decimal("1.2345"),
            lunghezza_standard_mm=6000,
        )
        colore = Colore(codice_normalizzato="AN007", nome_visualizzato="Antracite")
        session.add_all([profilo, colore])
        session.flush()
        session.add(
            Pezzo(
                profilo_id=profilo.id,
                colore_id=colore.id,
                lunghezza_mm=6000,
                quantita=GIACENZA_INIZIALE,
                barcode=BARCODE,
            )
        )
        # Commit esplicito: senza di esso la chiusura della sessione
        # annullerebbe la transazione e il pezzo non esisterebbe più.
        session.commit()

    app = crea_app(
        session_factory=factory,
        durata_token_secondi=3600,
        segrete_token=SEGRET0_TEST,
    )
    return TestClient(app), factory


def _token(client: TestClient, utente: str = "maria") -> str:
    risposta = client.post(
        "/api/login", json={"utente": utente, "password": "segreta"}
    )
    assert risposta.status_code == 200
    return risposta.json()["token"]


def _intestazioni(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _conteggio(factory, modello) -> int:
    with factory() as session:
        return session.scalar(select(func.count(modello.id)))


def test_carico_senza_token_restituisce_401() -> None:
    client, _ = _app_con_dati()
    risposta = client.post(
        "/api/carico", json={"barcode": BARCODE, "quantita": 1}
    )
    assert risposta.status_code == 401
    assert "detail" in risposta.json()


def test_carico_con_token_e_barcode_esistente_registra_movimento() -> None:
    client, factory = _app_con_dati()
    token = _token(client)

    risposta = client.post(
        "/api/carico",
        json={"barcode": BARCODE, "quantita": 3, "causale": "ordine 42"},
        headers=_intestazioni(token),
    )
    assert risposta.status_code == 200
    corpo = risposta.json()
    assert corpo["barcode"] == BARCODE
    assert corpo["quantita_giacenza"] == GIACENZA_INIZIALE + 3
    assert corpo["codice_profilo"] == "AB12"
    assert corpo["colore"] == "Antracite"

    # Verifica sul database: giacenza aggiornata + movimento contabile.
    with factory() as session:
        pezzo = session.scalar(select(Pezzo).where(Pezzo.barcode == BARCODE))
        assert pezzo.quantita == GIACENZA_INIZIALE + 3
    movimento = None
    with factory() as session:
        movimento = session.scalar(select(Movimento))
    assert movimento is not None
    assert movimento.tipo == TipoMovimento.CARICO
    assert movimento.quantita == 3
    assert movimento.utente == "maria"
    assert movimento.causale == "ordine 42"


def test_carico_con_barcode_inesistente_restituisce_404_e_non_crea_nienta() -> None:
    client, factory = _app_con_dati()
    token = _token(client)

    risposta = client.post(
        "/api/carico",
        json={"barcode": "ZZ99-XX-9999", "quantita": 2},
        headers=_intestazioni(token),
    )
    assert risposta.status_code == 404
    assert "non trovato" in risposta.json()["detail"].lower()

    # Nessun pezzo nuovo, nessun movimento: il telefono non crea pezzi.
    assert _conteggio(factory, Pezzo) == 1
    assert _conteggio(factory, Movimento) == 0
    with factory() as session:
        pezzo = session.scalar(select(Pezzo).where(Pezzo.barcode == BARCODE))
        assert pezzo.quantita == GIACENZA_INIZIALE


def test_scarico_con_quantita_sopra_la_giacenza_restituisce_409() -> None:
    client, factory = _app_con_dati()
    token = _token(client)

    risposta = client.post(
        "/api/scarico",
        json={"barcode": BARCODE, "quantita": GIACENZA_INIZIALE + 10},
        headers=_intestazioni(token),
    )
    assert risposta.status_code == 409
    assert "quantità" in risposta.json()["detail"].lower()

    # Giacenza invariata e nessun movimento registrato.
    with factory() as session:
        pezzo = session.scalar(select(Pezzo).where(Pezzo.barcode == BARCODE))
        assert pezzo.quantita == GIACENZA_INIZIALE
    assert _conteggio(factory, Movimento) == 0


def test_scarico_valido_diminuisce_la_giacenza() -> None:
    client, factory = _app_con_dati()
    token = _token(client)

    risposta = client.post(
        "/api/scarico",
        json={"barcode": BARCODE, "quantita": 2, "causale": "montaggio 7"},
        headers=_intestazioni(token),
    )
    assert risposta.status_code == 200
    assert risposta.json()["quantita_giacenza"] == GIACENZA_INIZIALE - 2

    with factory() as session:
        pezzo = session.scalar(select(Pezzo).where(Pezzo.barcode == BARCODE))
        assert pezzo.quantita == GIACENZA_INIZIALE - 2
    with factory() as session:
        movimento = session.scalar(select(Movimento))
    assert movimento is not None
    assert movimento.tipo == TipoMovimento.SCARICO
    assert movimento.quantita == 2
    assert movimento.causale == "montaggio 7"


def test_carico_con_quantita_non_valida_restituisce_422() -> None:
    client, factory = _app_con_dati()
    token = _token(client)

    for quantita_non_valida in (0, "abc"):
        risposta = client.post(
            "/api/carico",
            json={"barcode": BARCODE, "quantita": quantita_non_valida},
            headers=_intestazioni(token),
        )
        assert risposta.status_code == 422
        assert "quantità" in risposta.json()["detail"].lower()

    assert _conteggio(factory, Movimento) == 0


def test_utente_sola_lettura_riceve_403_sul_carico() -> None:
    client, _ = _app_con_dati()
    token = _token(client, utente="osservatore")
    risposta = client.post(
        "/api/carico", json={"barcode": BARCODE, "quantita": 1},
        headers=_intestazioni(token),
    )
    assert risposta.status_code == 403
    assert "autorizzato" in risposta.json()["detail"].lower()


# ----------------------------------------------------------------------
# Fase 7B: modalita "Lettore" - /api/scansione e /api/telefono/ping
# ----------------------------------------------------------------------
def test_scansione_con_token_operatore_accoda_e_non_tocca_la_giacenza() -> None:
    from magazzino_profili.domain import Pezzo, ScansioneTelefono
    from magazzino_profili.services import telefono

    client, factory = _app_con_dati()
    token = _token(client)
    risposta = client.post(
        "/api/scansione", json={"barcode": "ab12-an007-6000"}, headers=_intestazioni(token)
    )
    assert risposta.status_code == 200
    corpo = risposta.json()
    assert corpo["barcode"] == "AB12-AN007-6000"

    with factory() as session:
        righe = session.scalars(select(ScansioneTelefono)).all()
        assert len(righe) == 1
        assert righe[0].barcode == "AB12-AN007-6000"
        assert righe[0].letta is False
        assert session.get(Pezzo, 1).quantita == GIACENZA_INIZIALE  # giacenza invariata


def test_scansione_sicurezza_401_403_422() -> None:
    client, _ = _app_con_dati()
    # Senza token: 401.
    assert client.post("/api/scansione", json={"barcode": BARCODE}).status_code == 401
    # SOLA_LETTURA: 403.
    token = _token(client, utente="osservatore")
    assert client.post(
        "/api/scansione", json={"barcode": BARCODE}, headers=_intestazioni(token)
    ).status_code == 403
    # Barcode vuoto: 422 con messaggio in italiano.
    token = _token(client)
    risposta = client.post("/api/scansione", json={"barcode": ""}, headers=_intestazioni(token))
    assert risposta.status_code == 422
    assert "barcode" in risposta.json()["detail"].lower()


def test_ping_segna_il_telefono_collegato() -> None:
    from magazzino_profili.services import telefono

    client, factory = _app_con_dati()
    # Senza token: 401.
    assert client.post("/api/telefono/ping").status_code == 401
    token = _token(client)
    assert client.post("/api/telefono/ping", headers=_intestazioni(token)).status_code == 200
    with factory() as session:
        assert telefono.telefono_collegato(session) is True


@pytest.mark.parametrize("quantita", [True, 1.0, "3", 0, -1])
@pytest.mark.parametrize("percorso", ["/api/carico", "/api/scarico"])
def test_quantita_non_intera_positiva_rifiutata_dal_telefono(percorso, quantita) -> None:
    client, factory = _app_con_dati()
    token = _token(client)
    risposta = client.post(
        percorso, json={"barcode": BARCODE, "quantita": quantita},
        headers=_intestazioni(token),
    )
    assert risposta.status_code == 422
    assert _conteggio(factory, Movimento) == 0
    with factory() as session:
        pezzo = session.scalar(select(Pezzo).where(Pezzo.barcode == BARCODE))
        assert pezzo.quantita == GIACENZA_INIZIALE


# ----------------------------------------------------------------------
# Fase 7: barcode modificato, vassoio/stato nella risposta, eliminati
# ----------------------------------------------------------------------
def test_telefono_trova_il_nuovo_barcode_con_vassoio_e_stato() -> None:
    from magazzino_profili.services import aggiorna_barcode, imposta_numero_vassoio

    client, factory = _app_con_dati()
    token = _token(client)
    with factory() as session:
        pezzo_id = session.scalar(select(Pezzo.id).where(Pezzo.barcode == BARCODE))
    with factory() as session:
        aggiorna_barcode(session, pezzo_id, "nuovo-1")
    with factory() as session:
        imposta_numero_vassoio(session, pezzo_id, "Vassoio 4")

    ok = client.post("/api/carico", json={"barcode": "nuovo-1", "quantita": 1}, headers=_intestazioni(token))
    assert ok.status_code == 200
    corpo = ok.json()
    assert (corpo["barcode"], corpo["numero_vassoio"], corpo["stato"]) == ("NUOVO-1", "Vassoio 4", None)
    vecchio = client.post("/api/carico", json={"barcode": BARCODE, "quantita": 1}, headers=_intestazioni(token))
    assert vecchio.status_code == 404


@pytest.mark.parametrize("percorso", ["/api/carico", "/api/scarico"])
def test_telefono_pezzo_eliminato_non_disponibile_e_non_riattivato(percorso) -> None:
    from datetime import datetime, timezone

    client, factory = _app_con_dati()
    token = _token(client)
    with factory() as session, session.begin():
        session.scalar(select(Pezzo).where(Pezzo.barcode == BARCODE)).eliminato_il = datetime.now(timezone.utc)
    risposta = client.post(percorso, json={"barcode": BARCODE, "quantita": 1}, headers=_intestazioni(token))
    assert risposta.status_code == 404
    assert _conteggio(factory, Movimento) == 0
    with factory() as session:
        pezzo = session.scalar(select(Pezzo).where(Pezzo.barcode == BARCODE))
        assert pezzo.eliminato_il is not None and pezzo.quantita == GIACENZA_INIZIALE
