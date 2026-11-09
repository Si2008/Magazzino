"""Scheda Avvisi: pezzi esauriti o sotto scorta minima.

- "Dettagli" emette :attr:`vai_a_colore` con l'id del colore del pezzo:
  la finestra principale passa alla scheda Inventario e seleziona la
  scheda colore corrispondente (azzera ricerca e combo).
- "Carica" emette :attr:`vai_a_scheda` con ``("Carico", barcode)``:
  la finestra principale passa alla scheda Carico con il barcode compilato.
"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..services import consultazione, impostazioni
from .componenti import Stepper, bottone
from . import animazioni
from .icone import ic_px, pixmap_icona
from .tema import M, rem, tema_attivo


class _MeterBarra(QFrame):
    """Barra di avanzamento: la larghezza è una frazione della barra."""

    def __init__(self, frazione: float, gravita: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MeterBarra")
        self.setProperty("gravita", gravita)
        self._frazione = max(0.0, min(1.0, frazione))
        self._frazione_finale = self._frazione
        self._animata = False
        self.setFixedHeight(M.METER_H)
        self.setMaximumWidth(M.METER_MAXW)
        self.style().unpolish(self)
        self.style().polish(self)

    def _aggiorna(self) -> None:
        sfondo_larghezza = self.parent().width() if self.parent() else self.width()
        self.setFixedWidth(int(round(sfondo_larghezza * self._frazione)))

    def _imposta(self, v: float) -> None:
        self._frazione = v
        self._aggiorna()

    def showEvent(self, evento) -> None:  # noqa: N802
        super().showEvent(evento)
        if not self._animata:  # la barra "cresce" solo alla prima comparsa
            self._animata = True
            animazioni.anima_valore(0.0, self._frazione_finale, self._imposta, animazioni.DURATA_LUNGA, ritardo=120)

    def resizeEvent(self, _evento) -> None:  # noqa: N802
        self._aggiorna()
        super().resizeEvent(_evento)


def _riga_avviso(
    z,  # noqa: ANN001 - modello di dominio (Pezzo)
    scheda: "SchedaAvvisi",
    parent: QWidget,
) -> QFrame:
    """Una riga ``QFrame#RigaAvviso`` per un pezzo da riordinare."""
    t = tema_attivo()
    livello = consultazione.livello_scorta(z, scheda._soglia)
    gravita = "avviso" if livello == "esaurimento" else "pericolo"
    etichetta = {"esaurito": "Esaurito", "sotto": "Sotto scorta", "esaurimento": "In esaurimento"}[livello]
    colore = z.colore.nome_visualizzato or z.colore.codice_normalizzato
    lunghezza = f"{z.lunghezza_mm:,}".replace(",", ".") if z.lunghezza_mm else "—"
    titolo = f"{z.profilo.codice} · {colore} · {lunghezza} mm — {etichetta}"

    sotto = [z.profilo.descrizione or ""]
    if z.ubicazione:
        sotto.append(z.ubicazione)
    if consultazione.quantita_per_scorta(z):
        sotto.append(f"{consultazione.quantita_per_scorta(z)} {'pezzo' if consultazione.quantita_per_scorta(z) == 1 else 'pezzi'} rimasti")
    else:
        sotto.append("nessun pezzo disponibile")

    riga = QFrame(parent)
    riga.setObjectName("RigaAvviso")
    riga.setProperty("gravita", gravita)  # "avviso" = giallo (in esaurimento)

    h = QHBoxLayout(riga)
    h.setContentsMargins(M.AVV_PH, M.AVV_PV, M.AVV_PH, M.AVV_PV)
    h.setSpacing(M.GAP)

    ico = QLabel(riga)
    ico.setObjectName("AvvIco")
    ico.setFixedSize(M.AVV_ICO, M.AVV_ICO)
    ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
    ico.setProperty("gravita", gravita)
    ico.setPixmap(pixmap_icona("alert", t.avviso if gravita == "avviso" else t.pericolo, ic_px(26)))
    h.addWidget(ico, 0, Qt.AlignmentFlag.AlignVCenter)

    colonna = QVBoxLayout()
    colonna.setContentsMargins(0, 0, 0, 0)
    colonna.setSpacing(rem(0.25))
    lab_t = QLabel(titolo, riga)
    lab_t.setObjectName("AvvTitolo")
    lab_s = QLabel(" · ".join(s for s in sotto if s), riga)
    lab_s.setObjectName("AvvSotto")
    lab_s.setTextFormat(Qt.TextFormat.PlainText)
    colonna.addWidget(lab_t)
    colonna.addWidget(lab_s)

    riferimento = z.scorta_minima if z.scorta_minima else scheda._soglia
    frazione = min(1.0, consultazione.quantita_per_scorta(z) / (riferimento * 3)) if (riferimento and consultazione.quantita_per_scorta(z) and consultazione.quantita_per_scorta(z) > 0) else 0.0
    sfondo = QFrame(riga)
    sfondo.setObjectName("MeterSfondo")
    sfondo.setFixedHeight(M.METER_H)
    sfondo.setMaximumWidth(M.METER_MAXW)
    barra = _MeterBarra(frazione, gravita, sfondo)
    sfondo_lay = QHBoxLayout(sfondo)
    sfondo_lay.setContentsMargins(0, 0, 0, 0)
    sfondo_lay.addWidget(barra)
    sfondo_lay.addStretch(1)
    colonna.addWidget(sfondo)
    h.addLayout(colonna, 1)

    btn_dettagli = bottone("Dettagli", dim="sm", parent=riga)
    btn_dettagli.clicked.connect(lambda _c=False, cid=z.colore.id: scheda.vai_a_colore.emit(cid))
    btn_carica = bottone("Carica", "ok", "sm", "up", riga)
    btn_carica.clicked.connect(
        lambda _c=False, bc=z.barcode or "": scheda.vai_a_scheda.emit("Carico", bc)
    )
    h.addWidget(btn_dettagli, 0, Qt.AlignmentFlag.AlignVCenter)
    h.addWidget(btn_carica, 0, Qt.AlignmentFlag.AlignVCenter)
    return riga


class SchedaAvvisi(QWidget):
    """Righe dei pezzi da riordinare (esauriti o sotto scorta)."""

    #: emesso da "Dettagli" di una riga: id del colore del pezzo
    vai_a_colore = Signal(int)
    #: emesso da "Carica" di una riga: nome scheda e barcode
    vai_a_scheda = Signal(str, str)
    #: emesso con il nuovo valore quando cambia la soglia globale
    soglia_cambiata = Signal(int)

    def __init__(self, factory, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._factory = factory
        self._pagina = 0
        self._dimensione_pagina = 30

        # Soglia globale di sotto scorta: letta una volta all'avvio; ogni
        # modifica dello stepper viene salvata in debounce (350 ms; 0 con
        # MAGAZZINO_NO_ANIM=1) e aggiorna DB, contatore e righe.
        self._soglia = impostazioni.SOGLIA_DEFAULT
        sessione = factory()
        try:
            self._soglia = impostazioni.leggi_soglia(sessione)
        finally:
            sessione.close()
        self._timer_soglia = QTimer(self)
        self._timer_soglia.setSingleShot(True)
        self._timer_soglia.setInterval(0 if os.environ.get("MAGAZZINO_NO_ANIM") else 350)
        self._timer_soglia.timeout.connect(self._salva_soglia)

        root = QVBoxLayout(self)
        root.setContentsMargins(M.PAG_H, M.PAG_T, M.PAG_H, M.PAG_B)
        root.setSpacing(M.GAP)

        # intestazione
        intest = QFrame(self)
        intest.setObjectName("Card")
        vi = QVBoxLayout(intest)
        vi.setContentsMargins(M.CARD_PAD, M.CARD_PAD, M.CARD_PAD, M.CARD_PAD)
        vi.setSpacing(rem(0.375))
        h = QHBoxLayout()
        h.setSpacing(M.GAP)
        colonna = QVBoxLayout()
        colonna.setContentsMargins(0, 0, 0, 0)
        colonna.setSpacing(rem(0.25))
        titolo = QLabel("Avvisi scorte", intest)
        titolo.setObjectName("TitoloCard")
        self.contatore = QLabel(intest)
        self.contatore.setObjectName("Dim")
        colonna.addWidget(titolo)
        colonna.addWidget(self.contatore)
        h.addLayout(colonna, 1)
        self.lbl_soglia = QLabel("Soglia sotto scorta", intest)
        self.lbl_soglia.setObjectName("Dim")
        self.stepper_soglia = Stepper(
            valore=self._soglia,
            minimo=impostazioni.SOGLIA_MIN,
            massimo=impostazioni.SOGLIA_MAX,
            parent=intest,
        )
        self.stepper_soglia.setFixedWidth(rem(9.5))  # ~230 px: − [campo] +
        self.stepper_soglia.campo.textChanged.connect(lambda _t: self._timer_soglia.start())
        self.lbl_unita = QLabel("pezzi", intest)
        self.lbl_unita.setObjectName("Dim")
        h.addWidget(self.lbl_soglia)
        h.addWidget(self.stepper_soglia)
        h.addWidget(self.lbl_unita)
        self.aggiorna_btn = bottone("Aggiorna", icona="refresh", parent=intest)
        self.aggiorna_btn.clicked.connect(self.aggiorna)
        h.addWidget(self.aggiorna_btn)
        vi.addLayout(h)
        root.addWidget(intest)

        # lista avvisi (scroll)
        self._corpo = QWidget(self)
        self._v_corpo = QVBoxLayout(self._corpo)
        self._v_corpo.setContentsMargins(0, 0, 0, 0)
        self._v_corpo.setSpacing(M.GAP_SM)
        area = QScrollArea(self)
        area.setWidgetResizable(True)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        area.setContentsMargins(0, 0, 0, 0)
        area.setWidget(self._corpo)
        root.addWidget(area, 1)
        paginazione = QHBoxLayout()
        self._precedente = bottone("Precedenti", parent=self)
        self._successiva = bottone("Successivi", parent=self)
        self._pagina_info = QLabel(self)
        self._precedente.clicked.connect(lambda: self._cambia_pagina(-1))
        self._successiva.clicked.connect(lambda: self._cambia_pagina(1))
        paginazione.addWidget(self._precedente)
        paginazione.addWidget(self._pagina_info, 1)
        paginazione.addWidget(self._successiva)
        root.addLayout(paginazione)

        # segnaposto vuoto
        self._vuoto = QFrame(self._corpo)
        self._vuoto.setObjectName("Card")
        vv = QVBoxLayout(self._vuoto)
        vv.setContentsMargins(rem(3.0), rem(3.0), rem(3.0), rem(3.0))
        vv.setSpacing(rem(0.5))
        ico = QLabel(self._vuoto)
        t = tema_attivo()
        ico.setPixmap(pixmap_icona("check", t.ok, ic_px(34)))
        ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lab_t = QLabel("Nessun avviso", self._vuoto)
        lab_t.setObjectName("AvvTitolo")
        lab_s = QLabel("Tutte le referenze sono sopra la soglia di scorta.", self._vuoto)
        lab_s.setObjectName("AvvSotto")
        for w in (ico, lab_t, lab_s):
            w.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vv.addWidget(ico)
        vv.addWidget(lab_t)
        vv.addWidget(lab_s)
        vv.addStretch(1)
        self._v_corpo.addWidget(self._vuoto)
        self._v_corpo.addStretch(1)  # le righe NON devono allungarsi a tutta l'altezza

        self.aggiorna()

    # ------------------------------------------------------------------
    def _vuole_mostrare(self) -> None:
        """Crea/rigenera le righe (chiamato da ``aggiorna``)."""
        sessione = self._factory()
        try:
            totale = consultazione.pezzi_avvisi(sessione, self._soglia, conteggio=True)
            self._pagina = min(self._pagina, max(0, (totale - 1) // self._dimensione_pagina))
            offset = self._pagina * self._dimensione_pagina
            lista = consultazione.pezzi_avvisi(sessione, self._soglia,
                limite=self._dimensione_pagina, offset=offset)
        finally:
            sessione.close()

        # rimuovi le righe precedenti
        i = 0
        while i < self._v_corpo.count():
            voce = self._v_corpo.itemAt(i)
            if voce is not None:
                w = voce.widget()
                if isinstance(w, QFrame) and w.objectName() == "RigaAvviso":
                    self._v_corpo.removeWidget(w)
                    w.deleteLater()
                    continue
            i += 1

        for z in lista:
            riga = _riga_avviso(z, self, self._corpo)
            self._v_corpo.insertWidget(self._v_corpo.count() - 1, riga)  # prima dello stretch

        n = len(lista)
        self._precedente.setEnabled(self._pagina > 0)
        self._successiva.setEnabled(offset + n < totale)
        self._pagina_info.setText(f"{offset + 1 if totale else 0}–{offset + n} di {totale} avvisi")
        self._vuoto.setVisible(n == 0)
        # Sottotitolo: spiega la soglia globale corrente.
        self.contatore.setText(
            f"Sotto scorta: fino a {self._soglia} pezzi · In esaurimento: "
            f"fino a {impostazioni.soglia_esaurimento(self._soglia)} pezzi"
        )

    def _salva_soglia(self) -> None:
        """Salva la soglia dallo stepper (debounce) ed emette ``soglia_cambiata``."""
        testo = self.stepper_soglia.campo.text()
        try:
            valore = int(testo) if testo.strip() else self._soglia
        except ValueError:
            return
        sessione = self._factory()
        try:
            salvato = impostazioni.imposta_soglia(sessione, valore)
        finally:
            sessione.close()
        if salvato != self._soglia:
            self._pagina = 0
            self._soglia = salvato
            self.soglia_cambiata.emit(salvato)
            self.aggiorna()
        # Allinea lo stepper al valore effettivamente salvato (fuori range).
        if testo.isdigit() and int(testo) != salvato:
            self.stepper_soglia.campo.setText(str(salvato))

    def aggiorna(self) -> None:
        self._vuole_mostrare()

    def _cambia_pagina(self, delta):
        self._pagina = max(0, self._pagina + delta)
        self.aggiorna()
