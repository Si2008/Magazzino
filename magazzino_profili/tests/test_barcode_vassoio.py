"""Fase 7: modifica barcode, numero di vassoio, record eliminati logicamente (SQLite)."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from magazzino_profili.domain import (
    Base, Colore, Movimento, Pezzo, Profilo, Spezzone, TipoMovimento, registra_movimento,
)
from magazzino_profili.services import (
    BarcodeDuplicatoError, PezzoEliminatoError, PezzoNonTrovatoError,
    aggiorna_barcode, carica, imposta_numero_vassoio, registra_spezzone, scarica,
)
from magazzino_profili.services import consultazione as C


@pytest.fixture()
def engine():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(Profilo(codice="AB12", descrizione="Profilo", peso_kg_per_metro=1.0, lunghezza_standard_mm=6000))
        s.add(Profilo(codice="ZZ99", descrizione="Senza pezzi", peso_kg_per_metro=1.0, lunghezza_standard_mm=6000))
        s.add(Colore(codice_normalizzato="NERO", nome_visualizzato="Nero"))
        s.commit()
    return eng


@pytest.fixture()
def sessione(engine):
    with Session(engine, expire_on_commit=False) as s:
        yield s


def _carica(session, lunghezza=6000, quantita=5, **extra):
    return carica(session, "AB12", "NERO", lunghezza, quantita, "t", "prova", **extra)


# ---- aggiorna_barcode -------------------------------------------------------
def test_aggiorna_barcode_conserva_id_movimenti_e_spezzoni(sessione) -> None:
    z = _carica(sessione)
    registra_spezzone(sessione, z.id, 800, 300, "t")  # spezzone collegato al pezzo
    pezzo_id, n_mov = z.id, sessione.scalar(select(func.count(Movimento.id)))
    n_spezzoni = sessione.scalar(select(func.count()).select_from(Spezzone))
    assert n_spezzoni == 1
    sessione.rollback()  # i servizi aprono la propria transazione: nessuna lettura pendente
    aggiornato = aggiorna_barcode(sessione, pezzo_id, "  nuovo-codice-1 ")
    assert (aggiornato.id, aggiornato.barcode) == (pezzo_id, "NUOVO-CODICE-1")
    assert sessione.scalar(select(func.count(Movimento.id))) == n_mov
    assert sessione.scalar(select(func.count()).select_from(Spezzone)) == n_spezzoni
    assert sessione.scalar(select(func.count(Pezzo.id))) == 1  # nessun nuovo record
    assert C.pezzo_per_barcode(sessione, "nuovo-codice-1").id == pezzo_id
    assert C.pezzo_per_barcode(sessione, "AB12-NERO-6000") is None  # vecchio codice non più valido


def test_aggiorna_barcode_stesso_valore_non_fa_nulla(sessione) -> None:
    z = _carica(sessione)
    assert aggiorna_barcode(sessione, z.id, "ab12-nero-6000").barcode == "AB12-NERO-6000"


def test_aggiorna_barcode_duplicato_rifiutato_e_dati_invariati(sessione) -> None:
    a, b = _carica(sessione, 6000), _carica(sessione, 3000)
    with pytest.raises(BarcodeDuplicatoError, match="già assegnato"):
        aggiorna_barcode(sessione, b.id, a.barcode)
    assert sessione.get(Pezzo, b.id).barcode == "AB12-NERO-3000"


@pytest.mark.parametrize("valore", ["", "   ", "AB 12", "AB/12", "ÀB-1", "AB\t1", "A" * 256])
def test_aggiorna_barcode_valori_non_validi(sessione, valore) -> None:
    z = _carica(sessione)
    with pytest.raises(ValueError):
        aggiorna_barcode(sessione, z.id, valore)
    assert sessione.get(Pezzo, z.id).barcode == "AB12-NERO-6000"


def test_aggiorna_barcode_non_testo(sessione) -> None:
    z = _carica(sessione)
    with pytest.raises(ValueError, match="testo"):
        aggiorna_barcode(sessione, z.id, 123)  # type: ignore[arg-type]


def test_aggiorna_barcode_pezzo_assente_o_eliminato(sessione) -> None:
    with pytest.raises(PezzoNonTrovatoError, match="id 999"):
        aggiorna_barcode(sessione, 999, "X-1")
    z = _carica(sessione)
    with sessione.begin():
        sessione.get(Pezzo, z.id).eliminato_il = datetime.now(timezone.utc)
    with pytest.raises(PezzoEliminatoError):
        aggiorna_barcode(sessione, z.id, "X-1")


def test_dopo_la_modifica_il_carico_usa_lo_stesso_record(sessione) -> None:
    z = _carica(sessione)
    aggiorna_barcode(sessione, z.id, "CUSTOM-1")
    z2 = _carica(sessione, quantita=2)  # stessa combinazione: stesso record, nessun duplicato
    assert (z2.id, z2.barcode, z2.quantita) == (z.id, "CUSTOM-1", 7)


def test_barcode_generato_gia_usato_da_altro_pezzo_da_errore_leggibile(sessione) -> None:
    a = _carica(sessione, 6000)
    aggiorna_barcode(sessione, a.id, "AB12-NERO-3000")  # codice che il generatore darebbe a un'altra misura
    with pytest.raises(BarcodeDuplicatoError, match="AB12-NERO-3000"):
        _carica(sessione, 3000)
    assert sessione.scalar(select(func.count(Pezzo.id))) == 1  # nulla creato a metà


# ---- numero di vassoio ------------------------------------------------------
@pytest.mark.parametrize("ingresso, atteso", [(None, None), ("", None), ("   ", None), ("4", "4"),
                                              (" Vassoio 4 ", "Vassoio 4"), ("Corsia B / scaffale 2", "Corsia B / scaffale 2")])
def test_vassoio_normalizzato_e_riletto(engine, sessione, ingresso, atteso) -> None:
    z = _carica(sessione, ubicazione="Scaffale 1")
    imposta_numero_vassoio(sessione, z.id, ingresso)
    with Session(engine) as nuova:  # nuova sessione = riapertura
        riletto = nuova.get(Pezzo, z.id)
        assert riletto.numero_vassoio == atteso
        assert (riletto.ubicazione, riletto.barcode, riletto.quantita, riletto.stato) == ("Scaffale 1", "AB12-NERO-6000", 5, None)


@pytest.mark.parametrize("valore", ["x" * 129, 4, 4.0, ["4"]])
def test_vassoio_non_valido(sessione, valore) -> None:
    z = _carica(sessione)
    with pytest.raises(ValueError):
        imposta_numero_vassoio(sessione, z.id, valore)  # type: ignore[arg-type]
    assert sessione.get(Pezzo, z.id).numero_vassoio is None


def test_vassoio_non_toglie_il_valore_se_la_validazione_fallisce(sessione) -> None:
    z = _carica(sessione)
    imposta_numero_vassoio(sessione, z.id, "7")
    with pytest.raises(ValueError):
        imposta_numero_vassoio(sessione, z.id, "x" * 200)
    assert sessione.get(Pezzo, z.id).numero_vassoio == "7"


# ---- record eliminati: nessun flusso attivo li vede -------------------------
def _elimina(session, pezzo_id) -> None:
    session.rollback()  # chiude la lettura pendente: session.begin() richiede una sessione libera
    with session.begin():
        session.get(Pezzo, pezzo_id).eliminato_il = datetime.now(timezone.utc)


def test_pezzo_eliminato_nascosto_ovunque(sessione) -> None:
    z = _carica(sessione, quantita=1, ubicazione="Vassoio 9")  # 1 < scorta minima 3
    sessione.get(Pezzo, z.id).scorta_minima = 3
    sessione.commit()
    visibili_prima = {
        "lista": len(C.lista_pezzi(sessione)), "cerca": len(C.cerca_pezzi(sessione)),
        "sotto": len(C.pezzi_sotto_scora(sessione)), "riordino": len(C.pezzi_da_riordinare(sessione)),
        "ubic": C.lista_ubicazioni(sessione),
    }
    assert visibili_prima == {"lista": 1, "cerca": 1, "sotto": 1, "riordino": 1, "ubic": ["Vassoio 9"]}
    _elimina(sessione, z.id)
    assert C.lista_pezzi(sessione) == [] and C.cerca_pezzi(sessione) == []
    assert C.pezzi_sotto_scora(sessione) == [] and C.pezzi_da_riordinare(sessione) == []
    assert C.lista_ubicazioni(sessione) == []
    assert C.pezzo_per_barcode(sessione, "AB12-NERO-6000") is None
    assert C.pezzo_per_combinazione(sessione, "AB12", "NERO", 6000) is None
    r = C.riepilogo_inventario(sessione)
    assert (r["referenze"], r["pezzi_totali"], r["da_riordinare"]) == (0, 0, 0)


def test_profili_e_colori_senza_pezzi_attivi_restano_elencati_con_zero(sessione) -> None:
    z = _carica(sessione, quantita=4)
    _elimina(sessione, z.id)
    profili = {p.codice: n for p, n in C.lista_profili_con_giacenza(sessione)}
    assert profili == {"AB12": 0, "ZZ99": 0}  # AB12 non sparisce: la condizione è nel join esterno
    colori = {c.codice_normalizzato: (ref, tot) for c, ref, tot in C.lista_colori_con_conteggio(sessione)}
    assert colori == {"NERO": (0, 0)}


def test_movimenti_storici_restano_leggibili(sessione) -> None:
    z = _carica(sessione)
    _elimina(sessione, z.id)
    assert len(C.ultimi_movimenti(sessione, limite=5)) == 1


def test_filtro_stato_barcode_separato_dallo_stato_scorta(sessione) -> None:
    a, b = _carica(sessione, 6000), _carica(sessione, 3000)
    with sessione.begin():
        sessione.get(Pezzo, a.id).stato = "Caricato"
        sessione.get(Pezzo, b.id).stato = "Scaricato"
    assert [p.id for p in C.cerca_pezzi(sessione, stato_barcode="Caricato")] == [a.id]
    assert [p.id for p in C.cerca_pezzi(sessione, stato_barcode="Scaricato")] == [b.id]
    assert len(C.cerca_pezzi(sessione, stato="ok")) == 2  # il filtro di scorta non è cambiato
    with pytest.raises(ValueError, match="Stato barcode"):
        C.cerca_pezzi(sessione, stato_barcode="ok")


def test_scarico_su_eliminato_come_non_trovato(sessione) -> None:
    z = _carica(sessione)
    _elimina(sessione, z.id)
    with pytest.raises(PezzoNonTrovatoError):
        scarica(sessione, z.barcode, 1, "t", "prova")
    assert sessione.get(Pezzo, z.id).quantita == 5


def test_carico_desktop_riattiva_lo_stesso_record(sessione) -> None:
    z = _carica(sessione)
    imposta_numero_vassoio(sessione, z.id, "4")
    aggiorna_barcode(sessione, z.id, "CUSTOM-1")
    _elimina(sessione, z.id)
    r = _carica(sessione, quantita=2)
    assert (r.id, r.barcode, r.numero_vassoio, r.quantita, r.eliminato_il) == (z.id, "CUSTOM-1", "4", 7, None)
    assert sessione.scalar(select(func.count(Pezzo.id))) == 1  # nessuna seconda combinazione


def test_carico_da_telefono_non_riattiva(sessione) -> None:
    z = _carica(sessione)
    _elimina(sessione, z.id)
    with pytest.raises(PezzoNonTrovatoError):
        carica(sessione, "AB12", "NERO", 6000, 1, "t", "tel", crea_se_mancante=False)
    assert sessione.get(Pezzo, z.id).eliminato_il is not None


# ---- traduzione dell'errore di unicità: solo quello del barcode ------------------
def test_riconosce_solo_il_conflitto_di_barcode(engine) -> None:
    from sqlalchemy import insert
    from sqlalchemy.exc import IntegrityError

    from magazzino_profili.services.pezzi import _e_conflitto_barcode

    base = dict(profilo_id=1, colore_id=1, quantita=1)
    with engine.begin() as cn:
        cn.execute(insert(Pezzo), dict(base, lunghezza_mm=6000, barcode="UNO"))
    with pytest.raises(IntegrityError) as barcode_doppio:
        with engine.begin() as cn:
            cn.execute(insert(Pezzo), dict(base, lunghezza_mm=3000, barcode="UNO"))
    with pytest.raises(IntegrityError) as quantita_negativa:
        with engine.begin() as cn:
            cn.execute(insert(Pezzo), dict(profilo_id=1, colore_id=1, lunghezza_mm=2000, quantita=-1, barcode="DUE"))
    assert _e_conflitto_barcode(barcode_doppio.value) is True
    assert _e_conflitto_barcode(quantita_negativa.value) is False
