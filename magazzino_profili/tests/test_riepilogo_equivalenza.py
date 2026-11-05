import random
from decimal import Decimal
import pytest
from sqlalchemy import create_engine, insert
from sqlalchemy.orm import Session
from magazzino_profili.domain import Base, Colore, Pezzo, Profilo
from magazzino_profili.services import consultazione as C

def _riferimento(session) -> dict:
    pezzi = list(session.query(Pezzo).all())
    return {
        "pezzi_totali": sum(p.quantita for p in pezzi), "referenze": len(pezzi),
        "peso_kg": sum(C.peso_totale_kg(p) for p in pezzi),
        "da_riordinare": sum(1 for p in pezzi if C.stato_scorta(p) != "ok"),
        "profili": len({p.profilo_id for p in pezzi}), "colori": len({p.colore_id for p in pezzi}),
        "barcodes_unici": len({p.barcode for p in pezzi}),
    }

@pytest.mark.parametrize("seme", [1, 2, 3])
def test_riepilogo_sql_uguale_al_calcolo_in_python(seme) -> None:
    rnd = random.Random(seme)
    eng = create_engine("sqlite://"); Base.metadata.create_all(eng)
    with eng.begin() as c:
        c.execute(insert(Profilo), [dict(codice=f"P{i}", descrizione="d",
                  peso_kg_per_metro=Decimal(rnd.choice(["0", "1.2345", "2.5", "0.8"])),
                  lunghezza_standard_mm=6000) for i in range(30)])
        c.execute(insert(Colore), [dict(codice_normalizzato=f"C{i}", nome_visualizzato="c") for i in range(8)])
        righe, visti = [], set()
        while len(righe) < 400:
            p, col, lung = rnd.randint(1, 30), rnd.randint(1, 8), rnd.choice([6000, 3000, 0, 1500])
            if (p, col, lung) in visti: continue
            visti.add((p, col, lung))
            righe.append(dict(profilo_id=p, colore_id=col, lunghezza_mm=lung, quantita=rnd.randint(0, 20),
                              scorta_minima=rnd.choice([None, None, 0, 5, 10]), barcode=f"P{p}-C{col}-{lung}"))
        c.execute(insert(Pezzo), righe)
    with Session(eng) as s:
        atteso, ottenuto = _riferimento(s), C.riepilogo_inventario(s)
    for chiave, valore in atteso.items():
        assert ottenuto[chiave] == pytest.approx(valore, rel=1e-9), chiave

def test_riepilogo_database_vuoto() -> None:
    eng = create_engine("sqlite://"); Base.metadata.create_all(eng)
    with Session(eng) as s:
        r = C.riepilogo_inventario(s)
    assert (r["pezzi_totali"], r["referenze"], r["peso_kg"], r["da_riordinare"]) == (0, 0, 0.0, 0)
