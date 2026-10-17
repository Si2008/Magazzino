"""Test delle consultazioni inventario.

Regressione: la UI accede a ``pezzo.profilo``/``pezzo.colore`` DOPO
aver chiuso la sessione; le query devono caricare le relazioni
eagermente (selectinload) o SQLAlchemy solleva
``DetachedInstanceError`` (bug emerso con DB popolato).
"""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from magazzino_profili.db import crea_session_factory
from magazzino_profili.domain import Base, Colore, Movimento, Pezzo, Profilo
from magazzino_profili.services.consultazione import (
    cerca_pezzi,
    lista_colori_con_conteggio,
    lista_pezzi,
    lista_profili_con_giacenza,
    lista_ubicazioni,
    livello_scorta,
    pezzo_per_barcode,
    pezzo_per_combinazione,
    pezzi_avvisi,
    pezzi_da_riordinare,
    pezzi_sotto_scora,
    peso_totale_kg,
    peso_unitario_kg,
    riepilogo_inventario,
    stato_scorta,
    ultimi_movimenti,
)


@pytest.fixture()
def factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return crea_session_factory(engine)


@pytest.fixture()
def con_dati(factory):
    """Un profilo, un colore e un pezzo in giacenza."""
    sessione: Session = factory()
    profilo = Profilo(
        codice="AB12",
        descrizione="Profilo di prova",
        peso_kg_per_metro=Decimal("1.0"),
        lunghezza_standard_mm=6000,
    )
    sessione.add(profilo)
    colore = Colore(codice_normalizzato="ROSSO", nome_visualizzato="Rosso")
    sessione.add(colore)
    sessione.flush()
    pezzo = Pezzo(
        profilo=profilo,
        colore=colore,
        lunghezza_mm=6000,
        quantita=5,
        barcode="AB12-ROSSO-6000",
    )
    sessione.add(pezzo)
    sessione.commit()
    sessione.close()


def test_lista_pezzi_relazioni_a_sessione_chiusa(factory, con_dati):
    """Accesso a profilo/colore DOPO la chiusura della sessione."""
    sessione = factory()
    pezzi = lista_pezzi(sessione)
    sessione.close()  # <-- qui scattava DetachedInstanceError
    assert len(pezzi) == 1
    assert pezzi[0].profilo.codice == "AB12"
    assert pezzi[0].colore.nome_visualizzato == "Rosso"
    assert pezzi[0].scorta_minima is None


def test_cerca_pezzi_testo_a_sessione_chiusa(factory, con_dati):
    sessione = factory()
    trovati = cerca_pezzi(sessione, testo="ab12", colore_id=None, stato=None)
    sessione.close()
    assert len(trovati) == 1
    assert trovati[0].profilo.descrizione == "Profilo di prova"


def test_cerca_pezzi_stati_scorta_a_sessione_chiusa(factory, con_dati):
    """I filtri sotto/ok scorta usano scorta_minima (non scora_minima)."""
    sessione = factory()
    ok = cerca_pezzi(sessione, testo="", colore_id=None, stato="ok")
    assert len(ok) == 1
    sotto = cerca_pezzi(sessione, testo="", colore_id=None, stato="sotto")
    assert sotto == []
    assert ok[0].colore.codice_normalizzato == "ROSSO"
    sessione.close()


def test_pezzi_sotto_scora_a_sessione_chiusa(factory, con_dati):
    sessione = factory()
    sotto = pezzi_sotto_scora(sessione)
    sessione.close()
    assert sotto == []  # scorta minima non definita -> nessun avviso


# ----------------------------------------------------------------------
# stato_scorta / peso
# ----------------------------------------------------------------------
def test_stato_scorta_esaurito(factory, con_dati):
    sessione = factory()
    pezzo = sessione.get(Pezzo, 1)
    pezzo.quantita = 0
    sessione.close()
    assert stato_scorta(pezzo) == "esaurito"


def test_stato_scorta_sotto(factory, con_dati):
    sessione = factory()
    pezzo = sessione.get(Pezzo, 1)
    pezzo.scorta_minima = 10  # giacenza 5 < 10
    sessione.close()
    assert stato_scorta(pezzo) == "sotto"


def test_stato_scorta_ok_e_senza_scora(factory, con_dati):
    sessione = factory()
    pezzo = sessione.get(Pezzo, 1)
    assert stato_scorta(pezzo) == "ok"  # scorta_minima None
    pezzo.scorta_minima = 5  # giacenza 5 >= 5
    assert stato_scorta(pezzo) == "ok"
    sessione.close()


def test_stato_scorta_quantita_nulla(factory):
    sessione = factory()
    assert stato_scorta(Pezzo(quantita=None)) == "esaurito"
    sessione.close()


def test_peso_unitario_e_totale(factory, con_dati):
    """Profilo 1,0 kg/m, pezzo 6000 mm x 5 pz: 6 kg e 30 kg."""
    sessione = factory()
    # lista_pezzi carica i profili eager: accessibili anche a sessione chiusa.
    pezzo = lista_pezzi(sessione)[0]
    assert peso_unitario_kg(pezzo) == 6.0
    assert peso_totale_kg(pezzo) == 30.0
    sessione.close()
    assert peso_unitario_kg(pezzo) == 6.0  # anche dopo la chiusura


def test_peso_con_profilo_senza_peso(factory, con_dati):
    """Profilo senza peso lineare: peso unitario e totale zero."""
    sessione = factory()
    pezzo = sessione.get(Pezzo, 1)
    assert pezzo.profilo.peso_kg_per_metro is not None
    assert peso_unitario_kg(pezzo) == 6.0
    pezzo.profilo.peso_kg_per_metro = None
    assert peso_unitario_kg(pezzo) == 0.0
    assert peso_totale_kg(pezzo) == 0.0
    sessione.close()


# ----------------------------------------------------------------------
# riepilogo_inventario: le quattro chiavi delle card KPI
# ----------------------------------------------------------------------
def test_riepilogo_inventario_quattro_chiavi(factory, con_dati):
    """Con_dati: 1 riga, 5 pezzi, profilo 1,0 kg/m x 6 m -> 30 kg, ok scorta."""
    sessione = factory()
    riepilogo = riepilogo_inventario(sessione)
    assert riepilogo["pezzi_totali"] == 5
    assert riepilogo["pezzi"] == 5  # alias
    assert riepilogo["referenze"] == 1
    assert riepilogo["peso_kg"] == 30.0
    assert riepilogo["da_riordinare"] == 0
    assert riepilogo["profili"] == 1
    assert riepilogo["colori"] == 1
    assert riepilogo["barcodes_unici"] == 1
    sessione.close()


def test_riepilogo_da_riordinare_coerente_stato_scorta(factory, con_dati):
    sessione = factory()
    pezzo = sessione.get(Pezzo, 1)
    pezzo.scorta_minima = 10  # sotto scorta (giacenza 5)
    riepilogo = riepilogo_inventario(sessione)
    assert riepilogo["da_riordinare"] == 1
    assert [p.id for p in pezzi_da_riordinare(sessione)] == [pezzo.id]
    sessione.close()


def test_riepilogo_peso_somma_pezzo(factory):
    """Due pezzi con pesi diversi: peso_kg è la somma dei pesi totali."""
    sessione = factory()
    p1 = Profilo(codice="PA", descrizione="A", peso_kg_per_metro=Decimal("2.0"), lunghezza_standard_mm=6000)
    p2 = Profilo(codice="PB", descrizione="B", peso_kg_per_metro=Decimal("1.0"), lunghezza_standard_mm=6000)
    c = Colore(codice_normalizzato="X1", nome_visualizzato="X1")
    sessione.add_all([p1, p2, c])
    sessione.flush()
    z1 = Pezzo(profilo=p1, colore=c, lunghezza_mm=5000, quantita=2, barcode="PA-X1-5000")
    z2 = Pezzo(profilo=p2, colore=c, lunghezza_mm=4000, quantita=3, barcode="PB-X1-4000")
    sessione.add_all([z1, z2])
    sessione.commit()
    riepilogo = riepilogo_inventario(sessione)
    # 2,0*5*2 = 20 kg + 1,0*4*3 = 12 kg
    assert riepilogo["peso_kg"] == 32.0
    assert riepilogo["pezzi_totali"] == 5
    assert riepilogo["referenze"] == 2
    sessione.close()


# ----------------------------------------------------------------------
# cerca_pezzi: filtri e firma retrocompatibile
# ----------------------------------------------------------------------
def test_cerca_pezzi_multi_testo_and(factory, con_dati):
    """Ogni parola deve comparire in almeno un campo (AND tra le parole)."""
    sessione = factory()
    assert len(cerca_pezzi(sessione, testo="ab12 rosso")) == 1
    assert cerca_pezzi(sessione, testo="ab12 blu") == []
    assert len(cerca_pezzi(sessione, testo="  ")) == 1  # solo spazi = nessun filtro
    sessione.close()


def test_cerca_pezzi_filtro_profilo_id(factory, con_dati):
    sessione = factory()
    assert len(cerca_pezzi(sessione, profilo_id=1)) == 1
    assert cerca_pezzi(sessione, profilo_id=999) == []
    sessione.close()


def test_cerca_pezzi_ubicazione_esatta(factory):
    """'Vassoio 1' non deve trovare 'Vassoio 10' (uguaglianza, non sottostringa)."""
    sessione = factory()
    profilo = Profilo(codice="AB12", descrizione="X", peso_kg_per_metro=Decimal("1.0"), lunghezza_standard_mm=6000)
    colore = Colore(codice_normalizzato="ROSSO", nome_visualizzato="Rosso")
    sessione.add_all([profilo, colore])
    sessione.flush()
    sessione.add_all([
        Pezzo(profilo=profilo, colore=colore, lunghezza_mm=6000, quantita=1, barcode="AB12-ROSSO-6000", ubicazione="Vassoio 1"),
        Pezzo(profilo=profilo, colore=colore, lunghezza_mm=5000, quantita=1, barcode="AB12-ROSSO-5000", ubicazione="Vassoio 10"),
    ])
    sessione.commit()
    trovat1 = cerca_pezzi(sessione, ubicazione="Vassoio 1")
    assert [p.barcode for p in trovat1] == ["AB12-ROSSO-6000"]
    trovat10 = cerca_pezzi(sessione, ubicazione="Vassoio 10")
    assert [p.barcode for p in trovat10] == ["AB12-ROSSO-5000"]
    # case-insensitive e spazi ai bordi
    assert len(cerca_pezzi(sessione, ubicazione="  vassoio 1 ")) == 1
    sessione.close()


def test_cerca_pezzi_stati_esaurito_e_riordino(factory, con_dati):
    sessione = factory()
    pezzo = sessione.get(Pezzo, 1)
    # 1) tutto ok
    assert [p.id for p in cerca_pezzi(sessione, stato="esaurito")] == []
    assert [p.id for p in cerca_pezzi(sessione, stato="riordino")] == []
    # 2) sotto scorta ma non esaurito
    pezzo.scorta_minima = 10
    assert [p.id for p in cerca_pezzi(sessione, stato="esaurito")] == []
    assert [p.id for p in cerca_pezzi(sessione, stato="sotto")] == [pezzo.id]
    assert [p.id for p in cerca_pezzi(sessione, stato="riordino")] == [pezzo.id]
    # 3) esaurito: entra in 'esaurito' e 'riordino'; con scorta definita
    #    resta anche in 'sotto' (0 < scorta), esce da 'ok'
    pezzo.quantita = 0
    assert [p.id for p in cerca_pezzi(sessione, stato="esaurito")] == [pezzo.id]
    assert [p.id for p in cerca_pezzi(sessione, stato="riordino")] == [pezzo.id]
    assert [p.id for p in cerca_pezzi(sessione, stato="sotto")] == [pezzo.id]
    assert [p.id for p in cerca_pezzi(sessione, stato="ok")] == []
    sessione.close()


def test_cerca_pezzi_firma_vecchia_invariata(factory, con_dati):
    """La chiamata storica a parole chiave continua a funzionare."""
    sessione = factory()
    trovati = cerca_pezzi(sessione, testo="ab12", colore_id=1, stato=None)
    assert len(trovati) == 1
    assert trovati[0].profilo.codice == "AB12"
    assert trovati[0].colore.id == 1
    sessione.close()


# ----------------------------------------------------------------------
# pezzo_per_barcode
# ----------------------------------------------------------------------
def test_pezzo_per_barcode_case_e_spazi(factory, con_dati):
    sessione = factory()
    assert sessione.get(Pezzo, 1).id == 1
    assert pezzo_per_barcode(sessione, "ab12-rosso-6000").id == 1  # minuscole
    assert pezzo_per_barcode(sessione, "  ab12-rosso-6000  ").id == 1  # spazi
    assert pezzo_per_barcode(sessione, "AB12-ROSSO-6000").id == 1
    sessione.close()


def test_pezzo_per_barcode_inesistente_e_vuoto(factory, con_dati):
    sessione = factory()
    assert pezzo_per_barcode(sessione, "NON-ESISTE") is None
    assert pezzo_per_barcode(sessione, "") is None
    assert pezzo_per_barcode(sessione, "   ") is None
    assert pezzo_per_barcode(sessione, None) is None
    sessione.close()


# ----------------------------------------------------------------------
# pezzo_per_combinazione
# ----------------------------------------------------------------------
def test_pezzo_per_combinazione(factory, con_dati):
    sessione = factory()
    trovo = pezzo_per_combinazione(sessione, "AB12", "ROSSO", 6000)
    assert trovo is not None and trovo.id == 1
    assert trovo.profilo.codice == "AB12"  # relazioni eager
    assert pezzo_per_combinazione(sessione, "AB12", "ROSSO", 5000) is None
    assert pezzo_per_combinazione(sessione, "AB12", "ROSSO", 0) is None
    assert pezzo_per_combinazione(sessione, "", "ROSSO", 6000) is None
    sessione.close()


# ----------------------------------------------------------------------
# lista_ubicazioni
# ----------------------------------------------------------------------
def test_lista_ubicazioni_ordine_naturale_e_distinte(factory):
    sessione = factory()
    profilo = Profilo(codice="AB12", descrizione="X", peso_kg_per_metro=Decimal("1.0"), lunghezza_standard_mm=6000)
    colore = Colore(codice_normalizzato="ROSSO", nome_visualizzato="Rosso")
    sessione.add_all([profilo, colore])
    sessione.flush()
    sessione.add_all([
        Pezzo(profilo=profilo, colore=colore, lunghezza_mm=6000, quantita=1, barcode="A-1", ubicazione="Vassoio 10"),
        Pezzo(profilo=profilo, colore=colore, lunghezza_mm=5000, quantita=1, barcode="A-2", ubicazione="Vassoio 2"),
        Pezzo(profilo=profilo, colore=colore, lunghezza_mm=4000, quantita=1, barcode="A-3", ubicazione="Vassoio 1"),
        Pezzo(profilo=profilo, colore=colore, lunghezza_mm=3000, quantita=1, barcode="A-4", ubicazione="Vassoio 1"),  # duplicata
        Pezzo(profilo=profilo, colore=colore, lunghezza_mm=2000, quantita=1, barcode="A-5", ubicazione=""),  # vuota
        Pezzo(profilo=profilo, colore=colore, lunghezza_mm=1000, quantita=1, barcode="A-6"),  # None
    ])
    sessione.commit()
    assert lista_ubicazioni(sessione) == ["Vassoio 1", "Vassoio 2", "Vassoio 10"]
    sessione.close()


# ----------------------------------------------------------------------
# ultimi_movimenti
# ----------------------------------------------------------------------
def test_ultimi_movimenti_ordine_limite_e_filtri(factory, con_dati):
    sessione = factory()
    from datetime import datetime, timezone, timedelta
    pezzo = sessione.get(Pezzo, 1)
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    m1 = Movimento(pezzo_id=pezzo.id, tipo="CARICO", quantita=1, data_ora=base, causale="c1", utente="u")
    m2 = Movimento(pezzo_id=pezzo.id, tipo="SCARICO", quantita=1, data_ora=base + timedelta(hours=1), causale="c2", utente="u")
    m3 = Movimento(pezzo_id=pezzo.id, tipo="CARICO", quantita=1, data_ora=base + timedelta(hours=2), causale="c3", utente="u")
    altro = Movimento(pezzo_id=999, tipo="CARICO", quantita=1, data_ora=base + timedelta(hours=3), causale="x", utente="u")
    sessione.add_all([m1, m2, m3, altro])
    sessione.commit()

    tutti = ultimi_movimenti(sessione)  # FK a 999: SQLite non la valida
    assert [m.causale for m in tutti] == ["x", "c3", "c2", "c1"]  # data_ora decrescente
    assert [m.causale for m in ultimi_movimenti(sessione, limite=2)] == ["x", "c3"]
    solo = ultimi_movimenti(sessione, limite=10, pezzo_id=pezzo.id)
    assert [m.causale for m in solo] == ["c3", "c2", "c1"]
    sessione.close()
    # Accesso a movimento.pezzo.profilo DOPO la chiusura (eager).
    assert solo[0].pezzo.profilo.codice == "AB12"


# ----------------------------------------------------------------------
# lista_profili_con_giacenza
# ----------------------------------------------------------------------
def test_lista_profili_con_giacenza_senza_pezzi(factory, con_dati):
    sessione = factory()
    vuoto = Profilo(codice="ZZ99", descrizione="Senza pezzi", peso_kg_per_metro=Decimal("1.0"), lunghezza_standard_mm=6000)
    sessione.add(vuoto)
    sessione.commit()
    righe = {p.codice: n for p, n in lista_profili_con_giacenza(sessione)}
    assert righe == {"AB12": 5, "ZZ99": 0}  # profilo senza pezzi = 0
    assert [p.codice for p, _ in lista_profili_con_giacenza(sessione)] == ["AB12", "ZZ99"]
    sessione.close()


# ----------------------------------------------------------------------
# pezzi_da_riordinare
# ----------------------------------------------------------------------
def test_pezzi_da_riordinare_ordine(factory, con_dati):
    sessione = factory()
    p = sessione.get(Pezzo, 1)
    colore = p.colore
    profilo = p.profilo
    sotto = Pezzo(profilo=profilo, colore=colore, lunghezza_mm=5000, quantita=3, barcode="AB12-ROSSO-5000", scorta_minima=5)
    esaurito = Pezzo(profilo=profilo, colore=colore, lunghezza_mm=4000, quantita=0, barcode="AB12-ROSSO-4000")
    ok = Pezzo(profilo=profilo, colore=colore, lunghezza_mm=3000, quantita=50, barcode="AB12-ROSSO-3000")
    sessione.add_all([sotto, esaurito, ok])
    sessione.commit()
    lista = pezzi_da_riordinare(sessione)
    assert [z.barcode for z in lista] == ["AB12-ROSSO-4000", "AB12-ROSSO-5000"]  # giacenza crescente
    assert all(z.id != ok.id for z in lista)
    sessione.close()


# ----------------------------------------------------------------------
# Fase 7A: soglia globale, livello "esaurimento" e pezzi_avvisi
# ----------------------------------------------------------------------
def _pezzo(factory, barcode, quantita, scorta_minima=None) -> Pezzo:
    """Crea un pezzo (profilo + colore + giacenza) e restituisce l'istanza."""
    sessione = factory()
    from sqlalchemy import select
    profilo = sessione.scalars(select(Profilo).limit(1)).first()
    colore = sessione.scalars(select(Colore).limit(1)).first()
    if profilo is None:
        profilo = Profilo(
            codice="AB12", descrizione="Profilo di prova",
            peso_kg_per_metro=Decimal("1.0"), lunghezza_standard_mm=6000,
        )
        sessione.add(profilo)
    if colore is None:
        colore = Colore(codice_normalizzato="ROSSO", nome_visualizzato="Rosso")
        sessione.add(colore)
    sessione.flush()
    lunghezza = int(barcode.rsplit('-', 1)[1])  # il barcode termina con la lunghezza
    z = Pezzo(
        profilo=profilo, colore=colore, lunghezza_mm=lunghezza,
        quantita=quantita, scorta_minima=scorta_minima, barcode=barcode,
    )
    sessione.add(z)
    sessione.commit()
    sessione.close()
    return z


def test_stato_scorta_soglia_globale_pezzo_senza_scora(factory):
    """Pezzo senza scorta_minima: 'fino a N pezzi' con la soglia globale."""
    z = _pezzo(factory, "AB12-ROSSO-6000", 5)
    assert stato_scorta(z, 5) == "sotto"  # 5 <= 5
    assert stato_scorta(z, 4) == "ok"  # 5 > 4
    assert stato_scorta(z, 6) == "sotto"  # 5 <= 6
    z6 = _pezzo(factory, "AB12-ROSSO-6006", 6)
    assert stato_scorta(z6, 5) == "ok"  # 6 > 5


def test_stato_scorta_senza_soglia_comportamento_storico(factory):
    """Senza soglia globale il pezzo senza scorta_minima resta 'ok' (come prima)."""
    z = _pezzo(factory, "AB12-ROSSO-5000", 3)
    assert stato_scorta(z) == "ok"


def test_stato_scorta_scora_minima_ha_priorita(factory):
    """scorta_minima presente: '<' resta stretto, la soglia globale non conta."""
    z = _pezzo(factory, "AB12-ROSSO-4000", 10, scorta_minima=10)
    assert stato_scorta(z, 5) == "ok"  # 10 < 10 falso, la soglia 5 non vale
    z2 = _pezzo(factory, "AB12-ROSSO-3000", 9, scorta_minima=10)
    assert stato_scorta(z2, 5) == "sotto"  # 9 < 10


def test_livello_scorta_esaurimento(factory):
    """Soglia 5: giacenza 6..15 = 'esaurimento', da 16 = 'ok'."""
    z = _pezzo(factory, "AB12-ROSSO-6001", 15)
    assert livello_scorta(z, 5) == "esaurimento"  # 15 <= 15
    z2 = _pezzo(factory, "AB12-ROSSO-6002", 16)
    assert livello_scorta(z2, 5) == "ok"  # 16 > 15
    z3 = _pezzo(factory, "AB12-ROSSO-6003", 6)
    assert livello_scorta(z3, 5) == "esaurimento"  # 6 <= 15
    # senza soglia globale: niente livello esaurimento
    assert livello_scorta(z2) == "ok"
    # 'sotto' e 'esaurito' non vengono mai riscritti in 'esaurimento'
    z4 = _pezzo(factory, "AB12-ROSSO-6004", 3)
    assert livello_scorta(z4, 5) == "sotto"
    z5 = _pezzo(factory, "AB12-ROSSO-6005", 0)
    assert livello_scorta(z5, 5) == "esaurito"


def test_pezzi_da_riordinare_esclude_esaurimento(factory):
    """Con soglia 5: da_riordinare = esauriti + sotto (non 'in esaurimento')."""
    sotto = _pezzo(factory, "AB12-ROSSO-7001", 3)  # sotto (3 <= 5)
    esaurito = _pezzo(factory, "AB12-ROSSO-7002", 0)  # esaurito
    esaurimento = _pezzo(factory, "AB12-ROSSO-7003", 12)  # solo 'in esaurimento'
    ok = _pezzo(factory, "AB12-ROSSO-7004", 40)
    sessione = factory()
    riordino = pezzi_da_riordinare(sessione, 5)
    assert {z.id for z in riordino} == {sotto.id, esaurito.id}
    avvisi = pezzi_avvisi(sessione, 5)
    assert {z.id for z in avvisi} == {sotto.id, esaurito.id, esaurimento.id}
    assert all(z.id != ok.id for z in avvisi)
    sessione.close()


def test_cerca_pezzi_sotto_ok_complementari_con_soglia(factory):
    """Con soglia 5, sotto/ok sono complementari sui pezzi con quantita > 0."""
    _pezzo(factory, "AB12-ROSSO-8001", 3)   # sotto
    _pezzo(factory, "AB12-ROSSO-8002", 12)  # in esaurimento -> ok per l'inventario
    _pezzo(factory, "AB12-ROSSO-8003", 40)  # ok
    sessione = factory()
    sotto = {z.id for z in cerca_pezzi(sessione, stato="sotto", soglia_globale=5)}
    ok = {z.id for z in cerca_pezzi(sessione, stato="ok", soglia_globale=5)}
    vivi = {z.id for z in cerca_pezzi(sessione, soglia_globale=5) if z.quantita and z.quantita > 0}
    assert sotto | ok == vivi
    assert sotto & ok == set()
    assert len(sotto) == 1
    sessione.close()


# ----------------------------------------------------------------------
# lista_colori_con_conteggio
# ----------------------------------------------------------------------
def test_lista_colori_con_conteggio(factory):
    """Colore senza pezzi incluso con 0; ordinamento; somme corrette."""
    sessione = factory()
    profilo = Profilo(codice="AB12", descrizione="X", peso_kg_per_metro=Decimal("1.0"), lunghezza_standard_mm=6000)
    c_a = Colore(codice_normalizzato="AN007", nome_visualizzato="Antracite")
    c_b = Colore(codice_normalizzato="RAL9010", nome_visualizzato="Bianco")
    c_z = Colore(codice_normalizzato="ZZZ", nome_visualizzato="Vuoto")  # senza pezzi
    sessione.add_all([profilo, c_a, c_b, c_z])
    sessione.flush()
    sessione.add_all([
        Pezzo(profilo=profilo, colore=c_a, lunghezza_mm=6000, quantita=4, barcode="AB12-AN007-6000"),
        Pezzo(profilo=profilo, colore=c_a, lunghezza_mm=5000, quantita=2, barcode="AB12-AN007-5000"),
        Pezzo(profilo=profilo, colore=c_b, lunghezza_mm=6000, quantita=7, barcode="AB12-RAL9010-6000"),
    ])
    sessione.commit()
    righe = lista_colori_con_conteggio(sessione)
    assert [(c.codice_normalizzato, ref, pz) for c, ref, pz in righe] == [
        ("AN007", 2, 6),
        ("RAL9010", 1, 7),
        ("ZZZ", 0, 0),  # colore senza pezzi: referenze e pezzi = 0
    ]
    # Accessibili a sessione chiusa (istanze già caricate).
    sessione.close()
    assert righe[0][0].nome_visualizzato == "Antracite"
