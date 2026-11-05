"""Fase 8 — backup Excel: la colonna ``colore_hex`` è facoltativa in lettura.

- round-trip completo CON ``colore_hex`` (esportazione -> validazione ->
  ripristino su DB vuoto: il valore confermato è conservato);
- file VECCHIO senza la colonna resta valido (``colore_hex`` -> NULL);
- valore non vuoto non conforme a ``#RRGGBB`` -> validazione rifiutata,
  con foglio e riga indicati nel messaggio.
"""

from __future__ import annotations

from decimal import Decimal

from openpyxl import load_workbook
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from magazzino_profili.domain import Base, Colore
from magazzino_profili.reports import backup_excel as be
from magazzino_profili.services import carica
from magazzino_profili.services.anagrafica import crea_profilo


def _eng(percorso):
    e = create_engine(f"sqlite:///{percorso}")
    Base.metadata.create_all(e)
    return e


def _popola(eng):
    with Session(eng, expire_on_commit=False) as s:
        crea_profilo(s, "AB12", "Angolo", Decimal("1.2500"), 6000, "t")
        s.add(Colore(codice_normalizzato="NERO", nome_visualizzato="Nero", colore_hex="#B63A32"))
        s.add(Colore(codice_normalizzato="RAL1013", nome_visualizzato="Bianco perla"))
        s.commit()
        carica(s, "AB12", "NERO", 6000, 1, "t", "init")
        s.commit()


def _esporta(eng, out):
    with Session(eng) as s:
        return be.esporta_backup_logico_excel(s, out)


def test_roundtrip_con_colore_hex(tmp_path):
    src = _eng(tmp_path / "a.db")
    dst = _eng(tmp_path / "b.db")
    _popola(src)
    out = _esporta(src, tmp_path / "b.xlsx")
    bk = be.valida_backup_logico_excel(out)
    assert bk.tabelle["Colori"][0]["colore_hex"] == "#B63A32"
    assert bk.tabelle["Colori"][1]["colore_hex"] is None
    with Session(dst) as s:
        be.ripristina_backup_logico_excel(s, bk, modalita="db_vuoto")
    with Session(dst) as s:
        nero = s.scalars(select(Colore).where(Colore.codice_normalizzato == "NERO")).one()
        assert nero.colore_hex == "#B63A32"
        bianco = s.scalars(select(Colore).where(Colore.codice_normalizzato == "RAL1013")).one()
        assert bianco.colore_hex is None


def test_file_vecchio_senza_colonna_resta_valido(tmp_path):
    src = _eng(tmp_path / "a.db")
    dst = _eng(tmp_path / "b.db")
    _popola(src)
    out = _esporta(src, tmp_path / "b.xlsx")
    # Simulo un file VECCHIO: rimuovo la colonna colore_hex dal foglio Colori.
    wb = load_workbook(out)
    wb["Colori"].delete_cols(4)
    wb.save(out)
    bk = be.valida_backup_logico_excel(out)
    assert bk.tabelle["Colori"][0]["colore_hex"] is None
    with Session(dst) as s:
        be.ripristina_backup_logico_excel(s, bk, modalita="db_vuoto")
    with Session(dst) as s:
        nero = s.scalars(select(Colore).where(Colore.codice_normalizzato == "NERO")).one()
        assert nero.colore_hex is None          # NULL, nessun errore


def test_valore_non_valido_blocca_il_ripristino(tmp_path):
    src = _eng(tmp_path / "a.db")
    _popola(src)
    out = _esporta(src, tmp_path / "b.xlsx")
    wb = load_workbook(out)
    wb["Colori"].cell(row=2, column=4, value="blu scuro")   # riga 2 = NERO
    wb.save(out)
    try:
        be.valida_backup_logico_excel(out)
        raise AssertionError("validazione avrebbe dovuto fallire")
    except be.BackupNonValidoError as e:
        assert "Colori" in str(e)
        assert "colore_hex" in str(e)
        assert "riga 2" in str(e)
    # e nessuna modifica è stata scritta in nessun database
    with Session(src) as s:
        assert len(s.scalars(select(Colore)).all()) == 2
