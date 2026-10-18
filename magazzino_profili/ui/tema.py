"""Tema grafico dell'interfaccia (design "grande" del mockup).

Tutte le misure numeriche dell'UI passano da :func:`rem` (mockup,
``html{font-size:24px}``) o da :func:`px` (pixel di design, per le API Qt
interne) o da :func:`css` (stringhe di foglio di stile).
I valori di riferimento sono i pixel del mockup; ``SCALA`` permette di
ingrandire/ridurre l'intera interfaccia in un colpo solo.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QColor

SCALA: float = 1.0

ROOT_PX: int = 24  # html{font-size:24px} del mockup: 1rem = 24 px


def rem(valore: float) -> int:
    """Misura del mockup (in rem) convertita in pixel interi."""
    return max(1, int(round(valore * ROOT_PX * SCALA)))


def alfa(hx: str, a: float) -> str:
    """Colore ``rgba(r, g, b, A)`` con A INTERO 0-255 (Qt non garantisce gli alfa decimali)."""
    c = QColor(hx)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {int(round(a * 255))})"


class M:
    """Tutte le misure dell'interfaccia, ricavate dal mockup (rem x 24). NON scrivere numeri a mano altrove."""

    # font
    FONT = rem(0.8438)         # 20  body
    FONT_BTN = rem(0.8125)     # 20
    FONT_BTN_LG = rem(0.875)   # 21
    FONT_BTN_SM = rem(0.75)    # 18
    FONT_H2 = rem(0.9375)      # 22
    FONT_HINT = rem(0.7812)    # 19
    FONT_SMALL = rem(0.75)     # 18
    FONT_XS = rem(0.7188)      # 17
    # raggi
    R = rem(0.75)              # 18  card, tessere
    R_SM = rem(0.5)            # 12  campi, pulsanti
    R_MENU = rem(0.625)        # 15  menu, righe avviso, tab, toast
    R_DLG = rem(0.875)         # 21  finestre di dialogo
    # pulsanti
    BTN_PV, BTN_PH = rem(0.5), rem(0.8125)            # 12, 20
    BTN_LG_PV, BTN_LG_PH = rem(0.75), rem(1.0)        # 18, 24
    BTN_SM_PV, BTN_SM_PH = rem(0.3125), rem(0.625)    # 8, 15
    BTN_ICONA = rem(2.25)                             # 54
    # barra del titolo / schede / pagina
    TITOLO_PV, TITOLO_PH = rem(0.625), rem(1.125)     # 15, 27
    LOGO = rem(1.875)                                 # 45
    FONT_BRAND = rem(0.9375)                          # 22
    TAB_PV, TAB_PH = rem(0.625), rem(1.0625)          # 15, 26
    CONTA = rem(1.1875)                               # 28 (badge contatore)
    FONT_CONTA = rem(0.6875)                          # 16
    PAG_T, PAG_H, PAG_B = rem(1.25), rem(1.375), rem(1.75)   # 30, 33, 42
    CARD_PAD = rem(1.125)                             # 27
    GAP = rem(0.875)                                  # 21
    GAP_SM = rem(0.75)                                # 18
    # KPI
    KPI_PV, KPI_PH = rem(0.875), rem(1.0)             # 21, 24
    KPI_ICO = rem(2.375)                              # 57
    KPI_ICO_R = rem(0.625)                            # 15
    KPI_ICO_SVG = rem(1.25)                           # 30
    KPI_GAP = rem(0.8125)                             # 20
    FONT_KPI_V = rem(1.3125)                          # 32
    # inventario
    ASIDE_W = rem(20.625)                             # 495
    TOOLBAR_PAD = rem(0.875)                          # 21
    TOOLBAR_GAP = rem(0.5)                            # 12
    CAMPO_PV, CAMPO_PH = rem(0.5625), rem(0.625)      # 14, 15
    TH_PV, TH_PH = rem(0.6875), rem(0.875)            # 16, 21
    TD_PV, TD_PH = rem(0.625), rem(0.875)             # 15, 21
    PILL_PV, PILL_PH = rem(0.125), rem(0.5625)        # 3, 14
    PILL_PUNTO = rem(0.375)                           # 9
    RIGA_INV = 76                                     # altezza riga inventario (verificata a screenshot)
    # colonna laterale
    LAT_PV, LAT_PH = rem(1.0), rem(1.125)             # 24, 27
    FONT_LAT_TITOLO = rem(1.125)                      # 27
    # form
    CAMPO_GAP = rem(0.375)                            # 9
    CAMPO_MB = rem(0.875)                             # 21
    BIG_FONT = rem(1.125)                             # 27
    BIG_PV, BIG_PH = rem(0.8125), rem(0.875)          # 20, 21
    SPLIT_SX = rem(27.5)                              # 660 (colonna form)
    PROF_DX = rem(22.5)                               # 540
    IMG_BOX_H = rem(12.5)                             # 300
    CHIP_PV, CHIP_PH = rem(0.25), rem(0.6875)         # 6, 16
    CHIP_R = 16                                       # raggio chip: Qt IGNORA border-radius > altezza/2 (chip alti ~35 px)
    ANT_PV, ANT_PH = rem(0.75), rem(0.875)            # 18, 21
    FONT_FLUSSO = rem(0.9375)                         # 22
    MSG_PV, MSG_PH = rem(0.5625), rem(0.75)           # 14, 18
    STEP_BTN = rem(2.375)                             # 57
    # avvisi / movimenti / stato / toast
    AVV_PV, AVV_PH = rem(0.8125), rem(1.0)            # 20, 24
    AVV_ICO = rem(2.25)                               # 54
    METER_H = rem(0.3125)                             # 8
    METER_MAXW = rem(18.75)                           # 450
    MOV_ICO = rem(1.75)                               # 42
    MOV_PV = rem(0.5625)                              # 14
    MOV_GAP = rem(0.6875)                             # 16
    STATO_PV, STATO_PH = rem(0.5), rem(1.125)         # 12, 27
    TOAST_DX = rem(1.125)                             # 27
    TOAST_BASSO = rem(3.25)                           # 78
    TOAST_BORDO = rem(0.25)                           # 6
    TOAST_MAXW = rem(26.25)                           # 630
    MENU_MINW = rem(16.875)                           # 405


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
    bordo_campo: str  # bordo di campi/pulsanti: contrasto >= 3:1 (WCAG 1.4.11)
    testo: str
    testo_dim: str
    testo_debole: str
    accento: str
    accento_sfondo: str
    ok: str
    avviso: str
    pericolo: str
    # inchiostro (testo sopra pulsanti pieni) e veli (sfondi tenui, alfa INTERO)
    accento_inchiostro: str
    ok_inchiostro: str
    pericolo_inchiostro: str
    accento_vel: str
    ok_vel: str
    avviso_vel: str
    pericolo_vel: str


SCURO = Tema(
    sfondo="#12141a",
    superficie="#171a21",
    carta="#1e222b",
    carta2="#252a35",
    bordo="#2c323e",
    bordo_forte="#3b4354",
    bordo_campo="#6a748a",
    testo="#eceef2",
    testo_dim="#9ba3b1",
    testo_debole="#8d97ab",
    accento="#5b8dff",
    accento_sfondo="#243350",
    ok="#3ccb82",
    avviso="#f0b04a",
    pericolo="#f47a74",
    accento_inchiostro="#0b1633",
    ok_inchiostro="#06261a",
    pericolo_inchiostro="#2c0a08",
    accento_vel="rgba(91, 141, 255, 36)",
    ok_vel="rgba(60, 203, 130, 36)",
    avviso_vel="rgba(240, 176, 74, 38)",
    pericolo_vel="rgba(244, 122, 116, 36)",
)

CHIARO = Tema(
    sfondo="#e9ecf2",
    superficie="#f3f5f9",
    carta="#ffffff",
    carta2="#f1f3f8",
    bordo="#dde1ea",
    bordo_forte="#c6ccda",
    bordo_campo="#7d889d",
    testo="#161a22",
    testo_dim="#556073",
    testo_debole="#5d6a7d",
    accento="#2b62e0",
    accento_sfondo="#e3ebfc",
    ok="#117a48",
    avviso="#8f5900",
    pericolo="#c43832",
    accento_inchiostro="#ffffff",
    ok_inchiostro="#ffffff",
    pericolo_inchiostro="#ffffff",
    accento_vel="rgba(43, 98, 224, 26)",
    ok_vel="rgba(17, 122, 72, 28)",
    avviso_vel="rgba(201, 125, 0, 36)",
    pericolo_vel="rgba(196, 56, 50, 26)",
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
    "AN007": "#a9aeb7",
    "AN001": "#b9bec9",
    "RAL9010": "#f2f1ea",
    "RAL9005": "#0e0e10",
    "RAL7016": "#383e42",
    "RAL8014": "#4a3728",
    "ROSSO": "#c8443c",
    "BLU": "#33619e",
    "GRIGIO": "#8a909b",
    "NERO": "#232529",
    "BIANCO": "#f0f1f3",
}


def _hsl(h: int, s: int, l: int) -> str:
    """Converte HSL in esadecimale (implementazione compatta)."""
    s /= 100.0
    l /= 100.0
    k = lambda d: (d + h / 30.0) % 12.0
    a = s * min(l, 1.0 - l)
    f = lambda d: l - a * max(-1.0, min(k(d) - 3.0, min(9.0 - k(d), 1.0)))
    return "#%02x%02x%02x" % tuple(int(round(f(d) * 255)) for d in (0, 8, 4))


def colore_di_codice(codice: str) -> str:
    """Colore esadecimale associato a un codice colore (deterministico)."""
    t = (codice or "").upper().strip()
    if t in _NOTI:
        return _NOTI[t]
    h = sum(ord(c) * 7 for c in t) % 360
    return _hsl(h, 18, 55)


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

def colore_da_css(valore: str) -> QColor:
    """QColor da ``#rrggbb`` oppure da ``rgba(r, g, b, A)`` (A intero 0-255)."""
    if valore.startswith("rgba"):
        r, g, b, a = (int(x) for x in valore[valore.index("(") + 1 : valore.index(")")].split(","))
        return QColor(r, g, b, a)
    return QColor(valore)


def schiarisci(hx: str, percento: int = 108) -> str:
    """Equivalente di ``filter: brightness(1.08)`` per l'hover dei pulsanti pieni."""
    return QColor(hx).lighter(percento).name()


def palette_tema(t: Tema):
    """QPalette coerente col tema: i widget senza regola QSS (viewport di QScrollArea, finestre di
    sistema, dialoghi nativi) non devono ricadere sui grigi chiari di default."""
    from PySide6.QtGui import QPalette

    p = QPalette()
    R = QPalette.ColorRole
    for ruolo, colore in (
        (R.Window, t.sfondo), (R.WindowText, t.testo), (R.Base, t.superficie),
        (R.AlternateBase, t.carta2), (R.Text, t.testo), (R.Button, t.carta2),
        (R.ButtonText, t.testo), (R.ToolTipBase, t.carta2), (R.ToolTipText, t.testo),
        (R.Highlight, t.accento), (R.HighlightedText, t.accento_inchiostro),
        (R.PlaceholderText, t.testo_dim), (R.Link, t.accento),
    ):
        p.setColor(ruolo, colore_da_css(colore))
    return p


def qss_globale(t: Tema) -> str:
    """Foglio di stile globale. Le misure vengono SOLO da ``M`` (mockup, rem x 24)."""
    from .icone import percorso_icona_png

    chev = percorso_icona_png("chev", t.testo_dim, rem(0.875))
    chev_t = percorso_icona_png("chev", t.testo, rem(0.875))
    return f"""
* {{ outline: none; }}
QWidget {{
    color: {t.testo};
    font-family: "Segoe UI Variable", "Segoe UI", "Noto Sans", "DejaVu Sans", sans-serif;
    font-size: {M.FONT}px;
}}
QWidget#Finestra {{ background: {t.sfondo}; }}
QDialog, QMessageBox {{ background: {t.carta}; }}
QLabel {{ background: transparent; }}

/* ---------- barra del titolo ---------- */
QFrame#Titlebar {{ background: {t.carta}; border: none; border-bottom: 1px solid {t.bordo}; }}
QLabel#Logo {{ background: {t.accento}; border-radius: {rem(0.5625)}px; }}
QLabel#BrandNome {{ font-size: {M.FONT_BRAND}px; font-weight: 700; }}
QLabel#BrandSotto {{ color: {t.testo_debole}; font-size: {M.FONT_XS}px; }}

/* ---------- schede principali ---------- */
QTabWidget::pane {{ border: none; border-top: 1px solid {t.bordo}; background: {t.superficie}; top: -1px; }}
QTabWidget::tab-bar {{ left: {M.TITOLO_PH}px; }}
QTabBar {{ background: transparent; }}
QTabBar#TabPrincipali::tab {{
    background: transparent; color: {t.testo_dim};
    padding: {M.TAB_PV}px {M.TAB_PH}px; margin-right: 2px;
    border: 1px solid transparent; border-bottom: none;
    border-top-left-radius: {M.R_MENU}px; border-top-right-radius: {M.R_MENU}px;
    font-size: {M.FONT}px; font-weight: 600;
}}
QTabBar#TabPrincipali::tab:selected {{ background: {t.superficie}; color: {t.testo}; border-color: {t.bordo}; }}
QTabBar#TabPrincipali::tab:hover:!selected {{ color: {t.testo}; }}
QLabel#Conta {{
    background: {t.pericolo}; color: {t.pericolo_inchiostro}; font-size: {M.FONT_CONTA}px; font-weight: 700;
    border-radius: {M.CONTA // 2}px; min-width: {M.CONTA}px; max-height: {M.CONTA}px; min-height: {M.CONTA}px;
    padding: 0 {rem(0.375)}px;
}}

/* ---------- schede colore (chip) dell'Inventario ---------- */
QTabBar#TabColori::tab {{
    background: {t.carta2}; color: {t.testo_dim}; border: 1px solid {t.bordo_campo};
    border-radius: {M.CHIP_R}px;
    padding: {M.CHIP_PV}px {M.CHIP_PH}px; margin: 0 {rem(0.375)}px 0 0;
    font-size: {M.FONT_SMALL}px; font-weight: 400;
}}
QTabBar#TabColori::tab:selected {{ background: {t.accento_vel}; border-color: {t.accento}; color: {t.testo}; }}
QTabBar#TabColori::tab:hover:!selected {{ border-color: {t.accento}; color: {t.testo}; }}
QTabBar#TabColori::scroller {{ width: {rem(1.5)}px; }}

/* ---------- card, barre, anteprime ---------- */
QFrame#Card {{ background: {t.carta}; border: 1px solid {t.bordo}; border-radius: {M.R}px; }}
QFrame#CardKPI {{ background: {t.carta}; border: 1px solid {t.bordo}; border-radius: {M.R}px; }}
QFrame#CardKPI[cliccabile="true"]:hover {{ border-color: {t.accento}; }}
QLabel#KpiIco {{ background: {t.accento_vel}; border-radius: {M.KPI_ICO_R}px; }}
QLabel#KpiIco[tono="bad"] {{ background: {t.pericolo_vel}; }}
QLabel#KpiIco[tono="good"] {{ background: {t.ok_vel}; }}
QLabel#KpiValore {{ font-size: {M.FONT_KPI_V}px; font-weight: 700; }}
QLabel#KpiEtichetta {{ font-size: {M.FONT_SMALL}px; color: {t.testo_dim}; }}
QFrame#BarraStrumenti {{ background: transparent; border: none; border-bottom: 1px solid {t.bordo}; }}
QLabel#Piede {{ color: {t.testo_dim}; font-size: {M.FONT_SMALL}px; border-top: 1px solid {t.bordo};
    padding: {rem(0.6875)}px {M.TD_PH}px; }}
QFrame#Lat {{ background: transparent; border: none; border-bottom: 1px solid {t.bordo}; }}
QLabel#LatTitolo {{ font-size: {M.FONT_LAT_TITOLO}px; font-weight: 700; }}
QLabel#LatSezione {{ font-size: {M.FONT_XS}px; color: {t.testo_debole}; font-weight: 600; }}
QLabel#Dim {{ color: {t.testo_dim}; }}
QLabel#Debole {{ color: {t.testo_debole}; }}
QLabel#Etichetta {{ color: {t.testo_dim}; font-size: {M.FONT_SMALL}px; font-weight: 600; }}
QLabel#Suggerimento {{ color: {t.testo_dim}; font-size: {M.FONT_HINT}px; }}
QLabel#TitoloCard {{ font-size: {M.FONT_H2}px; font-weight: 700; }}
QLabel#Divisore {{ color: {t.testo_debole}; font-size: {M.FONT_SMALL}px; }}
QFrame#Linea {{ background: {t.bordo}; border: none; max-height: 1px; min-height: 1px; }}
QFrame#CasellaBarcode {{ background: {t.superficie}; border: 1px dashed {t.bordo_forte}; border-radius: {rem(0.5625)}px; }}
QLabel#BoxImmagine {{ background: {t.superficie}; border: 1px dashed {t.bordo_forte}; border-radius: {M.R_MENU}px;
    color: {t.testo_debole}; font-size: {M.FONT_HINT}px; }}
QFrame#Anteprima {{ background: {t.superficie}; border: 1px solid {t.bordo}; border-radius: {M.R_MENU}px; }}
QFrame#Anteprima QLabel {{ color: {t.testo_dim}; font-size: {M.FONT_HINT}px; }}
QFrame#Messaggio {{ background: {t.pericolo_vel}; border: none; border-radius: {M.R_SM}px; }}
QFrame#Messaggio QLabel {{ color: {t.pericolo}; font-size: {M.FONT_HINT}px; font-weight: 600; }}
QFrame#RigaMov {{ background: transparent; border: none; border-bottom: 1px solid {t.bordo}; }}
QLabel#MovIco {{ border-radius: {rem(0.5)}px; background: {t.carta2}; }}
QLabel#MovIco[tono="ok"] {{ background: {t.ok_vel}; }}
QLabel#MovIco[tono="pericolo"] {{ background: {t.pericolo_vel}; }}
QLabel#MovIco[tono="avviso"] {{ background: {t.avviso_vel}; }}
QLabel#MovTitolo {{ font-weight: 600; }}
QLabel#MovSotto {{ color: {t.testo_dim}; font-size: {M.FONT_SMALL}px; }}
QLabel#MovOra {{ color: {t.testo_debole}; font-size: {M.FONT_XS}px; }}
QLabel#MovQta {{ font-weight: 700; }}
QLabel#MovQta[tono="ok"] {{ color: {t.ok}; }}
QLabel#MovQta[tono="pericolo"] {{ color: {t.pericolo}; }}
QLabel#MovQta[tono="avviso"] {{ color: {t.avviso}; }}

/* righe di avviso */
QFrame#RigaAvviso {{ background: {t.carta}; border: 1px solid {t.bordo}; border-radius: {M.R_MENU}px; }}
QFrame#RigaAvviso[gravita="pericolo"] {{ background: {t.pericolo_vel}; border-color: {t.pericolo}; }}
QFrame#RigaAvviso[gravita="avviso"] {{ background: {t.avviso_vel}; border-color: {t.avviso}; }}
QLabel#AvvIco {{ border-radius: {M.KPI_ICO_R}px; background: {t.avviso_vel}; }}
QLabel#AvvIco[gravita="pericolo"] {{ background: {t.pericolo_vel}; }}
QLabel#AvvIco[gravita="avviso"] {{ background: {t.avviso_vel}; }}
QLabel#AvvTitolo {{ font-weight: 700; }}
QLabel#AvvSotto {{ color: {t.testo_dim}; font-size: {M.FONT_HINT}px; }}
QFrame#MeterSfondo {{ background: {t.bordo}; border: none; border-radius: {M.METER_H // 2}px; }}
QFrame#MeterBarra {{ background: {t.avviso}; border: none; border-radius: {M.METER_H // 2}px; }}
QFrame#MeterBarra[gravita="pericolo"] {{ background: {t.pericolo}; }}

/* barra di stato e toast */
QFrame#Statusbar {{ background: {t.carta}; border: none; border-top: 1px solid {t.bordo}; }}
QFrame#Statusbar QLabel {{ color: {t.testo_dim}; font-size: {M.FONT_SMALL}px; }}
QFrame#Toast {{ background: {t.carta}; border: 1px solid {t.bordo_forte}; border-left: {M.TOAST_BORDO}px solid {t.ok};
    border-radius: {M.R_MENU}px; }}
QFrame#Toast[tono="warn"] {{ border-left-color: {t.avviso}; }}
QFrame#Toast[tono="info"] {{ border-left-color: {t.accento}; }}
QFrame#Toast[tono="danger"] {{ border-left-color: {t.pericolo}; }}
QFrame#Toast QLabel {{ font-weight: 600; }}

/* ---------- campi ---------- */
QLineEdit, QComboBox, QSpinBox {{
    background: {t.superficie}; border: 1px solid {t.bordo_campo}; border-radius: {M.R_SM}px;
    padding: {M.CAMPO_PV}px {M.CAMPO_PH}px; selection-background-color: {t.accento_vel}; selection-color: {t.testo};
}}
QLineEdit:focus, QComboBox:focus {{ border-color: {t.accento}; }}
QLineEdit:disabled, QComboBox:disabled {{ color: {t.testo_debole}; }}
QLineEdit[classe="grande"] {{
    font-family: "Cascadia Mono", Consolas, "DejaVu Sans Mono", monospace;
    font-size: {M.BIG_FONT}px; padding: {M.BIG_PV}px {M.BIG_PH}px;
    border-color: {t.accento}; background: {t.accento_vel};
}}
QLineEdit[classe="stepper"] {{
    border-radius: 0; border-left: none; border-right: none; font-weight: 700; background: {t.superficie};
}}
QComboBox::drop-down {{ border: none; width: {rem(1.25)}px; }}
QComboBox::down-arrow {{ image: url("{chev}"); width: {rem(0.875)}px; height: {rem(0.875)}px; }}
QComboBox QAbstractItemView {{
    background: {t.carta}; border: 1px solid {t.bordo_forte}; selection-background-color: {t.accento_vel};
    selection-color: {t.testo}; outline: none;
}}

/* ---------- pulsanti ---------- */
QPushButton {{
    background: {t.carta2}; border: 1px solid {t.bordo_campo}; color: {t.testo}; border-radius: {M.R_SM}px;
    padding: {M.BTN_PV}px {M.BTN_PH}px; font-weight: 600; font-size: {M.FONT_BTN}px;
}}
QPushButton:hover {{ border-color: {t.accento}; }}
QPushButton:disabled {{ color: {t.testo_debole}; border-color: {t.bordo}; }}
QPushButton[dim="sm"] {{ padding: {M.BTN_SM_PV}px {M.BTN_SM_PH}px; font-size: {M.FONT_BTN_SM}px; }}
QPushButton[dim="lg"] {{ padding: {M.BTN_LG_PV}px {M.BTN_LG_PH}px; font-size: {M.FONT_BTN_LG}px; }}
QPushButton[dim="icona"] {{ padding: 0; }}
QPushButton[classe="primario"] {{ background: {t.accento}; border-color: {t.accento}; color: {t.accento_inchiostro}; }}
QPushButton[classe="primario"]:hover {{ background: {schiarisci(t.accento)}; }}
QPushButton[classe="ok"] {{ background: {t.ok}; border-color: {t.ok}; color: {t.ok_inchiostro}; }}
QPushButton[classe="ok"]:hover {{ background: {schiarisci(t.ok)}; }}
QPushButton[classe="pericolo"] {{ background: {t.pericolo}; border-color: {t.pericolo}; color: {t.pericolo_inchiostro}; }}
QPushButton[classe="pericolo"]:hover {{ background: {schiarisci(t.pericolo)}; }}
QPushButton[classe="primario"]:disabled, QPushButton[classe="ok"]:disabled, QPushButton[classe="pericolo"]:disabled {{
    background: {t.carta2}; color: {t.testo_debole}; border-color: {t.bordo};
}}
QPushButton[classe="chip"] {{
    background: {t.carta2}; border: 1px solid {t.bordo_campo}; color: {t.testo_dim}; font-size: {M.FONT_SMALL}px; font-weight: 400;
    border-radius: {M.CHIP_R}px; padding: {M.CHIP_PV}px {M.CHIP_PH}px;
}}
QPushButton[classe="chip"]:hover {{ border-color: {t.accento}; color: {t.testo}; }}
QPushButton[classe="stepper"] {{ background: {t.carta2}; border: 1px solid {t.bordo_campo}; border-radius: 0; padding: 0; }}
QPushButton[classe="stepper"][lato="sx"] {{ border-top-left-radius: {M.R_SM}px; border-bottom-left-radius: {M.R_SM}px; }}
QPushButton[classe="stepper"][lato="dx"] {{ border-top-right-radius: {M.R_SM}px; border-bottom-right-radius: {M.R_SM}px; }}
QPushButton[telefono="on"] {{ color: {t.ok}; border: 1px solid {t.ok}; background: {t.ok_vel}; }}
QPushButton::menu-indicator {{
    image: url("{chev_t}"); width: {rem(0.875)}px; height: {rem(0.875)}px;
    subcontrol-origin: padding; subcontrol-position: right center; right: {M.BTN_PH}px;
}}
QPushButton[menu="true"] {{ padding-right: {M.BTN_PH * 2 + rem(0.875)}px; }}
QPushButton[classe="link"] {{ background: transparent; border: none; color: {t.accento}; padding: 0; font-weight: 600; }}
QPushButton[classe="link"]:hover {{ text-decoration: underline; }}

/* ---------- tabelle ---------- */
QTableWidget {{
    background: transparent; border: none; gridline-color: transparent;
    selection-background-color: {t.accento_vel}; selection-color: {t.testo};
}}
QTableWidget::item {{ padding: {M.TD_PV}px {M.TD_PH}px; border: none; border-bottom: 1px solid {t.bordo}; }}
QTableWidget::item:hover {{ background: {t.accento_vel}; }}
QTableWidget::item:selected {{ background: {t.accento_vel}; color: {t.testo}; }}
QTableWidget QWidget {{ background: transparent; }}
QHeaderView {{ background: {t.carta}; }}
QHeaderView::section {{
    background: {t.carta}; color: {t.testo_dim}; border: none; border-bottom: 1px solid {t.bordo_forte};
    padding: {M.TH_PV}px {M.TH_PH}px; font-weight: 600; font-size: {M.FONT_SMALL}px;
}}
QTableCornerButton::section {{ background: {t.carta}; border: none; }}

QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: {rem(0.5)}px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {t.bordo_forte}; border-radius: {rem(0.25)}px; min-height: {rem(1.25)}px; }}
QScrollBar::handle:vertical:hover {{ background: {t.testo_debole}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: {rem(0.5)}px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {t.bordo_forte}; border-radius: {rem(0.25)}px; min-width: {rem(1.25)}px; }}
QScrollBar::handle:horizontal:hover {{ background: {t.testo_debole}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}

QToolTip {{
    background: {t.carta2}; color: {t.testo}; border: 1px solid {t.bordo_forte};
    padding: {rem(0.25)}px {rem(0.375)}px; font-size: {M.FONT_SMALL}px;
}}
QMenu {{
    background: {t.carta}; border: 1px solid {t.bordo_forte}; border-radius: {M.R_MENU}px;
    padding: {rem(0.375)}px; min-width: {M.MENU_MINW}px;
}}
QMenu::item {{ padding: {rem(0.5625)}px {rem(0.625)}px {rem(0.5625)}px {rem(0.625)}px; border-radius: {rem(0.4375)}px; color: {t.testo}; }}
QMenu::item:selected {{ background: {t.accento_vel}; }}
QMenu::icon {{ padding-left: {rem(0.25)}px; }}
QMenu::separator {{ height: 1px; background: {t.bordo}; margin: {rem(0.3125)}px {rem(0.25)}px; }}
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
