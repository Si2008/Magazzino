"""Animazioni di transizione: brevi, sobrie, spegnibili.

Regole:
- tutte le funzioni sono NO-OP (stato finale immediato) se ``attive()`` è False;
- nessuna animazione lascia effetti grafici/proprietà "appesi": a fine corsa si ripulisce;
- si anima solo ciò che il layout non gestisce (opacità, overlay, posizione di widget flottanti).
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable

from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    QObject,
    QPropertyAnimation,
    QSettings,
    Qt,
    QTimer,
    QVariantAnimation,
)
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel, QWidget

DURATA_BREVE = 140
DURATA = 200
DURATA_LUNGA = 320

_CHIAVE = "interfaccia/animazioni"
_ATTIVE: bool | None = None
_in_corso: dict[int, object] = {}  # tiene vive le animazioni (id widget -> animazione)


# ---------------------------------------------------------------- attivazione
def _windows_animazioni_attive() -> bool:
    """Rispetta l'impostazione di Windows "Mostra animazioni" (SPI_GETCLIENTAREAANIMATION)."""
    if sys.platform != "win32":
        return True
    try:
        import ctypes

        valore = ctypes.c_int(1)
        ok = ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(valore), 0)
        return bool(valore.value) if ok else True
    except Exception:  # noqa: BLE001 - mai bloccare l'avvio per un'animazione
        return True


def attive() -> bool:
    global _ATTIVE
    if _ATTIVE is None:
        if os.environ.get("MAGAZZINO_NO_ANIM") == "1":
            _ATTIVE = False
        else:
            from ..percorsi_installazione import preferenze
            salvato = preferenze("MagazzinoProfili", "MagazzinoProfili").value(_CHIAVE, None)
            if salvato is None:
                _ATTIVE = _windows_animazioni_attive()
            else:
                _ATTIVE = str(salvato).lower() in ("1", "true")
    return _ATTIVE


def imposta_attive(valore: bool, salva: bool = True) -> None:
    global _ATTIVE
    _ATTIVE = bool(valore)
    if salva:
        from ..percorsi_installazione import preferenze
        preferenze("MagazzinoProfili", "MagazzinoProfili").setValue(_CHIAVE, _ATTIVE)


def _tieni(widget: QWidget, anim) -> None:
    chiave = id(widget)
    vecchia = _in_corso.get(chiave)
    if vecchia is not None and vecchia is not anim:
        vecchia.stop()
    _in_corso[chiave] = anim
    anim.finished.connect(lambda c=chiave, a=anim: _in_corso.pop(c, None) if _in_corso.get(c) is a else None)


# ---------------------------------------------------------------- dissolvenza
def dissolvenza(widget: QWidget, durata: int = DURATA) -> None:
    """Fade-in del widget (0 -> 1). L'effetto grafico viene rimosso a fine corsa."""
    if not attive() or widget is None:
        return
    effetto = QGraphicsOpacityEffect(widget)
    effetto.setOpacity(0.0)
    widget.setGraphicsEffect(effetto)
    anim = QPropertyAnimation(effetto, b"opacity", widget)
    anim.setDuration(durata)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _fine() -> None:
        # rimozione differita: non si distrugge l'effetto dentro il suo stesso segnale
        QTimer.singleShot(0, lambda: widget.setGraphicsEffect(None) if widget.graphicsEffect() is effetto else None)

    anim.finished.connect(_fine)
    _tieni(widget, anim)
    anim.start()


# ---------------------------------------------------------------- cambio tema (dissolvenza incrociata)
def transizione_tema(finestra: QWidget, applica: Callable[[], None], durata: int = 240) -> None:
    """Esegue ``applica`` (cambio tema) e dissolve dal vecchio aspetto al nuovo."""
    if not attive() or not finestra.isVisible():
        applica()
        return
    istantanea = finestra.grab()
    applica()
    velo = QLabel(finestra)
    velo.setPixmap(istantanea)
    velo.setGeometry(finestra.rect())
    velo.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    velo.show()
    velo.raise_()
    effetto = QGraphicsOpacityEffect(velo)
    velo.setGraphicsEffect(effetto)
    anim = QPropertyAnimation(effetto, b"opacity", velo)
    anim.setDuration(durata)
    anim.setStartValue(1.0)
    anim.setEndValue(0.0)
    anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
    anim.finished.connect(velo.deleteLater)
    _tieni(velo, anim)
    anim.start()


# ---------------------------------------------------------------- numeri che "salgono"
def conta_su(
    destinazione,  # qualsiasi oggetto con set_valore(str), es. CardKPI
    nuovo: float,
    formatta: Callable[[float], str],
    durata: int = DURATA_LUNGA,
) -> None:
    """Porta il valore mostrato dal precedente a ``nuovo``; a fine corsa il testo è ESATTAMENTE ``formatta(nuovo)``."""
    precedente = float(getattr(destinazione, "_valore_num", 0.0))
    destinazione._valore_num = float(nuovo)
    if not attive() or precedente == nuovo:
        destinazione.set_valore(formatta(nuovo))
        return
    anim = QVariantAnimation(destinazione if isinstance(destinazione, QObject) else None)
    anim.setDuration(durata)
    anim.setStartValue(precedente)
    anim.setEndValue(float(nuovo))
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.valueChanged.connect(lambda v: destinazione.set_valore(formatta(round(v) if float(nuovo).is_integer() else v)))
    anim.finished.connect(lambda: destinazione.set_valore(formatta(nuovo)))
    _tieni(destinazione, anim)
    anim.start()


def anima_valore(
    da: float, a: float, aggiorna: Callable[[float], None], durata: int = DURATA_LUNGA, ritardo: int = 0
) -> None:
    """Interpola ``da`` -> ``a`` chiamando ``aggiorna(v)``; senza animazioni chiama solo ``aggiorna(a)``."""
    if not attive() or da == a:
        aggiorna(a)
        return
    aggiorna(da)
    anim = QVariantAnimation()
    anim.setDuration(durata)
    anim.setStartValue(float(da))
    anim.setEndValue(float(a))
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.valueChanged.connect(lambda v: aggiorna(float(v)))
    anim.finished.connect(lambda: aggiorna(float(a)))
    chiave = id(anim)
    _in_corso[chiave] = anim
    anim.finished.connect(lambda c=chiave: _in_corso.pop(c, None))
    if ritardo:
        QTimer.singleShot(ritardo, anim.start)
    else:
        anim.start()


# ---------------------------------------------------------------- scossa (errore di validazione)
def scuoti(widget: QWidget, ampiezza: int = 8, durata: int = DURATA_LUNGA) -> None:
    """Scossa orizzontale breve. Da chiamare quando il layout è già assestato (es. QTimer.singleShot(0, ...))."""
    if not attive() or not widget.isVisible():
        return
    base = widget.pos()
    anim = QPropertyAnimation(widget, b"pos", widget)
    anim.setDuration(durata)
    for k, dx in ((0.0, 0), (0.15, -ampiezza), (0.35, ampiezza), (0.55, -ampiezza * 3 // 4), (0.75, ampiezza * 3 // 4), (1.0, 0)):
        anim.setKeyValueAt(k, base + QPoint(dx, 0))
    anim.setEasingCurve(QEasingCurve.Type.Linear)
    _tieni(widget, anim)
    anim.start()


# ---------------------------------------------------------------- toast
def entra_da_destra(widget: QWidget, spostamento: int = 36, durata: int = DURATA) -> None:
    """Scorre dal bordo destro verso la posizione corrente e compare in dissolvenza."""
    if not attive():
        return
    finale = widget.pos()
    effetto = QGraphicsOpacityEffect(widget)
    effetto.setOpacity(0.0)
    widget.setGraphicsEffect(effetto)
    scorri = QPropertyAnimation(widget, b"pos", widget)
    scorri.setDuration(durata)
    scorri.setStartValue(finale + QPoint(spostamento, 0))
    scorri.setEndValue(finale)
    scorri.setEasingCurve(QEasingCurve.Type.OutCubic)
    appari = QPropertyAnimation(effetto, b"opacity", widget)
    appari.setDuration(durata)
    appari.setStartValue(0.0)
    appari.setEndValue(1.0)
    gruppo = QParallelAnimationGroup(widget)
    gruppo.addAnimation(scorri)
    gruppo.addAnimation(appari)

    def _fine() -> None:
        QTimer.singleShot(0, lambda: widget.setGraphicsEffect(None) if widget.graphicsEffect() is effetto else None)

    gruppo.finished.connect(_fine)
    _tieni(widget, gruppo)
    gruppo.start()


def esci_e_chiudi(widget: QWidget, durata: int = DURATA_BREVE) -> None:
    """Dissolve il widget e poi lo chiude (``close``). Senza animazioni chiude subito."""
    if not attive() or not widget.isVisible():
        widget.close()
        return
    effetto = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effetto)
    anim = QPropertyAnimation(effetto, b"opacity", widget)
    anim.setDuration(durata)
    anim.setStartValue(1.0)
    anim.setEndValue(0.0)
    anim.finished.connect(widget.close)
    _tieni(widget, anim)
    anim.start()
