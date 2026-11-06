"""Ricerca locale alle operazioni: pagine limitate, selezione esplicita del pezzo."""
from dataclasses import dataclass

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QLabel, QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView, QSizePolicy)
from sqlalchemy import select, or_, func

from ..domain import Profilo, Pezzo, Colore
from .componenti import bottone
from .tema import M, rem


@dataclass(frozen=True)
class SceltaProfilo:
    profilo_id: int
    codice: str
    descrizione: str
    lunghezza_mm: int
    barcode: str = ""
    colore: str = ""
    vassoio: str = ""
    ubicazione: str = ""

    @property
    def chiave(self):
        return self.barcode or self.profilo_id


class RicercaProfili(QWidget):
    selezionato = Signal(object)
    LIMITE = 50

    def __init__(self, factory, *, scarico=False, parent=None):
        super().__init__(parent)
        self._factory, self._scarico = factory, scarico
        self._pagina, self._scelta = 0, None
        self._righe = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(M.TOOLBAR_GAP)
        self.cerca = QLineEdit(self)
        self.cerca.setPlaceholderText("Cerca profilo per codice o nome…")
        self.cerca.setAccessibleName("Ricerca profili nello scarico" if scarico else "Ricerca profili nel carico")
        self.cerca.setClearButtonEnabled(True)
        layout.addWidget(self.cerca)
        self.tabella = QTableWidget(0, 4 if scarico else 2, self)
        self.tabella.setHorizontalHeaderLabels(
            ["Profilo", "Misura", "Colore", "Vassoio"] if scarico else ["Profilo", "Nome"])
        self.tabella.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabella.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabella.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabella.verticalHeader().hide()
        self.tabella.verticalHeader().setDefaultSectionSize(M.RIGA_PROFILI)
        self.tabella.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.tabella.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tabella.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tabella.setMinimumHeight(rem(8))
        self.tabella.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.tabella.itemSelectionChanged.connect(self._seleziona)
        # Dopo un salvataggio il form è vuoto, ma la riga può essere ancora
        # selezionata: anche un nuovo clic sulla stessa riga deve ricompilarlo.
        self.tabella.cellClicked.connect(lambda _r, _c: self._seleziona())
        layout.addWidget(self.tabella, 1)
        self.esito = QLabel(self)
        self.esito.setObjectName("Dim")
        self.esito.setWordWrap(True)
        layout.addWidget(self.esito)
        pagina = QHBoxLayout()
        self.precedente = bottone("Precedenti", dim="sm", parent=self)
        self.successiva = bottone("Altri risultati", dim="sm", parent=self)
        self.precedente.clicked.connect(lambda: self._cambia_pagina(-1))
        self.successiva.clicked.connect(lambda: self._cambia_pagina(1))
        pagina.addWidget(self.precedente)
        pagina.addWidget(self.successiva)
        layout.addLayout(pagina)
        self._ritardo = QTimer(self)
        self._ritardo.setSingleShot(True)
        self._ritardo.setInterval(180)
        self._ritardo.timeout.connect(self._filtra)
        self.cerca.textChanged.connect(lambda: self._ritardo.start())
        self.aggiorna()

    def _filtra(self):
        self._pagina = 0
        self.aggiorna()

    def _cambia_pagina(self, delta):
        self._pagina = max(0, self._pagina + delta)
        self.aggiorna()

    def aggiorna(self):
        from sqlalchemy.exc import SQLAlchemyError
        try:
            self._carica()
        except SQLAlchemyError:
            import logging
            logging.getLogger(__name__).exception("Ricerca profili non disponibile")
            self._righe = []
            self._scelta = None
            self.tabella.blockSignals(True)
            self.tabella.setRowCount(0)
            self.tabella.blockSignals(False)
            self.precedente.setEnabled(False)
            self.successiva.setEnabled(False)
            self.esito.setText("Database non disponibile. Riprova la ricerca.")
            self.selezionato.emit(None)

    def _carica(self):
        testo = self.cerca.text().strip().lower()
        with self._factory() as sessione:
            if self._scarico:
                query = (select(Profilo, Pezzo, Colore).join(Pezzo, Pezzo.profilo_id == Profilo.id)
                    .join(Colore, Colore.id == Pezzo.colore_id)
                    .where(Pezzo.eliminato_il.is_(None), Pezzo.quantita > 0,
                           or_(Pezzo.stato.is_(None), Pezzo.stato == "Caricato")))
            else:
                query = select(Profilo)
            if testo:
                query = query.where(or_(
                    func.lower(Profilo.codice).contains(testo, autoescape=True),
                    func.lower(Profilo.descrizione).contains(testo, autoescape=True)))
            query = query.order_by(Profilo.codice, Pezzo.id) if self._scarico else query.order_by(Profilo.codice)
            records = sessione.execute(query.offset(self._pagina * self.LIMITE).limit(self.LIMITE + 1)).all()
            altre = len(records) > self.LIMITE
            righe = []
            for record in records[:self.LIMITE]:
                p = record[0]
                if self._scarico:
                    z, c = record[1:]
                    righe.append(SceltaProfilo(p.id, p.codice, p.descrizione, z.lunghezza_mm,
                        z.barcode, c.codice_normalizzato, z.numero_vassoio or "", z.ubicazione or ""))
                else:
                    righe.append(SceltaProfilo(p.id, p.codice, p.descrizione, p.lunghezza_standard_mm))
        scelta = self._scelta
        self._righe = righe
        self.tabella.blockSignals(True)
        self.tabella.setRowCount(0)
        selezione = None
        for n, r in enumerate(righe):
            self.tabella.insertRow(n)
            valori = (r.codice, f"{r.lunghezza_mm} mm", r.colore, r.vassoio or "Non assegnato") if self._scarico else (r.codice, r.descrizione)
            for c, valore in enumerate(valori):
                item = QTableWidgetItem(valore)
                item.setToolTip(f"{r.codice} · {r.descrizione}" + (f"\nBarcode: {r.barcode}" if r.barcode else ""))
                self.tabella.setItem(n, c, item)
            if scelta is not None and scelta.chiave == r.chiave:
                selezione = n
        if selezione is not None:
            self.tabella.selectRow(selezione)
        self.tabella.blockSignals(False)
        if scelta is not None and selezione is None:
            self._scelta = None
            self.selezionato.emit(None)
        self.precedente.setEnabled(self._pagina > 0)
        self.successiva.setEnabled(altre)
        self.esito.setText("Nessun risultato. Modifica la ricerca." if not righe else
            f"{len(righe)} risultati · Pagina {self._pagina + 1}. Clicca " + ("il pezzo da scaricare." if self._scarico else "il profilo da caricare."))

    def _seleziona(self):
        righe = self.tabella.selectionModel().selectedRows()
        self._scelta = self._righe[righe[0].row()] if righe else None
        self.selezionato.emit(self._scelta)
