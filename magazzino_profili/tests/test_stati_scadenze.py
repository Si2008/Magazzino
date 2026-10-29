"""Fase 8: stati del barcode, scadenza a 48 ore, eliminazione automatica e manuale (SQLite)."""
import logging
import threading
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from magazzino_profili.domain import Base, Colore, Movimento, Pezzo, Profilo
from magazzino_profili.services import (
    PezzoEliminatoError, PezzoNonTrovatoError, carica, elimina_manualmente, elimina_scaduti,
    elimina_scaduto, imposta_stato, lista_scaduti_per_eliminazione, scarica,
)
from magazzino_profili.services import stati as modulo_stati
from magazzino_profili.services.controllo_scadenze import ControlloScadenze

T0 = datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc)


class Orologio:
    """Clock simulato: l'orologio reale del computer non viene mai toccato."""

    def __init__(self, inizio: datetime = T0) -> None:
        self.t, self.chiamate = inizio, 0

    def __call__(self) -> datetime:
        self.chiamate += 1
        return self.t

    def a(self, istante: datetime) -> "Orologio":
        self.t = istante
        return self


def _in(*, ore=0, minuti=0, secondi=0, micro=0) -> datetime:
    return T0 + timedelta(hours=ore, minutes=minuti, seconds=secondi, microseconds=micro)


def _utc(valore):
    """SQLite restituisce datetime senza fuso (sono UTC, come scritti dal servizio)."""
    if valore is not None and valore.tzinfo is None:
        return valore.replace(tzinfo=timezone.utc)
    return valore


@pytest.fixture()
def engine(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(Profilo(codice="AB12", descrizione="d", peso_kg_per_metro=1.0, lunghezza_standard_mm=6000))
        s.add(Colore(codice_normalizzato="NERO", nome_visualizzato="Nero"))
        s.commit()
    yield eng
    eng.dispose()


def esegui(engine, funzione, *args, **kw):
    """Una sessione nuova per ogni chiamata: i servizi aprono la propria transazione."""
    with Session(engine, expire_on_commit=False) as s:
        return funzione(s, *args, **kw)


def nuovo(engine, lunghezza=6000, quantita=5) -> int:
    return esegui(engine, carica, "AB12", "NERO", lunghezza, quantita, "t", "prova").id


def leggi(engine, pezzo_id):
    with Session(engine) as s:
        p = s.get(Pezzo, pezzo_id)
        return p.stato, _utc(p.data_ultimo_cambio_stato), _utc(p.eliminato_il)


def scaduti(engine, istante) -> list[int]:
    return esegui(engine, lista_scaduti_per_eliminazione, now=Orologio(istante))


# ---- stati e timestamp ------------------------------------------------------
def test_imposta_stato_aggiorna_stato_e_timestamp_in_utc(engine) -> None:
    pid = nuovo(engine)
    assert leggi(engine, pid) == (None, None, None)  # record senza stato: nessun valore inventato
    fuso = timezone(timedelta(hours=2))
    esegui(engine, imposta_stato, pid, "Scaricato", now=Orologio(T0.astimezone(fuso)))
    assert leggi(engine, pid) == ("Scaricato", T0, None)


def test_stesso_stato_non_tocca_il_timestamp_e_non_chiama_il_clock(engine) -> None:
    pid = nuovo(engine)
    esegui(engine, imposta_stato, pid, "Scaricato", now=Orologio(T0))
    orologio = Orologio(_in(ore=30))
    esegui(engine, imposta_stato, pid, "Scaricato", now=orologio)
    assert orologio.chiamate == 0
    assert leggi(engine, pid)[1] == T0  # la scadenza non si rinnova ripetendo lo stato


@pytest.mark.parametrize("valore", [None, "", "scaricato", "Rotto", 5, ["Caricato"]])
def test_stato_non_valido(engine, valore) -> None:
    pid = nuovo(engine)
    with pytest.raises(ValueError, match="Stato non valido"):
        esegui(engine, imposta_stato, pid, valore, now=Orologio())
    assert leggi(engine, pid) == (None, None, None)


def test_clock_senza_timezone_rifiutato_senza_modifiche(engine) -> None:
    pid = nuovo(engine)
    with pytest.raises(ValueError, match="timezone"):
        esegui(engine, imposta_stato, pid, "Scaricato", now=lambda: datetime(2026, 10, 14, 12, 0))
    assert leggi(engine, pid) == (None, None, None)


def test_imposta_stato_pezzo_assente_o_eliminato(engine) -> None:
    with pytest.raises(PezzoNonTrovatoError):
        esegui(engine, imposta_stato, 999, "Caricato", now=Orologio())
    pid = nuovo(engine)
    esegui(engine, elimina_manualmente, pid, True, now=Orologio())
    with pytest.raises(PezzoEliminatoError):
        esegui(engine, imposta_stato, pid, "Caricato", now=Orologio())


def test_carico_e_scarico_non_cambiano_lo_stato(engine) -> None:
    pid = nuovo(engine)
    esegui(engine, imposta_stato, pid, "Scaricato", now=Orologio(T0))
    carica_ = esegui(engine, carica, "AB12", "NERO", 6000, 2, "t", "prova")
    esegui(engine, scarica, carica_.barcode, 1, "t", "prova")
    assert leggi(engine, pid) == ("Scaricato", T0, None)  # quantità e stato sono eventi distinti


# ---- regola delle 48 ore ----------------------------------------------------
@pytest.mark.parametrize("istante, atteso", [
    (_in(ore=47, minuti=59, secondi=59, micro=999999), False),  # un microsecondo prima
    (_in(ore=48), True),                                         # scadenza esatta: consentita
    (_in(ore=48, micro=1), True),
    (_in(ore=500), True),
    (_in(ore=0), False),
])
def test_scaduto_solo_da_48_ore_in_poi(engine, istante, atteso) -> None:
    pid = nuovo(engine)
    esegui(engine, imposta_stato, pid, "Scaricato", now=Orologio(T0))
    assert (pid in scaduti(engine, istante)) is atteso
    assert esegui(engine, elimina_scaduto, pid, now=Orologio(istante)) is atteso
    assert (leggi(engine, pid)[2] is not None) is atteso
    if atteso:
        assert leggi(engine, pid)[2] == istante


def test_caricato_non_scade_mai(engine) -> None:
    pid = nuovo(engine)
    esegui(engine, imposta_stato, pid, "Caricato", now=Orologio(T0))
    assert scaduti(engine, _in(ore=24 * 400)) == []
    assert esegui(engine, elimina_scaduto, pid, now=Orologio(_in(ore=24 * 400))) is False
    assert leggi(engine, pid)[2] is None


def test_stato_senza_timestamp_non_scade(engine) -> None:
    pid = nuovo(engine)
    with Session(engine) as s, s.begin():  # dato "storico" incoerente: Scaricato senza orario
        s.get(Pezzo, pid).stato = "Scaricato"
    assert scaduti(engine, _in(ore=9999)) == []
    assert esegui(engine, elimina_scaduto, pid, now=Orologio(_in(ore=9999))) is False


def test_ritorno_a_caricato_annulla_la_scadenza(engine) -> None:
    pid = nuovo(engine)
    esegui(engine, imposta_stato, pid, "Scaricato", now=Orologio(T0))
    esegui(engine, imposta_stato, pid, "Caricato", now=Orologio(_in(ore=47)))
    assert esegui(engine, elimina_scaduto, pid, now=Orologio(_in(ore=49))) is False
    assert elimina_scaduti(lambda: Session(engine), now=Orologio(_in(ore=200))) == 0
    assert leggi(engine, pid)[2] is None


def test_nuovo_passaggio_a_scaricato_ricalcola_la_scadenza(engine) -> None:
    pid = nuovo(engine)
    esegui(engine, imposta_stato, pid, "Scaricato", now=Orologio(T0))
    esegui(engine, imposta_stato, pid, "Caricato", now=Orologio(_in(ore=10)))
    esegui(engine, imposta_stato, pid, "Scaricato", now=Orologio(_in(ore=20)))
    assert scaduti(engine, _in(ore=48, secondi=1)) == []  # la vecchia scadenza è ignorata
    assert scaduti(engine, _in(ore=67, minuti=59)) == []
    assert scaduti(engine, _in(ore=68)) == [pid]           # 20 h + 48 h


def test_riavvio_la_scadenza_e_ricostruita_dai_dati_persistenti(engine, tmp_path) -> None:
    pid = nuovo(engine)
    esegui(engine, imposta_stato, pid, "Scaricato", now=Orologio(T0))
    engine.dispose()  # "il programma si chiude"
    riavviato = create_engine(f"sqlite:///{tmp_path / 'test.db'}")  # "il programma riparte"
    try:
        assert esegui(riavviato, lista_scaduti_per_eliminazione, now=Orologio(_in(ore=47))) == []
        assert elimina_scaduti(lambda: Session(riavviato), now=Orologio(_in(ore=48))) == 1
    finally:
        riavviato.dispose()


# ---- eliminazione automatica: integrità --------------------------------------
def test_eliminazione_automatica_e_solo_logica(engine) -> None:
    pid = nuovo(engine)
    esegui(engine, imposta_stato, pid, "Scaricato", now=Orologio(T0))
    n_mov = esegui(engine, lambda s: s.scalar(select(func.count(Movimento.id))))
    assert esegui(engine, elimina_scaduto, pid, now=Orologio(_in(ore=48))) is True
    assert esegui(engine, elimina_scaduto, pid, now=Orologio(_in(ore=60))) is False  # già eliminato
    assert esegui(engine, elimina_scaduto, 999, now=Orologio(_in(ore=60))) is False  # inesistente
    assert esegui(engine, lambda s: s.scalar(select(func.count(Pezzo.id)))) == 1     # riga ancora presente
    assert esegui(engine, lambda s: s.scalar(select(func.count(Movimento.id)))) == n_mov
    assert leggi(engine, pid)[2] == _in(ore=48)


def test_elimina_scaduti_conta_e_non_si_ferma_su_un_errore(engine, monkeypatch, caplog) -> None:
    ids = [nuovo(engine, lung) for lung in (6000, 3000, 2500, 1500)]
    for pid in ids[:3]:
        esegui(engine, imposta_stato, pid, "Scaricato", now=Orologio(T0))
    esegui(engine, imposta_stato, ids[3], "Scaricato", now=Orologio(_in(ore=40)))  # non ancora scaduto
    originale = modulo_stati.elimina_scaduto

    def a_volte_in_errore(session, pezzo_id, **kw):
        if pezzo_id == ids[1]:
            raise OperationalError("UPDATE", {}, Exception("connessione persa"))
        return originale(session, pezzo_id, **kw)

    monkeypatch.setattr(modulo_stati, "elimina_scaduto", a_volte_in_errore)
    with caplog.at_level(logging.ERROR):
        assert elimina_scaduti(lambda: Session(engine), now=Orologio(_in(ore=49))) == 2
    assert [leggi(engine, i)[2] is not None for i in ids] == [True, False, True, False]
    assert any("connessione persa" in r.exc_text for r in caplog.records if r.exc_text)  # traceback conservato


@pytest.mark.parametrize("operazione", ["imposta_stato", "elimina_scaduto", "elimina_manualmente"])
def test_errore_del_database_non_corrompe_i_dati(engine, operazione) -> None:
    pid = nuovo(engine)
    esegui(engine, imposta_stato, pid, "Scaricato", now=Orologio(T0))
    prima = leggi(engine, pid)

    def guasto(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("UPDATE PEZZI"):
            raise OperationalError(statement, parameters, Exception("disco pieno"))

    event.listen(engine, "before_cursor_execute", guasto)
    try:
        with pytest.raises(OperationalError):
            if operazione == "imposta_stato":
                esegui(engine, imposta_stato, pid, "Caricato", now=Orologio(_in(ore=1)))
            elif operazione == "elimina_scaduto":
                esegui(engine, elimina_scaduto, pid, now=Orologio(_in(ore=50)))
            else:
                esegui(engine, elimina_manualmente, pid, True, now=Orologio(_in(ore=50)))
    finally:
        event.remove(engine, "before_cursor_execute", guasto)
    assert leggi(engine, pid) == prima
    assert esegui(engine, elimina_scaduto, pid, now=Orologio(_in(ore=50))) is True  # il database è ancora utilizzabile


# ---- eliminazione manuale -----------------------------------------------------
@pytest.mark.parametrize("stato", ["Scaricato", "Caricato", None])
def test_eliminazione_manuale_di_qualsiasi_stato_senza_limite_di_tempo(engine, stato) -> None:
    pid = nuovo(engine)
    if stato:
        esegui(engine, imposta_stato, pid, stato, now=Orologio(T0))
    adesso = _in(minuti=1)  # nessuna attesa di 48 ore
    pezzo = esegui(engine, elimina_manualmente, pid, True, now=Orologio(adesso))
    assert pezzo.eliminato_il == adesso
    assert leggi(engine, pid)[2] == adesso


@pytest.mark.parametrize("conferma", [False, None, 1, "si"])
def test_eliminazione_manuale_non_confermata_non_fa_nulla(engine, conferma) -> None:
    pid = nuovo(engine)
    orologio = Orologio()
    with pytest.raises(ValueError, match="non confermata"):
        esegui(engine, elimina_manualmente, pid, conferma, now=orologio)
    assert orologio.chiamate == 0 and leggi(engine, pid)[2] is None


def test_eliminazione_manuale_doppia_o_su_assente(engine) -> None:
    pid = nuovo(engine)
    esegui(engine, elimina_manualmente, pid, True, now=Orologio())
    with pytest.raises(PezzoEliminatoError):
        esegui(engine, elimina_manualmente, pid, True, now=Orologio())
    with pytest.raises(PezzoNonTrovatoError):
        esegui(engine, elimina_manualmente, 999, True, now=Orologio())


# ---- carico dopo l'eliminazione automatica -------------------------------------
def test_carico_su_barcode_eliminato_da_scaricato_non_viene_rieliminato(engine) -> None:
    pid = nuovo(engine)
    esegui(engine, imposta_stato, pid, "Scaricato", now=Orologio(T0))
    assert elimina_scaduti(lambda: Session(engine), now=Orologio(_in(ore=48))) == 1
    r = esegui(engine, carica, "AB12", "NERO", 6000, 3, "t", "prova", now=Orologio(_in(ore=49)))
    assert (r.id, r.eliminato_il, r.stato, _utc(r.data_ultimo_cambio_stato)) == (pid, None, "Caricato", _in(ore=49))
    assert elimina_scaduti(lambda: Session(engine), now=Orologio(_in(ore=500))) == 0  # senza la correzione: 1
    assert leggi(engine, pid)[2] is None


# ---- servizio in background -------------------------------------------------------
def test_controllo_esegui_ora_notifica_il_numero_di_eliminati(engine) -> None:
    pid = nuovo(engine)
    esegui(engine, imposta_stato, pid, "Scaricato", now=Orologio(T0))
    notifiche: list[int] = []
    controllo = ControlloScadenze(lambda: Session(engine), now=Orologio(_in(ore=48)), su_eliminati=notifiche.append)
    assert controllo.esegui_ora() == 1 and notifiche == [1]
    assert controllo.esegui_ora() == 0 and notifiche == [1]  # niente da fare: nessuna notifica


def test_controllo_sopravvive_a_errori_del_database_e_del_callback(engine, caplog) -> None:
    pid = nuovo(engine)
    esegui(engine, imposta_stato, pid, "Scaricato", now=Orologio(T0))
    chiamate = {"n": 0}

    def factory():
        chiamate["n"] += 1
        if chiamate["n"] == 1:
            raise OperationalError("SELECT", {}, Exception("database non raggiungibile"))
        return Session(engine)

    def callback_rotto(_n):
        raise RuntimeError("UI chiusa")

    controllo = ControlloScadenze(factory, now=Orologio(_in(ore=48)), su_eliminati=callback_rotto)
    with caplog.at_level(logging.ERROR):
        assert controllo.esegui_ora() == 0  # errore registrato, nessuna eccezione verso l'esterno
        assert controllo.esegui_ora() == 1  # il giro successivo funziona anche se il callback fallisce
    assert "Controllo scadenze non riuscito" in caplog.text and "Notifica" in caplog.text


def test_controllo_parte_subito_in_un_thread_e_si_ferma(engine) -> None:
    pid = nuovo(engine)
    esegui(engine, imposta_stato, pid, "Scaricato", now=Orologio(T0))
    fatto = threading.Event()
    controllo = ControlloScadenze(
        lambda: Session(engine), intervallo_secondi=3600, now=Orologio(_in(ore=48)),
        su_eliminati=lambda n: fatto.set(),
    )
    controllo.avvia()
    assert fatto.wait(5), "il primo controllo deve partire all'avvio, senza attendere l'intervallo"
    controllo.ferma(timeout=5)
    assert not any(t.name == "controllo-scadenze" and t.is_alive() for t in threading.enumerate())
    assert leggi(engine, pid)[2] is not None
