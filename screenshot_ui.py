"""Genera screenshot offscreen della nuova UI (Inventario e Carico).

Uso:  .venv/Scripts/python screenshot_ui.py
Salva: screenshot_inventario.png, screenshot_carico.png
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from decimal import Decimal

from PySide6.QtWidgets import QApplication
from sqlalchemy import create_engine, select

from magazzino_profili.db import crea_session_factory
from magazzino_profili.domain import Base, Colore, Pezzo
from magazzino_profili.sicurezza import Ruolo
from magazzino_profili.services import anagrafica
from magazzino_profili.services import carica, imposta_scorta_minima
from magazzino_profili.ui import FinestraPrincipale
from magazzino_profili.ui import tema


def _chiuso(factory, fn) -> None:
    """Esegue ``fn(sessione)`` su una sessione dedicata (come la UI)."""
    sessione = factory()
    try:
        fn(sessione)
    finally:
        sessione.close()


def _semi(factory) -> None:
    """Popola il DB di prova con dati realistici (una sessione per operazione)."""
    _chiuso(factory, lambda s: anagrafica.crea_profilo(
        s, codice="AB12", descrizione="Angolo 120 mm",
        peso_kg_per_metro=Decimal("1.2500"), lunghezza_standard_mm=6000,
    ))
    _chiuso(factory, lambda s: anagrafica.crea_profilo(
        s, codice="C50", descrizione="Cornice 50 mm",
        peso_kg_per_metro=Decimal("0.8000"), lunghezza_standard_mm=3000,
    ))
    for args in (
        ("AB12", "AN007", 6000, 12, "Carico iniziale", "Vassoio 1"),
        ("AB12", "AN007", 6000, 3, "Carico parziale", "Vassoio 1"),
        ("AB12", "RAL9010", 6000, 8, "Carico iniziale", "Vassoio 2"),
        ("AB12", "BIANCO", 4000, 5, "Carico iniziale", "Vassoio 2"),
        ("C50", "AN007", 3000, 4, "Carico iniziale", "Scaffale A"),
        ("C50", "ROSSO", 3000, 2, "Carico iniziale", "Scaffale A"),
    ):
        cod, col, lung, qty, causale, ubic = args
        _chiuso(factory, lambda s, c=cod, co=col, l=lung, q=qty, ca=causale, u=ubic:
            carica(s, c, co, l, q, "demo", ca, u))
    # un colore senza pezzi: la tab deve comparire comunque (sbiadita)
    def _aggiungi_nero(s):
        if not s.scalar(select(Colore).where(Colore.codice_normalizzato == "NERO")):
            s.add(Colore(codice_normalizzato="NERO", nome_visualizzato="Nero"))
            s.commit()

    _chiuso(factory, _aggiungi_nero)
    # una scorta minima alta per generare un avviso (due sessioni distinte)
    s1 = factory()
    pezzo = s1.scalar(select(Pezzo).where(Pezzo.barcode.like("AB12-RAL%")))
    s1.close()
    if pezzo is not None:
        _chiuso(factory, lambda s: imposta_scorta_minima(s, pezzo.id, 20))


def main() -> None:
    app = QApplication([])
    app.setStyleSheet(tema.qss_globale(tema.tema_attivo()))

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = crea_session_factory(engine)
    _semi(factory)

    finestra = FinestraPrincipale(factory, Ruolo.AMMINISTRATORE, "demo")
    finestra.resize(1320, 840)
    finestra.show()
    app.processEvents()

    finestra._tab.setCurrentWidget(finestra.scheda_inventario)
    app.processEvents()
    finestra.grab().save("screenshot_inventario.png")

    finestra._tab.setCurrentWidget(finestra.scheda_carico)
    app.processEvents()
    finestra.grab().save("screenshot_carico.png")

    print("OK: screenshot_inventario.png, screenshot_carico.png")


if __name__ == "__main__":
    main()
