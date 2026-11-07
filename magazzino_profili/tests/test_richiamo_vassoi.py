"""Verifiche del richiamo simulato, senza hardware o rete."""

import json
import socket
import subprocess
from unittest.mock import Mock

import pytest

from magazzino_profili.services.richiamo_vassoi import EsitoRichiamo, simula_richiamo


@pytest.fixture
def registro(tmp_path, monkeypatch):
    from magazzino_profili.services import richiamo_vassoi

    monkeypatch.setattr(richiamo_vassoi, "dati_runtime", lambda: tmp_path)
    return tmp_path / "log" / "richiami-vassoi.jsonl"


def test_simulazione_non_comunica_con_icon(registro, monkeypatch):
    rete = Mock(side_effect=AssertionError("Accesso alla rete"))
    processo = Mock(side_effect=AssertionError("Avvio di processo"))
    monkeypatch.setattr(socket, "socket", rete)
    monkeypatch.setattr(subprocess, "Popen", processo)

    risultato = simula_richiamo("Vassoio 004", "scarico")

    assert risultato.esito is EsitoRichiamo.SIMULATO
    assert risultato.durata_secondi >= 0
    rete.assert_not_called()
    processo.assert_not_called()
    voce = json.loads(registro.read_text(encoding="utf-8"))
    assert voce["vassoio"] == "004"
    assert voce["origine"] == "scarico"
    assert voce["modalita"] == "simulazione"
    assert voce["esito"] == "simulato"
    assert voce["data_ora"]


@pytest.mark.parametrize("vassoio", [None, "", "0", "-2", "Corsia B / scaffale 2", "4\n5"])
def test_vassoio_invalido_non_arriva_al_simulatore(vassoio, registro):
    simulatore = Mock()
    risultato = simula_richiamo(vassoio, "scarico", simulatore=simulatore)
    assert risultato.esito is EsitoRichiamo.VASSOIO_NON_VALIDO
    simulatore.assert_not_called()
    assert json.loads(registro.read_text(encoding="utf-8"))["esito"] == "vassoio_non_valido"


@pytest.mark.parametrize(("risposta", "errore", "esito"), [
    (False, None, EsitoRichiamo.RIFIUTATO),
    (None, FileNotFoundError(), EsitoRichiamo.NON_DISPONIBILE),
    (None, ConnectionRefusedError(), EsitoRichiamo.NON_DISPONIBILE),
    (None, TimeoutError(), EsitoRichiamo.SCONOSCIUTO),
    (None, ConnectionResetError(), EsitoRichiamo.SCONOSCIUTO),
    (None, ValueError(), EsitoRichiamo.SCONOSCIUTO),
    ({"esito": "ok"}, None, EsitoRichiamo.SCONOSCIUTO),
])
def test_errori_registrati_senza_retry(risposta, errore, esito, registro):
    simulatore = Mock(return_value=risposta, side_effect=errore)
    risultato = simula_richiamo("7", "commessa", simulatore=simulatore)
    assert risultato.esito is esito
    simulatore.assert_called_once_with("7")
    assert json.loads(registro.read_text(encoding="utf-8"))["esito"] == esito.value
    if esito is EsitoRichiamo.SCONOSCIUTO:
        assert "esito sconosciuto" in risultato.messaggio


def test_registro_non_scrivibile(registro):
    registro.parent.write_text("ostacolo", encoding="utf-8")
    risultato = simula_richiamo("7", "commessa")
    assert risultato.esito is EsitoRichiamo.SIMULATO
    assert "registro dei richiami non è scrivibile" in risultato.messaggio
