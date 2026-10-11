"""Tema grafico dell'interfaccia (design "grande" del mockup).

Tutte le misure numeriche dell'UI passano da :func:`px` (API Qt intere)
o da :func:`css` (stringhe di foglio di stile, con i decimali).
I valori di riferimento sono i pixel del mockup; ``SCALA`` permette di
ingrandire/ridurre l'intera interfaccia in un colpo solo.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QColor

SCALA: float = 1.0


def px(valore: float | int) -> int:
    """Misura di design in pixel interi (per le API Qt che richiedono int)."""
    return max(1, int(round(valore * SCALA)))


def css(valore: float | int) -> str:
    """Misura di design come stringa CSS (conserva i decimali)."""
    return f"{(valore * SCALA):g}px"


@dataclass(frozen=True)
class Tema:
    sfondo: str
    superficie: str
    carta: str
    carta2: str
    bordo: str
    bordo_forte: str
    testo: str
    testo_dim: str
    testo_debole: str
    accento: str
    accento_sfondo: str
    ok: str
    avviso: str
    pericolo: str


SCURO = Tema(
    sfondo="#12141a",
    superficie="#171a21",
    carta="#1e222b",
    carta2="#252a35",
    bordo="#2c323e",
    bordo_forte="#3b4354",
    testo="#eceef2",
    testo_dim="#9ba3b1",
    testo_debole="#6f7787",
    accento="#5b8dff",
    accento_sfondo="#243350",
    ok="#3ccb82",
    avviso="#f0b04a",
    pericolo="#f0605a",
)

CHIARO = Tema(
    sfondo="#e9ecf2",
    superficie="#f4f6fa",
    carta="#ffffff",
    carta2="#f2f4f9",
    bordo="#dde2ec",
    bordo_forte="#c4ccdb",
    testo="#1c2230",
    testo_dim="#5a6478",
    testo_debole="#8d96a8",
    accento="#2b62e0",
    accento_sfondo="#e3ebfc",
    ok="#149e63",
    avviso="#b57d1e",
    pericolo="#d64545",
)

ATTUALE: Tema = SCURO


def alterna_tema() -> Tema:
    """Cambia tema (scuro <-> chiaro) e restituisce quello attivo."""
    global ATTUALE
    ATTUALE = CHIARO if ATTUALE is SCURO else SCURO
    return ATTUALE


def tema_attivo() -> Tema:
    return ATTUALE


# ---------------------------------------------------------------------------
# Icona "pallino colore": il colore è derivato in modo deterministico dal
# codice (come nel mockup), così è stabile tra sessioni.
# ---------------------------------------------------------------------------

_NOTI: dict[str, str] = {
    "AN007": "#2f3238",
    "AN001": "#b9bec9",
    "RAL9010": "#f5f6f7",
    "RAL9005": "#252525",
    "ROSSO": "#c8443c",
    "BLU": "#33619e",
    "GRIGIO": "#8a909b",
    "NERO": "#232529",
    "BIANCO": "#f0f1f3",
}


def colore_di_codice(codice: str) -> str:
    """Colore esadecimale associato a un codice colore (deterministico)."""
    t = (codice or "").upper().strip()
    if t in _NOTI:
        return _NOTI[t]
    h = 0
    for i, carattere in enumerate(t):
        h = (h * 31 + ord(carattere) * 7) % 360
    return _hsl(h, 18, 55)


def _hsl(h: int, s: int, l: int) -> str:
    """Converte HSL in esadecimale (implementazione compatta)."""
    s /= 100.0
    l /= 100.0
    k = lambda d: (d + h / 30.0) % 12.0
    a = s * min(l, 1.0 - l)
    f = lambda d: l - a * max(-1.0, min(k(d) - 3.0, min(9.0 - k(d), 1.0)))
    return "#%02x%02x%02x" % tuple(int(round(f(d) * 255)) for d in (0, 8, 4))


def colore_sbiadito(hx: str, sfondo: str, peso: float = 0.65) -> str:
    """Mescola ``hx`` con ``sfondo`` (colore sbiadito, per tab senza pezzi)."""
    a = QColor(hx)
    b = QColor(sfondo)
    r = int(a.red() * peso + b.red() * (1 - peso))
    g = int(a.green() * peso + b.green() * (1 - peso))
    v = int(a.blue() * peso + b.blue() * (1 - peso))
    return "#%02x%02x%02x" % (r, g, v)


# ---------------------------------------------------------------------------
# Foglio di stile globale
# ---------------------------------------------------------------------------

def qss_globale(t: Tema) -> str:
    """Foglio di stile globale dell'applicazione."""
    return f"""
* {{ outline: none; }}
QWidget {{
    background: {t.sfondo};
    color: {t.testo};
    font-family: "Segoe UI Variable Text", "Segoe UI", "Noto Sans", sans-serif;
    font-size: {css(15)};
}}
QMainWindow, QDialog {{ background: {t.sfondo}; }}

QTabWidget::pane {{
    border: 1px solid {t.bordo};
    border-radius: {css(10)};
    background: {t.superficie};
    top: -1px;
}}
QTabBar {{ background: transparent; }}
QTabBar::tab {{
    background: transparent;
    color: {t.testo_dim};
    padding: {css(9)} {css(14)};
    margin-right: {css(2)};
    border: 1px solid transparent;
    border-bottom: none;
    border-top-left-radius: {css(9)};
    border-top-right-radius: {css(9)};
    font-size: {css(14.5)};
    font-weight: 600;
}}
QTabBar::tab:selected {{
    background: {t.superficie};
    color: {t.testo};
    border-color: {t.bordo};
}}
QTabBar::tab:hover:!selected {{ color: {t.testo}; background: {t.carta}; }}

QLineEdit, QComboBox {{
    background: {t.carta2};
    border: 1px solid {t.bordo};
    border-radius: {css(8)};
    padding: {css(8)} {css(11)};
    selection-background-color: {t.accento_sfondo};
}}
QLineEdit:focus, QComboBox:focus {{ border-color: {t.accento}; }}
QComboBox::drop-down {{
    border: none; width: {css(26)};
}}
QComboBox QAbstractItemView {{
    background: {t.carta};
    border: 1px solid {t.bordo_forte};
    selection-background-color: {t.accento_sfondo};
    outline: none;
}}

QPushButton {{
    background: {t.carta2};
    border: 1px solid {t.bordo};
    color: {t.testo};
    border-radius: {css(8)};
    padding: {css(8)} {css(14)};
    font-weight: 600;
}}
QPushButton:hover {{ border-color: {t.bordo_forte}; background: {t.carta}; }}
QPushButton:pressed {{ background: {t.accento_sfondo}; }}
QPushButton:disabled {{ color: {t.testo_debole}; }}

QPushButton[classe="primario"] {{
    background: {t.accento};
    border: 1px solid {t.accento};
    color: #ffffff;
}}
QPushButton[classe="primario"]:hover {{ background: #6d9aff; }}
QPushButton[classe="primario"]:pressed {{ background: #4a7ceb; }}
QPushButton[classe="primario"]:disabled {{ background: {t.carta2}; color: {t.testo_debole}; border-color: {t.bordo}; }}

QPushButton[classe="pericolo"] {{
    background: {t.carta};
    border: 1px solid {t.pericolo};
    color: {t.pericolo};
}}
QPushButton[classe="pericolo"]:hover {{ background: {t.pericolo}; color: #ffffff; }}

QTableWidget {{
    background: {t.superficie};
    border: 1px solid {t.bordo};
    border-radius: {css(10)};
    gridline-color: {t.bordo};
    selection-background-color: {t.accento_sfondo};
    selection-color: {t.testo};
}}
QTableWidget::item {{ padding: {css(6)}; border: none; }}
QHeaderView::section {{
    background: {t.carta};
    color: {t.testo_dim};
    border: none;
    border-bottom: 1px solid {t.bordo};
    border-right: 1px solid {t.bordo};
    padding: {css(8)} {css(10)};
    font-weight: 700;
    font-size: {css(13)};
}}
QTableCornerButton::section {{ background: {t.carta}; border: none; }}

QScrollBar:vertical {{ background: transparent; width: {css(12)}; margin: 0; }}
QScrollBar::handle:vertical {{
    background: {t.bordo_forte}; border-radius: {css(6)}; min-height: {css(30)};
}}
QScrollBar::handle:vertical:hover {{ background: {t.testo_debole}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: {css(12)}; margin: 0; }}
QScrollBar::handle:horizontal {{
    background: {t.bordo_forte}; border-radius: {css(6)}; min-width: {css(30)};
}}
QScrollBar::handle:horizontal:hover {{ background: {t.testo_debole}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}

QStatusBar {{
    background: {t.carta};
    border-top: 1px solid {t.bordo};
    color: {t.testo_dim};
    font-size: {css(13)};
}}
QStatusBar::item {{ border: none; }}

QToolTip {{
    background: {t.carta2};
    color: {t.testo};
    border: 1px solid {t.bordo_forte};
    padding: {css(6)} {css(9)};
    font-size: {css(13)};
}}

QMenu {{
    background: {t.carta};
    border: 1px solid {t.bordo_forte};
    border-radius: {css(9)};
    padding: {css(5)};
}}
QMenu::item {{
    padding: {css(7)} {css(14)};
    border-radius: {css(6)};
    color: {t.testo};
}}
QMenu::item:selected {{ background: {t.accento_sfondo}; }}
QMenu::separator {{ height: 1px; background: {t.bordo}; margin: {css(4)} {css(6)}; }}

QLabel#TitoloSezione {{
    font-size: {css(17)};
    font-weight: 800;
    letter-spacing: -0.2px;
}}
QLabel#SottotitoloSezione {{ color: {t.testo_dim}; font-size: {css(13.5)}; }}
QLabel#TestoDebole {{ color: {t.testo_debole}; }}
QLabel#TestoDim {{ color: {t.testo_dim}; }}
"""


def qss_card(t: Tema) -> str:
    """Stile per un widget "card" (fondo carta, bordo, arrotondato)."""
    return (
        f"border: 1px solid {t.bordo};\n"
        f"border-radius: {css(10)};\n"
        f"background: {t.carta};"
    )


def qss_badge(t: Tema, colore: str) -> str:
    """Badge rotondo (es. contatore avvisi)."""
    return (
        f"background: {colore};\n"
        f"color: #ffffff;\n"
        f"border-radius: {css(9)};\n"
        f"min-width: {css(18)};\n"
        f"min-height: {css(18)};"
    )
