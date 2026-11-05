"""Test dell'esportazione Excel: one row per piece, with the barcode.

Usano un database SQLite in memoria: the export is independent from the
dialect.
"""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from openpyxl import load_workbook

from magazzino_profili.db import crea_session_factory
from magazzino_profili.domain import Base, Pezzo, Profilo
from magazzino_profili.reports import esporta_inventario_excel
from magazzino_profili.reports.export_excel import INTESTAZIONI
from magazzino_profili.services import carica


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = crea_session_factory(engine)
    s = factory()
    try:
        yield s
    finally:
        s.rollback()
        s.close()



def _fields(cls: type) -> list[str]:
    # Names of the declared columns (without the autoincrement id).
    return [c.key for c in cls.__dict__.values() if hasattr(c, "key") and c.key != "id"]


def _add_pozione(session: Session) -> Pezzo:
    # Insert a Profilo and return the piece created by carica.
    prof = Profilo()
    for nome, value in zip(_fields(Profilo), ("AB12", "Profilo test", None, Decimal("1.2500"), 6000)):
        setattr(prof, nome, value)
    session.add(prof)
    session.commit()
    return carica(session, "ab 12", "an 007", 6000, 5, "operator", "Arrival")


def test_export_contains_a_row_per_piece(session, tmp_path):
    """The Excel must have one row per piece, with all the columns."""
    piece_1 = _add_pozione(session)
    piece_2 = carica(session, "AB12", "an 007", 3000, 1, "operator", "Arrival")

    out = esporta_inventario_excel(session, tmp_path / "inventory.xlsx")
    assert out.exists()

    wb = load_workbook(out)
    assert wb.sheetnames == ["AN007"]
    ws = wb["AN007"]

    headers = tuple(cell.value for cell in ws[1])
    assert headers == tuple(INTESTAZIONI)
    assert headers[-1] == "Barcode"

    righe = [[cell.value for cell in row] for row in ws.iter_rows(min_row=2)]
    assert len(righe) == 2
    assert {row[INTESTAZIONI.index("Lunghezza (mm)")] for row in righe} == {6000, 3000}
    assert {row[-1] for row in righe} == {piece_1.barcode, piece_2.barcode}
    assert sum(row[INTESTAZIONI.index("Quantità")] for row in righe) == piece_1.quantita + piece_2.quantita
