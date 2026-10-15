# Prompt per Pi Agent — Fase 5: allineare la UI di Magazzino Profili al mockup

Ruolo: sviluppatore Python/PySide6 che lavora nel repository **Magazzino Profili**. Obiettivo: la UI desktop reale (`magazzino_profili/ui/`) deve avere lo stesso aspetto di `magazzino-mockup-grande.html` (tema scuro e chiaro). L'app resta Qt Widgets: il mockup NON va incorporato come web view.

## 0. Regole non negoziabili
1. Si modifica solo `magazzino_profili/ui/`, i test UI e UNA riga di `main.py` (`finestra.show()` -> `finestra.showMaximized()`). Vietato toccare `services/`, `domain/`, `db/`, `sicurezza/`, `reports/`, `web/`, `barcode/`, `backup/`.
2. Prima di tutto: `git status`, `git stash list`, annota lo stato. Non usare `git reset --hard` / `git checkout --` su file che non hai creato. Differenze di sole fine riga (CRLF/LF) non sono modifiche.
3. Crea il branch `fase5-ui-mockup`. Un commit per passo, messaggio in italiano.
4. Testi visibili in italiano. Non inventare funzioni: se il mockup mostra qualcosa che il codice non sa fare, NON simularlo (vedi sezione 12).
5. Dopo OGNI passo: `pytest -q` deve restare verde. Non rimuovere né indebolire test; se un test cambia per una modifica voluta del comportamento UI, spiegalo nel report.
6. Non scrivere numeri di misura a mano nei widget: usa solo `M.<nome>` / `rem()` da `ui/tema.py`.
7. Non dichiarare un punto "fatto" senza screenshot (offscreen: `QT_QPA_PLATFORM=offscreen`, `widget.grab().save(...)`). Cosa non verificato = scritto come "non verificato".

## 1. Fatti verificati leggendo il codice e il mockup (perché la UI è "completamente diversa")
- **Scala**: il mockup ha `html{font-size:24px}` e usa rem. Testo base 0,8438rem = 20 px, valore KPI 32 px, pulsanti 20 px, raggio card 18 px. L'app usava 15 px di base, valore KPI 20 px, pulsanti 15 px, finestra 1150x720 => tutto circa 0,7x. Regola: **1 rem = 24 px**.
- **Colori**: i token del tema SCURO in `tema.py` coincidono già col mockup; quelli del tema CHIARO NO (bordo, testo, testo_dim, testo_debole, superficie, carta2, ok, avviso, pericolo). Inoltre i pulsanti pieni hanno testo "inchiostro" scuro (scuro) / bianco (chiaro) e gli sfondi tenui sono veli traslucidi: mancavano.
- **Superfici**: nel mockup i campi hanno sfondo `superficie` (non `carta2`), la tabella non ha righe alternate, le righe sono separate da una linea.
- **Card KPI**: il mockup ha icona a SINISTRA (riquadro 57 px) e valore+etichetta a destra; l'app aveva l'icona sopra.
- **Barra del titolo**: mancano logo, sottotitolo, pulsante tema con icona, menu Report con icone.
- **Schede**: mancano icone nitide, pillola rossa con il numero su Avvisi (l'app scriveva "Avvisi (n)").
- **Inventario**: manca la colonna laterale (495 px) con dettagli del pezzo; le intestazioni devono essere MAIUSCOLE; il profilo ha codice in grassetto + descrizione sotto; stato = pillola con pallino; la colonna Barcode non c'è nel mockup.
- **Carico/Scarico**: titolo "Carico merce"/"Scarico merce", testo guida, campo barcode grande, divisore "oppure inserisci i dati a mano", stepper quantità, chip causale, messaggio d'errore in linea, riquadro anteprima, pulsante grande a tutta larghezza (verde/rosso), card "Ultimi movimenti" con icone.
- **Profili**: tabella a sinistra + a destra form e card "Sezione del profilo" con riquadro tratteggiato alto 300 px; l'app usava una lista.
- **Avvisi**: righe-card con barra di avanzamento, non tabella.
- **Colori pallino (swatch)**: l'app dava ad AN007 `#2f3238` (scuro); nel mockup è `#a9aeb7`.
- Nell'app esistono già le schede-colore (chip) dell'Inventario: il mockup non le ha, ma sono volute dall'utente: **restano**, con aspetto da chip.

## 2. CONTRATTO da non rompere (i test esistenti li usano)
- `TabellaPezzi`: `_tabella` (QTableWidget, 8 colonne con indici invariati: 0 Barcode, 1 Profilo, 2 Colore, 3 Lunghezza, 4 Quantità, 5 Peso, 6 Ubicazione, 7 Stato; testo dello stato in `Qt.UserRole` della colonna 7; `item(r, 2).text()` = nome colore), `_footer.text()` che contiene "N di M referenze", `_tabbar`, `cerca`, `combo_profilo`, `combo_ubicazione`, `combo_stato`, `azzera`, `kpi_pezzi/kpi_profili/kpi_peso/kpi_riordino` con `_valore`, `_etichetta`, `set_valore`, `vai_a_colore`, `aggiorna`. Le tab colore mostrano "Nome (N)" e la prima si chiama "Tutti".
- `CardKPI`: `objectName() == "CardKPI"`, `"border" not in _valore.styleSheet()`, `"background" not in _etichetta.styleSheet()` (quindi stili SOLO dal QSS globale, mai inline).
- `FinestraPrincipale`: `_tab` (nomi: Inventario, Carico, Scarico, Profili, Avvisi; per l'operatore solo Carico e Scarico; `tabText(4).startswith("Avvisi")`), `scheda_inventario/carico/scarico/profilo/avvisi`, `puls_report`, `puls_tema`, `_azione_pdf`, `_azione_excel`, `_barra_stato`.
- `SchedaCarico`: `barcode`, `codice`, `colore`, `lunghezza`, `quantita`, `ubicazione`, `causale`, `salva`, `salva_carico()`, `cambiato`, `movimenti.toPlainText()` deve contenere "CARICATO", "SCARICATO", "+ 10", "− 3".
- `SchedaScarico`: `barcode`, `quantita`, `causale`, `salva`, `salva_scarico()`, `anteprima.text()` deve contenere "giacenza: 12 pz" e l'ubicazione ("Vassoio 1") oppure "Nessun pezzo"; conferma di scarico totale via `chiedi_conferma`; `cambiato`.
- `SchedaProfilo`, `SchedaAvvisi` (`vai_a_colore` Signal(int), `aggiorna`): prima di modificarle esegui `grep -rn "<nome scheda>" tests/` e conserva ogni attributo che i test toccano.
- Se un test usa `QMessageBox.warning` per un errore di validazione che ora diventa messaggio in linea, aggiorna quel test e dichiaralo.

## 3. Passo 0 — Baseline
`pytest -q`, annota superati/falliti/saltati. Se `MAGAZZINO_TEST_DB_URL` non è impostata i test PostgreSQL sono saltati: scrivilo. Poi crea `fase5/` e salva screenshot "prima" di ogni scheda (scuro+chiaro) con `screenshot_ui.py` esteso (finestra 1700x1000).

## 4. Passo 1 — nuovo file `ui/icone.py` (CODICE COLLAUDATO, copia così com'è)
Sono gli stessi SVG del mockup disegnati con `QSvgRenderer` (QtSvg è incluso in PySide6). Se il file `.spec` di PyInstaller esiste, aggiungi `QtSvg` agli hidden imports e controlla che l'eseguibile mostri le icone. Il vecchio `icona_linea()` in `componenti.py` resta come wrapper: `return icona_svg(nome, colore_hx, d or px(20))` (gli alias "arrow-up/arrow-down/layout" sono gestiti).

```python
"""Icone a tratto: gli STESSI SVG del mockup (viewBox 24x24, tratto 2, estremi arrotondati).

Si disegnano con ``QSvgRenderer`` (modulo QtSvg, incluso in PySide6): nessun file esterno.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

# Contenuto interno dell'<svg> per ogni icona (copiato dal mockup, oggetto JS ``ICONS``).
ICONE: dict[str, str] = {
    'grid': '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/>',
    'plus': '<path d="M12 5v14M5 12h14"/>',
    'minus': '<path d="M5 12h14"/>',
    'up': '<path d="M12 19V5m0 0-6 6m6-6 6 6"/>',
    'down': '<path d="M12 5v14m0 0-6-6m6 6 6-6"/>',
    'profili': '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M4 9h16M9 9v11"/>',
    'alert': '<path d="M12 9v4M12 17h.01"/><path d="M10.3 3.9 2.7 17a2 2 0 0 0 1.7 3h15.2a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/>',
    'search': '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
    'download': '<path d="M12 3v12m0 0 4-4m-4 4-4-4"/><path d="M4 21h16"/>',
    'upload': '<path d="M12 15V3m0 0L8 7m4-4 4 4"/><path d="M4 21h16"/>',
    'barcode': '<path d="M4 6v12M7 6v12M11 6v12M14 6v12M17 6v12M20 6v12"/>',
    'sun': '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    'moon': '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
    'undo': '<path d="M3 7v6h6"/><path d="M3 13a9 9 0 1 0 3-7.7L3 8"/>',
    'x': '<path d="M18 6 6 18M6 6l12 12"/>',
    'check': '<path d="m5 12 5 5 9-9"/>',
    'image': '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-5-5L5 21"/>',
    'refresh': '<path d="M3 12a9 9 0 0 1 15.5-6.2L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15.5 6.2L3 16"/><path d="M3 21v-5h5"/>',
    'file': '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/>',
    'box': '<path d="M21 8 12 3 3 8v8l9 5 9-5z"/><path d="m3 8 9 5 9-5M12 13v8"/>',
    'layers': '<path d="m12 3 9 5-9 5-9-5z"/><path d="m3 13 9 5 9-5"/>',
    'weight': '<path d="M6.5 8h11l2 12h-15z"/><circle cx="12" cy="5" r="2"/>',
    'tag': '<path d="M20 12 12 20a2 2 0 0 1-2.8 0L3 13.8V4h9.8L20 11.2a1 1 0 0 1 0 .8z"/><circle cx="7.5" cy="8.5" r="1"/>',
    'printer': '<path d="M6 9V3h12v6M6 18H4v-7h16v7h-2"/><rect x="6" y="14" width="12" height="7"/>',
    'chev': '<path d="m6 9 6 6 6-6"/>',
    'info': '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
    'list': '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
    'phone': '<rect x="7" y="2" width="10" height="20" rx="2"/><path d="M11 18h2"/>',
}

# Nomi vecchi usati dal codice esistente -> nomi del mockup.
_ALIAS = {"arrow-up": "up", "arrow-down": "down", "layout": "profili"}


def _dpr() -> float:
    schermo = QGuiApplication.primaryScreen()
    return float(schermo.devicePixelRatio()) if schermo is not None else 1.0


def svg_icona(nome: str, colore_hx: str, spessore: float = 2.0) -> bytes:
    nome = _ALIAS.get(nome, nome)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{colore_hx}" stroke-width="{spessore}" stroke-linecap="round" '
        f'stroke-linejoin="round">{ICONE[nome]}</svg>'
    ).encode("utf-8")


def pixmap_icona(nome: str, colore_hx: str, d: int) -> QPixmap:
    """Pixmap nitido (tiene conto del devicePixelRatio) di lato ``d`` pixel logici."""
    dpr = _dpr()
    pm = QPixmap(int(round(d * dpr)), int(round(d * dpr)))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(svg_icona(nome, colore_hx)).render(p, QRectF(0, 0, d, d))
    p.end()
    return pm


def icona_svg(nome: str, colore_hx: str, d: int) -> QIcon:
    return QIcon(pixmap_icona(nome, colore_hx, d))


def ic_px(s: float) -> int:
    """Dimensione icona del mockup: ``ic(nome, s)`` = s/16 rem = s*1.5 px a root 24px."""
    return max(1, int(round(s * 1.5)))


def percorso_icona_png(nome: str, colore_hx: str, d: int) -> str:
    """Salva l'icona come PNG in una cartella temporanea e ne restituisce il percorso
    (con barre '/'), per le proprietà QSS ``image: url(...)`` (es. freccia dei QComboBox)."""
    cartella = Path(tempfile.gettempdir()) / "magazzino_profili_icone"
    cartella.mkdir(parents=True, exist_ok=True)
    file = cartella / f"{nome}-{colore_hx.lstrip('#')}-{d}.png"
    if not file.exists():
        pixmap_icona(nome, colore_hx, d).save(str(file), "PNG")
    return file.as_posix()
```

## 5. Passo 2 — sostituisci `ui/tema.py` (CODICE COLLAUDATO, copia così com'è)
Mantiene tutta l'API precedente (`px`, `css`, `Tema`, `SCURO`, `CHIARO`, `alterna_tema`, `tema_attivo`, `colore_di_codice`, `colore_sbiadito`, `qss_card`, `qss_badge`) e aggiunge `rem`, `M`, `alfa`, `colore_da_css`, `schiarisci`, nuovi token e il nuovo `qss_globale`. Se la tua copia di `tema.py` ha differenze rispetto a quella da cui parte questo file (controlla con `git diff` dopo la sostituzione) conserva le parti non toccate dal mockup.

Dopo la sostituzione fai SUBITO queste due modifiche a mano nello stesso file:
1. In `_NOTI` imposta come nel mockup: `"AN007": "#a9aeb7"`, `"RAL9010": "#f2f1ea"`, `"RAL7016": "#383e42"`, `"RAL9005": "#0e0e10"`, `"RAL8014": "#4a3728"` e lascia le altre voci esistenti; il colore di ripiego del mockup è `hsl((somma dei codici carattere*7) % 360, 18%, 55%)`: in `colore_di_codice` sostituisci il calcolo dell'hash con `h = sum(ord(c) * 7 for c in t) % 360`.
2. Rimuovi eventuali usi di `accento_sfondo` nei file `ui/` (resta nel dataclass): usa `accento_vel`.

```python
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
    testo="#eceef2",
    testo_dim="#9ba3b1",
    testo_debole="#6f7787",
    accento="#5b8dff",
    accento_sfondo="#243350",
    ok="#3ccb82",
    avviso="#f0b04a",
    pericolo="#f0605a",
    accento_inchiostro="#0b1633",
    ok_inchiostro="#06261a",
    pericolo_inchiostro="#2c0a08",
    accento_vel="rgba(91, 141, 255, 36)",
    ok_vel="rgba(60, 203, 130, 36)",
    avviso_vel="rgba(240, 176, 74, 38)",
    pericolo_vel="rgba(240, 96, 90, 36)",
)

CHIARO = Tema(
    sfondo="#e9ecf2",
    superficie="#f3f5f9",
    carta="#ffffff",
    carta2="#f1f3f8",
    bordo="#dde1ea",
    bordo_forte="#c6ccda",
    testo="#161a22",
    testo_dim="#556073",
    testo_debole="#7b8698",
    accento="#2b62e0",
    accento_sfondo="#e3ebfc",
    ok="#168a53",
    avviso="#9c6200",
    pericolo="#c43832",
    accento_inchiostro="#ffffff",
    ok_inchiostro="#ffffff",
    pericolo_inchiostro="#ffffff",
    accento_vel="rgba(43, 98, 224, 26)",
    ok_vel="rgba(22, 138, 83, 28)",
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

def colore_da_css(valore: str) -> QColor:
    """QColor da ``#rrggbb`` oppure da ``rgba(r, g, b, A)`` (A intero 0-255)."""
    if valore.startswith("rgba"):
        r, g, b, a = (int(x) for x in valore[valore.index("(") + 1 : valore.index(")")].split(","))
        return QColor(r, g, b, a)
    return QColor(valore)


def schiarisci(hx: str, percento: int = 108) -> str:
    """Equivalente di ``filter: brightness(1.08)`` per l'hover dei pulsanti pieni."""
    return QColor(hx).lighter(percento).name()


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
    background: {t.pericolo}; color: #ffffff; font-size: {M.FONT_CONTA}px; font-weight: 700;
    border-radius: {M.CONTA // 2}px; min-width: {M.CONTA}px; max-height: {M.CONTA}px; min-height: {M.CONTA}px;
    padding: 0 {rem(0.375)}px;
}}

/* ---------- schede colore (chip) dell'Inventario ---------- */
QTabBar#TabColori::tab {{
    background: {t.carta2}; color: {t.testo_dim}; border: 1px solid {t.bordo};
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
QLabel#AvvIco {{ border-radius: {M.KPI_ICO_R}px; background: {t.avviso_vel}; }}
QLabel#AvvIco[gravita="pericolo"] {{ background: {t.pericolo_vel}; }}
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
    background: {t.superficie}; border: 1px solid {t.bordo}; border-radius: {M.R_SM}px;
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
    background: {t.carta2}; border: 1px solid {t.bordo}; color: {t.testo}; border-radius: {M.R_SM}px;
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
    background: {t.carta2}; border: 1px solid {t.bordo}; color: {t.testo_dim}; font-size: {M.FONT_SMALL}px; font-weight: 400;
    border-radius: {M.CHIP_R}px; padding: {M.CHIP_PV}px {M.CHIP_PH}px;
}}
QPushButton[classe="chip"]:hover {{ border-color: {t.accento}; color: {t.testo}; }}
QPushButton[classe="stepper"] {{ background: {t.carta2}; border: 1px solid {t.bordo}; border-radius: 0; padding: 0; }}
QPushButton[classe="stepper"][lato="sx"] {{ border-top-left-radius: {M.R_SM}px; border-bottom-left-radius: {M.R_SM}px; }}
QPushButton[classe="stepper"][lato="dx"] {{ border-top-right-radius: {M.R_SM}px; border-bottom-right-radius: {M.R_SM}px; }}
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

QScrollArea {{ background: transparent; border: none; }}
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
```

## 6. Passo 3 — `ui/componenti.py`: AGGIUNGI queste classi (CODICE COLLAUDATO)
Tieni le funzioni già presenti (`icona_colore`, `icona_tessera`, `icona_linea` come wrapper) ma elimina la vecchia `CardKPI` (verticale) e la vecchia `pillola` QLabel: le sostituiscono quelle qui sotto (stessi nomi). Cambia la vecchia `_rgba` in modo che l'alfa sia INTERO 0-255 (usa `tema.alfa`).

```python
"""Componenti riutilizzabili dell'interfaccia (stile del mockup)."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QIntValidator, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .icone import ic_px, icona_svg, pixmap_icona
from .tema import M, colore_da_css, rem, tema_attivo


# ---------------------------------------------------------------- pulsanti
def bottone(
    testo: str,
    classe: str | None = None,
    dim: str | None = None,
    icona: str | None = None,
    parent: QWidget | None = None,
) -> QPushButton:
    """Pulsante nello stile del mockup.

    ``classe``: None (ghost) | "primario" | "ok" | "pericolo" | "chip" | "link"
    ``dim``: None | "sm" | "lg" | "icona";  ``icona``: nome in ``icone.ICONE``.
    L'icona prende il colore del testo del pulsante (come ``currentColor`` nel mockup).
    """
    t = tema_attivo()
    b = QPushButton(testo, parent)
    if classe:
        b.setProperty("classe", classe)
    if dim:
        b.setProperty("dim", dim)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if icona:
        colore = {
            "primario": t.accento_inchiostro,
            "ok": t.ok_inchiostro,
            "pericolo": t.pericolo_inchiostro,
        }.get(classe or "", t.testo)
        s = {"sm": 13, "lg": 16}.get(dim or "", 16)  # misure ic(...) del mockup
        b.setIcon(icona_svg(icona, colore, ic_px(s)))
        b.setIconSize(QSize(ic_px(s), ic_px(s)))
    return b


def chip(testo: str, campo: QLineEdit, parent: QWidget | None = None) -> QPushButton:
    """Suggerimento rapido: un clic scrive ``testo`` nel ``campo``."""
    b = bottone(testo, classe="chip", parent=parent)
    b.clicked.connect(lambda: (campo.setText(testo), campo.setFocus()))
    return b


# ---------------------------------------------------------------- pillola di stato
class Pillola(QLabel):
    """Badge a pillola con pallino: ``ok`` | ``avviso`` | ``pericolo`` | ``neutro``."""

    def __init__(self, testo: str, variante: str = "neutro", parent: QWidget | None = None) -> None:
        super().__init__(testo, parent)
        self.setObjectName("Pillola")
        self._variante = variante
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        f = QFont(self.font())
        f.setPixelSize(M.FONT_XS)
        f.setWeight(QFont.Weight.DemiBold)
        self.setFont(f)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def _colori(self) -> tuple[QColor, QColor]:
        t = tema_attivo()
        primo, velo = {
            "ok": (t.ok, t.ok_vel),
            "avviso": (t.avviso, t.avviso_vel),
            "pericolo": (t.pericolo, t.pericolo_vel),
        }.get(self._variante, (t.testo_dim, t.carta2))
        return QColor(primo), colore_da_css(velo)

    def sizeHint(self) -> QSize:
        fm = QFontMetrics(self.font())
        larghezza = M.PILL_PH + M.PILL_PUNTO + rem(0.375) + fm.horizontalAdvance(self.text()) + M.PILL_PH
        return QSize(larghezza, fm.height() + 2 * M.PILL_PV)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def paintEvent(self, _evento) -> None:
        primo, velo = self._colori()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(velo)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        d = float(M.PILL_PUNTO)
        p.setBrush(primo)
        p.drawEllipse(QPointF(M.PILL_PH + d / 2, r.height() / 2), d / 2, d / 2)
        p.setPen(primo)
        p.setFont(self.font())
        testo = QRectF(M.PILL_PH + d + rem(0.375), 0, r.width(), r.height())
        p.drawText(testo, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), self.text())
        p.end()


def pillola(testo: str, variante: str = "neutro") -> Pillola:
    """Compatibilità con il codice esistente."""
    return Pillola(testo, variante)


# ---------------------------------------------------------------- card KPI (icona a sinistra)
class CardKPI(QFrame):
    """Tessera riepilogo del mockup: riquadro icona a sinistra, valore e etichetta a destra.

    ``tono``: "accento" (default) | "bad" (rosso) | "good" (verde). Se la tessera è cliccabile
    emette ``cliccata``.
    """

    cliccata = Signal()

    def __init__(
        self,
        icona: str,
        valore: str,
        etichetta: str,
        tono: str = "accento",
        cliccabile: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("CardKPI")  # il test esistente lo richiede
        self.setProperty("cliccabile", "true" if cliccabile else "false")
        if cliccabile:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._icona_nome = icona
        riga = QHBoxLayout(self)
        riga.setContentsMargins(M.KPI_PH, M.KPI_PV, M.KPI_PH, M.KPI_PV)
        riga.setSpacing(M.KPI_GAP)

        self._ico = QLabel(self)
        self._ico.setObjectName("KpiIco")
        self._ico.setFixedSize(M.KPI_ICO, M.KPI_ICO)
        self._ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        riga.addWidget(self._ico, 0, Qt.AlignmentFlag.AlignVCenter)

        colonna = QVBoxLayout()
        colonna.setContentsMargins(0, 0, 0, 0)
        colonna.setSpacing(2)
        self._valore = QLabel(valore, self)
        self._valore.setObjectName("KpiValore")
        self._etichetta = QLabel(etichetta, self)
        self._etichetta.setObjectName("KpiEtichetta")
        colonna.addWidget(self._valore)
        colonna.addWidget(self._etichetta)
        riga.addLayout(colonna, 1)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.set_tono(tono)

    def set_tono(self, tono: str, icona: str | None = None) -> None:
        t = tema_attivo()
        if icona:
            self._icona_nome = icona
        colore = {"bad": t.pericolo, "good": t.ok}.get(tono, t.accento)
        self._ico.setProperty("tono", tono)
        self._ico.style().unpolish(self._ico)
        self._ico.style().polish(self._ico)
        self._ico.setPixmap(pixmap_icona(self._icona_nome, colore, M.KPI_ICO_SVG))

    def set_valore(self, valore: str) -> None:
        self._valore.setText(valore)

    def set_etichetta(self, etichetta: str) -> None:
        self._etichetta.setText(etichetta)

    def mouseReleaseEvent(self, evento) -> None:
        if self.property("cliccabile") == "true" and evento.button() == Qt.MouseButton.LeftButton:
            self.cliccata.emit()
        super().mouseReleaseEvent(evento)


# ---------------------------------------------------------------- stepper  [-] [ 1 ] [+]
class Stepper(QWidget):
    """Campo numerico con pulsanti − e +. ``campo`` è un QLineEdit con QIntValidator."""

    def __init__(self, valore: int = 1, minimo: int = 1, massimo: int = 99_999_999, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        t = tema_attivo()
        self._minimo, self._massimo = minimo, massimo
        riga = QHBoxLayout(self)
        riga.setContentsMargins(0, 0, 0, 0)
        riga.setSpacing(0)
        self.meno = QPushButton(self)
        self.piu = QPushButton(self)
        for b, nome, lato in ((self.meno, "minus", "sx"), (self.piu, "plus", "dx")):
            b.setProperty("classe", "stepper")
            b.setProperty("lato", lato)
            b.setFixedWidth(M.STEP_BTN)
            b.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)  # alto quanto il campo
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setIcon(icona_svg(nome, t.testo, ic_px(14)))
            b.setIconSize(QSize(ic_px(14), ic_px(14)))
        self.campo = QLineEdit(str(valore), self)
        self.campo.setProperty("classe", "stepper")
        self.campo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.campo.setValidator(QIntValidator(minimo, massimo, self))
        riga.addWidget(self.meno)
        riga.addWidget(self.campo, 1)
        riga.addWidget(self.piu)
        self.meno.clicked.connect(lambda: self._passo(-1))
        self.piu.clicked.connect(lambda: self._passo(+1))

    def _passo(self, delta: int) -> None:
        try:
            v = int(self.campo.text() or 0)
        except ValueError:
            v = self._minimo
        self.campo.setText(str(max(self._minimo, min(self._massimo, v + delta))))


# ---------------------------------------------------------------- messaggio d'errore in linea
class MessaggioErrore(QFrame):
    """Barra rossa con icona di avviso; nascosta finché non c'è un testo."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Messaggio")
        riga = QHBoxLayout(self)
        riga.setContentsMargins(M.MSG_PH, M.MSG_PV, M.MSG_PH, M.MSG_PV)
        riga.setSpacing(rem(0.5))
        self._ico = QLabel(self)
        self._ico.setPixmap(pixmap_icona("alert", tema_attivo().pericolo, ic_px(15)))
        self._testo = QLabel(self)
        self._testo.setWordWrap(True)
        riga.addWidget(self._ico, 0, Qt.AlignmentFlag.AlignTop)
        riga.addWidget(self._testo, 1)
        self.hide()

    def mostra(self, testo: str) -> None:
        self._testo.setText(testo)
        self.setVisible(bool(testo))

    def text(self) -> str:
        return self._testo.text()


# ---------------------------------------------------------------- riquadro anteprima
class Anteprima(QFrame):
    """Riquadro grigio con testo ricco (anteprima giacenza). API come una QLabel: setText/text/clear."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Anteprima")
        riga = QVBoxLayout(self)
        riga.setContentsMargins(M.ANT_PH, M.ANT_PV, M.ANT_PH, M.ANT_PV)
        self._label = QLabel(self)
        self._label.setTextFormat(Qt.TextFormat.RichText)
        self._label.setWordWrap(True)
        riga.addWidget(self._label)

    def setText(self, html: str) -> None:
        self._label.setText(html)

    def text(self) -> str:
        return self._label.text()

    def clear(self) -> None:
        self._label.clear()


# ---------------------------------------------------------------- divisore con testo
def divisore(testo: str, parent: QWidget | None = None) -> QWidget:
    w = QWidget(parent)
    riga = QHBoxLayout(w)
    riga.setContentsMargins(0, 2, 0, M.CAMPO_MB)
    riga.setSpacing(rem(0.625))
    for i in range(2):
        linea = QFrame(w)
        linea.setObjectName("Linea")
        linea.setFixedHeight(1)
        if i == 0:
            riga.addWidget(linea, 1)
            lab = QLabel(testo, w)
            lab.setObjectName("Divisore")
            riga.addWidget(lab)
        else:
            riga.addWidget(linea, 1)
    return w


def campo_con_etichetta(testo: str, widget: QWidget, parent: QWidget | None = None) -> QWidget:
    """Etichetta sopra il campo (``.field`` del mockup): gap 9 px, spazio sotto 21 px."""
    c = QWidget(parent)
    v = QVBoxLayout(c)
    v.setContentsMargins(0, 0, 0, M.CAMPO_MB)
    v.setSpacing(M.CAMPO_GAP)
    lab = QLabel(testo, c)
    lab.setObjectName("Etichetta")
    lab.setWordWrap(True)
    v.addWidget(lab)
    v.addWidget(widget)
    return c
```

Il file contiene: `bottone()`, `chip()`, `Pillola`/`pillola()`, `CardKPI` (orizzontale, parametro `tono` = "accento"|"bad"|"good", `cliccabile`, segnale `cliccata`), `Stepper` (`.campo` è un QLineEdit con QIntValidator), `MessaggioErrore` (`.mostra(testo)`), `Anteprima` (API `setText/text/clear`), `divisore()`, `campo_con_etichetta()`.

Aggiungi anche in `componenti.py` questi due widget (schema, da collaudare con screenshot; segui i nomi QSS già presenti nel foglio di stile):

**`ListaMovimenti(QWidget)`**: un `QVBoxLayout` con una riga per movimento: `QFrame#RigaMov` con HBox [`QLabel#MovIco` 42x42 con property `tono` ("ok" per CARICO, "pericolo" per SCARICO, "avviso" per RETTIFICA) e icona `up`/`down`/`refresh` 21 px nel colore del tono] + VBox [`QLabel#MovTitolo` "AB12 · AN007 · 6.000 mm", `QLabel#MovSotto` "CARICATO · causale"] + VBox a destra [`QLabel#MovQta` "+ 10" / "− 3" con property `tono`, `QLabel#MovOra` "13/10 14:32"]. Metodo `imposta(movimenti)`; metodo di compatibilità `toPlainText()` che restituisce le righe di testo (serve al test esistente: deve contenere "CARICATO", "SCARICATO", "+ 10", "− 3"). Dopo aver cambiato una property dinamica fai `style().unpolish(w); style().polish(w)`. Se non ci sono movimenti mostra "Nessun movimento" in `#Debole`.

**`Toast(QFrame#Toast)`**: icona + testo + pulsante "x"; property `tono` ("ok"|"warn"|"info"|"danger"); si posiziona in basso a destra della finestra a `M.TOAST_DX` dal bordo destro e `M.TOAST_BASSO` dal fondo, larghezza massima `M.TOAST_MAXW`, si chiude da solo dopo 4500 ms (QTimer), massimo 3 visibili. NON aggiungere il pulsante "Annulla" del mockup (annullare un movimento è logica di business, vedi sezione 12).

## 7. Passo 4 — `finestra_principale.py`
- `self.setObjectName("Finestra")`; layout radice con margini 0 e spaziatura 0: barra del titolo, `QTabWidget`, barra di stato. `self.resize(...)` con minimo 1280x760; in `main.py` usa `finestra.showMaximized()`.
- **Barra del titolo** (come nel mockup): `QFrame#Titlebar`, HBox con margini `(M.TITOLO_PH, M.TITOLO_PV, M.TITOLO_PH, M.TITOLO_PV)`, spaziatura `M.GAP_SM`:
  - `QLabel#Logo` fisso `M.LOGO`x`M.LOGO`, centrato, pixmap `pixmap_icona("box", t.accento_inchiostro, ic_px(18))`;
  - VBox con `QLabel#BrandNome` "Magazzino Profili" e `QLabel#BrandSotto` "Giacenza profili · Tre-D Lab" (testo del mockup; sotto-riga in cui ora c'è "utente: … · ruolo": spostala nella barra di stato a sinistra dopo il messaggio, non perderla);
  - stretch; `self.puls_report = bottone("Report", icona="file")` con `setProperty("menu", "true")` e `setMenu(menu)`; le voci del menu hanno icona (`download`/`file`) e testi "Esporta inventario in Excel", "Esporta inventario in PDF" (le azioni `_azione_excel`/`_azione_pdf` restano);
  - `self.puls_tema = bottone("", dim="icona", icona="sun" oppure "moon")` fisso `M.BTN_ICONA` quadrato; l'icona è `moon` nel tema chiaro, `sun` nello scuro (come il mockup: mostra il tema in cui si passa).
- **Schede**: `self._tab.setDocumentMode(True)`, `self._tab.tabBar().setObjectName("TabPrincipali")`, **`self._tab.tabBar().setDrawBase(False)`** (senza questo compare una linea bianca di 1 px sopra le schede), `self._tab.setIconSize(QSize(ic_px(16), ic_px(16)))`. Icone: Inventario `grid`, Carico `up`, Scarico `down`, Profili `profili`, Avvisi `alert`. La scheda selezionata ha l'icona in `t.accento`, le altre in `t.testo_dim`: scrivi `_aggiorna_icone_schede()` e collegala a `currentChanged` (e chiamala alla fine di `_crea_schede`).
- **Badge Avvisi**: il testo della tab resta "Avvisi"; in `_aggiorna_badge_avvisi` crea `QLabel#Conta` con il numero (centrato) e `self._tab.tabBar().setTabButton(i, QTabBar.ButtonPosition.RightSide, lab)`; nascondilo (`setVisible(n > 0)`) quando n = 0. Ricordati che la tab va cercata per `tabText(i) == "Avvisi"`.
- **Barra di stato**: `QFrame#Statusbar`, margini `(M.STATO_PH, M.STATO_PV, M.STATO_PH, M.STATO_PV)`: a sinistra icona `check` (`t.ok`, `ic_px(14)`) + `_barra_stato` (messaggio) + "· utente: X · ruolo"; stretch; pallino verde + "PostgreSQL" (solo dopo che `_aggiorna_stato_riepilogo` ha interrogato il DB con successo; in caso di eccezione pallino rosso e "Database non raggiungibile"); a destra "N referenze · N pezzi". NON mostrare "Backup automatico: 2 ore fa" (nel mockup è testo finto): mostralo solo se esiste già una funzione che restituisce l'ultimo backup reale; altrimenti omettilo e scrivilo nel report.
- **Toast**: metodo `mostra_toast(testo, tono="ok")` che aggiorna anche `_barra_stato`; riposiziona i toast in `resizeEvent`. `SchedaCarico` e `SchedaScarico` ottengono un nuovo `Signal(str, str)` chiamato `messaggio` (testo, tono) emesso dopo il salvataggio riuscito ("Carico registrato — AB12 · AN007 · +10", "Scarico registrato — AB12 · AN007 · −3", tono "warn" se la giacenza diventa 0 con " (esaurito)"); la finestra lo collega a `mostra_toast`. Il segnale `cambiato` resta.
- Le schede in `_crea_schede` sono ricostruite al cambio tema: va bene, ma chiama anche la ricostruzione di barra del titolo e icone (il tema cambia i colori delle icone).

## 8. Passo 5 — Inventario (`tabella_pezzi.py`)
Margini radice `(M.PAG_H, M.PAG_T, M.PAG_H, M.PAG_B)`, spaziatura `M.GAP`. Ordine: riga KPI -> chip colore -> riga [card tabella (stretch 1) | colonna laterale]. **Elimina** la riga con titolo e sottotitolo "Inventario" (il mockup non l'ha).
1. **KPI**: `CardKPI("layers", ..., "Pezzi a magazzino")`, `("tag", ..., "Referenze")`, `("weight", ..., "Peso complessivo")` tutti con tono "accento"; il quarto è cliccabile: se n > 0 `set_tono("bad", "alert")` e etichetta "Da riordinare", altrimenti `set_tono("good", "check")` e etichetta "Scorte ok". `cliccata` -> imposta `combo_stato` su "Da riordinare" (voce già presente). Rimuovi le chiamate a `set_colore_valore` (nel mockup il valore non cambia colore). Il peso: se ≥ 1000 kg mostra "3,4 t", altrimenti "NNN kg" (formato italiano).
2. **Chip colore**: `self._tabbar.setObjectName("TabColori")`, rimuovi lo `setStyleSheet` locale, `setDrawBase(False)`. Lo stile è nel QSS globale (`QTabBar#TabColori`). Se un layout orizzontale di chip `bottone(..., classe="chip")` ha spaziatura 0 imposta `setSpacing(rem(0.375))`.
3. **Card tabella**: `QFrame#Card` con layout verticale margini 0 spaziatura 0 contenente: `QFrame#BarraStrumenti` (margini `M.TOOLBAR_PAD`, spaziatura `M.TOOLBAR_GAP`) con `cerca` (`setMinimumWidth(rem(12.5))`, stretch 3, icona `search` 15 -> `icona_svg("search", t.testo_debole, ic_px(15))`), le combo, e `azzera = bottone("Azzera", icona="refresh")`; poi `_tabella` (stretch 1); poi `_footer` con `setObjectName("Piede")`. Testo del filtro stato come nel mockup: "Stato: tutti" ecc. NON cambiare i valori (`currentData`) delle combo.
4. **Tabella**: `setAlternatingRowColors(False)`, `setShowGrid(False)`, `setMouseTracking(True)`, intestazioni con testo MAIUSCOLO (`s.upper()`; il QSS non ha text-transform), `setColumnHidden(0, True)` (Barcode resta nel contratto ma non è nel mockup; l'ordine visibile diventa Profilo, Colore, Lunghezza, Pezzi, Peso tot., Ubicazione, Stato), colonne numeriche allineate a destra, altezza riga `M.RIGA_INV` = 76 px (due righe di testo + padding: aggiungi `RIGA_INV = 76` a `M` e verifica con screenshot). La colonna Profilo mostra il codice in grassetto e sotto la descrizione in `testo_dim` 18 px: usa un `QStyledItemDelegate` (`DelegatoProfilo`) che legge `Qt.DisplayRole` = codice e `Qt.UserRole + 1` = descrizione (il `text()` dell'item resta il codice + " — " + descrizione solo se i test lo richiedono: controlla). Colonna Colore: pallino 18 px (`colore_di_codice`) + nome. Lunghezza "6.000 mm", Peso "NN,N kg". Colonna Pezzi: testo `t.pericolo` se esaurito/sotto scorta, `t.avviso` se in esaurimento (se esiste), altrimenti normale, in grassetto. Stato: `Pillola`: ok -> "OK", sotto scorta -> **"pericolo"** (rossa, come nel mockup), esaurito -> "pericolo". Non introdurre lo stato "In esaurimento" (non esiste nella logica).
5. **Riga selezionata**: delegate che, per la riga selezionata, disegna una barra verticale `t.accento` larga 3 px sul bordo sinistro della prima colonna visibile (il QSS non può fare `inset box-shadow`).
6. **Colonna laterale** (`QFrame#Card`, larghezza fissa `M.ASIDE_W`, allineata in alto), aggiornata da `itemSelectionChanged` della tabella; senza selezione mostra icona `box`, "Nessun pezzo selezionato", "Scegli una riga per vedere barcode, peso e movimenti." e sotto "Ultimi movimenti" (`consultazione.ultimi_movimenti(sessione, limite=5)` in una `ListaMovimenti`). Con una riga selezionata:
   - sezione 1 (margini `M.LAT_PV`, `M.LAT_PH`, bordo inferiore): codice in `QLabel#LatTitolo`, descrizione sotto in `#Dim`, `Pillola` stato a destra; sotto `QFrame#CasellaBarcode` con l'immagine del barcode (genera il PNG in una cartella temporanea con `barcode.generazione.genera_immagine_barcode(barcode, percorso)` e caricalo in un `QPixmap`; se solleva `ValueError` mostra solo il testo) e il barcode in testo piccolo;
   - sezione "DETTAGLI" (`QLabel#LatSezione`, maiuscolo): coppie etichetta/valore in `QGridLayout` — Colore (pallino + nome), Lunghezza, Giacenza ("N pezzi"), Peso unitario (`consultazione.peso_unitario_kg`), Peso totale, Ubicazione; poi griglia di pulsanti: `bottone("Carica", "ok", icona="up")`, `bottone("Scarica", "pericolo", icona="down")`, `bottone("Stampa etichetta", icona="printer")` a tutta larghezza. "Carica"/"Scarica" emettono un nuovo `Signal(str, str)` `vai_a_scheda` (nome scheda, barcode): la finestra seleziona la scheda e fa `scheda.barcode.setText(barcode)` (il campo si compila da solo con la logica esistente). "Stampa etichetta": `QFileDialog.getSaveFileName` + `barcode.etichette.genera_etichetta_pdf(pezzo, percorso)` con messaggio di errore in caso di `ValueError`; se non riesci a collegarlo senza toccare altro codice, omettilo e scrivilo nel report;
   - sezione "MOVIMENTI DI QUESTO PEZZO": `consultazione.ultimi_movimenti(sessione, limite=4, pezzo_id=...)` in `ListaMovimenti`.
   Recupera il pezzo con `consultazione.pezzo_per_barcode(sessione, barcode)` (il barcode è nella colonna 0, nascosta). Chiudi sempre la sessione (`try/finally`).
7. **Piede** della tabella: testo "N di M referenze" invariato (contratto); se la lista è vuota con filtri attivi mostra al centro della tabella "Nessun risultato — Prova a modificare la ricerca o i filtri." con il pulsante "Azzera filtri".

## 9. Passo 6 — Carico e Scarico (`scheda_carico.py`, `scheda_scarico.py`)
Layout radice: margini pagina come sopra, `QHBoxLayout`, spaziatura `M.GAP`; a sinistra `QFrame#Card` larga `M.SPLIT_SX` con margini `M.CARD_PAD`; a destra `QFrame#Card` (stesso margine) con titolo "Ultimi movimenti" (`QLabel#TitoloCard`) e `ListaMovimenti` (nel `QScrollArea`). La colonna destra occupa lo spazio restante.
Struttura della card sinistra, nell'ordine: titolo (`#TitoloCard`: "Carico merce" / "Scarico merce"); testo guida (`#Suggerimento`, `setWordWrap`): per il carico "Scansiona il barcode di un pezzo già presente: i dati si compilano da soli. Scansionalo più volte per aumentare la quantità, poi premi Invio a campo vuoto per salvare. Per un pezzo nuovo inserisci i dati a mano." — attenzione: questo comportamento (scansioni ripetute = +1, Invio a campo vuoto) NON è nel codice attuale: usa invece il testo vero: "Scansiona il barcode di un pezzo già presente: i dati si compilano da soli. Per un pezzo nuovo inserisci codice, colore e lunghezza a mano." e per lo scarico "Scansiona il barcode (il lettore invia Invio in automatico) oppure digitalo."; `campo_con_etichetta("Barcode", self.barcode)` con `self.barcode.setProperty("classe", "grande")`, `setMinimumHeight(rem(3.0))` (obbligatorio: senza il testo viene tagliato); solo carico: `divisore("oppure inserisci i dati a mano")`; righe a due colonne (QHBoxLayout spaziatura `M.GAP_SM`) con `campo_con_etichetta`: Codice profilo | Colore; Lunghezza (mm) | Quantità (con `Stepper`: `self.quantita = stepper.campo` così `quantita.text()`/`setText` continuano a funzionare); Ubicazione | Causale (carico); Quantità | Causale (scarico). Etichette ESATTE del mockup tranne dove sono regole di business: nello scarico lascia "Causale (obbligatoria)". Sotto la causale una riga di `chip` (carico: "Arrivo fornitore", "Reso", "Rettifica inventario"; scarico: "Lavorazione", "Vendita", "Scarto") con spaziatura `rem(0.375)`. Poi `MessaggioErrore`, `Anteprima`, e in fondo `bottone("Salva carico", "ok", "lg", "plus")` / `bottone("Scarica", "pericolo", "lg", "down")` a tutta larghezza (assegna sempre a `self.salva`). Stretch prima del pulsante.
- **Errori di validazione** (campi mancanti, quantità non valida, ecc.): mostrali in `MessaggioErrore` invece di `QMessageBox.warning`; mantieni `mostra_errore`/`chiedi_conferma` per le eccezioni e per lo scarico totale. Dichiara nel report i test aggiornati.
- **Anteprima scarico**: HTML ricco con il codice grande (`M.FONT_LAT_TITOLO`+, grassetto), descrizione, pallino colore + colore · lunghezza, ubicazione, e la riga "giacenza: N pz" (**deve restare** perché il test la cerca); aggiungi sotto "Giacenza dopo lo scarico" e il flusso "N → N−q pezzi" in grassetto `M.FONT_FLUSSO`, rosso se negativo. Anteprima carico: quando codice e colore sono compilati mostra "Giacenza di <b>AB12 · AN007 · 6.000 mm</b>" e "N → N+q pezzi"; altrimenti "Compila profilo e colore per vedere l'anteprima della giacenza." (usa le funzioni di lettura già esistenti, es. `consultazione.pezzo_per_combinazione`; non scrivere query nuove).
- Scarico: la tabella "Pezzi in giacenza" oggi a destra: leggi `scheda_scarico.py` e verifica se un clic su una riga riempie il barcode. Se SÌ, mantienila in una seconda card sotto "Ultimi movimenti"; se NO, sostituiscila con "Ultimi movimenti" come nel mockup. Scrivi la decisione nel report.
- Pulsante "Collega telefono": NON implementarlo (vedi sezione 12).

## 10. Passo 7 — Profili (`scheda_profilo.py`)
Layout: sinistra `QFrame#Card` (stretch 1) con `QFrame#BarraStrumenti` [campo di ricerca "Cerca profilo…" + `bottone("Nuovo profilo", "primario", icona="plus")`] e una `QTableWidget` con colonne CODICE, DESCRIZIONE, PESO KG/M, LUNG. STD, PEZZI (numeri a destra: peso con virgola e 4 decimali, "6.000 mm", pezzi = giacenza totale da `consultazione.lista_profili_con_giacenza`); destra, larga `M.PROF_DX`, due card in colonna: form "Anagrafica — CODICE" (o "Nuovo profilo") con `campo_con_etichetta` (Codice, Descrizione, [Peso kg/m | Lunghezza std mm]) + `MessaggioErrore` + `bottone("Salva profilo", "primario", "lg", "check")`, e card "Sezione del profilo" con `QLabel#BoxImmagine` alto `M.IMG_BOX_H` (testo "Nessuna immagine caricata", icona `image` 34 -> `ic_px(34)`), sotto `bottone("Importa immagine (PNG)", icona="upload")` e, se c'è un'immagine, un pulsante `x` per rimuoverla. Conserva i nomi `codice`, `descrizione`, `peso`, `lunghezza`, `salva`, `_anteprima` (ora è il `BoxImmagine`), `_importa_immagine`, `_rimuovi_immagine`, `_nuovo`, `salva_profilo`. Se `_elenco` (QListWidget) è usato dai test, sostituisci `QListWidget` con la tabella e adegua SOLO i test che accedono a `_elenco`, mantenendo `_su_selezione` e la semantica della selezione; dichiaralo.

## 11. Passo 8 — Avvisi (`avvisi.py`)
Intestazione: titolo "Avvisi scorte" (`#TitoloCard`) e sottotitolo `#Dim` con il testo attuale del contatore; pulsante "Aggiorna" = `bottone("Aggiorna", icona="refresh")` a destra. Sotto, in `QScrollArea` (widget resizable, margine 0) una colonna di righe `QFrame#RigaAvviso` con property `gravita` ("pericolo" per esaurito, "avviso" per sotto scorta — attenzione: nel mockup anche "Sotto scorta" è rosso: usa "pericolo" per entrambi e "avviso" solo se in futuro esisterà "in esaurimento"): HBox con margini `(M.AVV_PH, M.AVV_PV, M.AVV_PH, M.AVV_PV)`, spaziatura `M.GAP`: `QLabel#AvvIco` `M.AVV_ICO` quadrato con icona `alert` rossa; VBox [`QLabel#AvvTitolo` "AB12 · AN007 · 6.000 mm — Sotto scorta", `QLabel#AvvSotto` "descrizione · ubicazione · N pezzi rimasti" (se 0: "nessun pezzo disponibile"), barra di avanzamento: `QFrame#MeterSfondo` alto `M.METER_H`, larghezza massima `M.METER_MAXW`, con dentro `QFrame#MeterBarra` (property `gravita`) larga `min(1, giacenza / scorta_minima)` x larghezza (se `scorta_minima` è vuota o 0: barra vuota); calcola la larghezza in `resizeEvent`/`setFixedWidth` dopo il layout]; a destra `bottone("Dettagli", dim="sm")` (collegato a `vai_a_colore` come ora) e `bottone("Carica", "ok", "sm", "up")` (vai alla scheda Carico con il barcode compilato, stesso meccanismo di `vai_a_scheda`: aggiungi il segnale a `SchedaAvvisi`). Senza avvisi: card con icona `check` verde, "Nessun avviso", "Tutte le referenze sono sopra la soglia di scorta.". Il widget "Soglia sotto scorta" del mockup NON esiste nell'app (la scorta minima è per pezzo, nella logica di business): non crearlo.

## 12. Fuori ambito (NON fare; elenca nel report come "non incluso")
Pulsante e finestra "Collega telefono" (richiede il server `web/`); "Annulla" nei toast (annullare un movimento è logica); ordinamento per colonna con frecce ▲▼ nelle intestazioni; stato "In esaurimento" e soglia modificabile; "Backup automatico: 2 ore fa" finto; importazione CSV, esportazione CSV e foglio etichette nel menu Report (aggiungile solo se esiste già la funzione e il collegamento richiede meno di 15 righe: altrimenti elencale); ombre (`box-shadow`), transizioni, animazione "shake", `letter-spacing` e `text-transform` (il QSS non li supporta: maiuscolo si fa nel testo).

## 13. Trappole Qt già verificate (non ripeterle)
- **`border-radius` maggiore di metà altezza viene IGNORATO** (il widget torna rettangolare). Per le pillole/chip usa `M.CHIP_R = 16`, mai valori tipo 999.
- Una linea bianca di 1 px sopra le schede compare se non chiami `tabBar().setDrawBase(False)`.
- I pulsanti dello stepper restano più bassi del campo se non hanno `QSizePolicy.Expanding` in verticale (già nel codice).
- Il campo barcode grande taglia il testo senza `setMinimumHeight(rem(3.0))`.
- QSS: alfa dei colori solo INTERO 0-255 (`rgba(91, 141, 255, 36)`); property dinamiche (`classe`, `dim`, `tono`, `gravita`) vanno impostate PRIMA del primo `show()`, oppure fai `unpolish/polish`.
- `font-weight` in QSS: usa 400/600/700 (650 non esiste).
- Nessuno stile inline su `CardKPI._valore/_etichetta` (test).
- Il QSS globale NON imposta più `QWidget { background }`: ogni finestra/dialogo di primo livello deve avere `objectName("Finestra")` oppure essere un `QDialog` (che ha lo sfondo nel QSS); se compare uno sfondo nero/bianco su un widget nuovo, è questo.

## 14. Passo finale — verifica e report
1. Screenshot "dopo" di tutte le schede in tema scuro e chiaro a 1700x1000 in `fase5/`, e confronto affiancato con il mockup (se hai un browser headless; altrimenti scrivi "mockup non renderizzato").
2. Per ogni area (barra del titolo, schede, KPI, inventario+laterale, carico, scarico, profili, avvisi, barra di stato, toast) tabella: Area | Mockup | App dopo | Stato (corrisponde / parziale / non possibile in Qt, con motivo).
3. Test: aggiungi `tests/test_ui_fase5.py` con: i token del tema (`SCURO`/`CHIARO` uguali ai valori del mockup), `M.FONT == 20`, `M.R == 18`, cinque schede nell'ordine, `Conta` visibile con avvisi e nascosta senza, `CardKPI` orizzontale (`layout()` è un `QHBoxLayout`), `Pillola` con testo, colonna Barcode nascosta, intestazioni maiuscole, nessun `border-radius` > metà altezza nei widget creati (controlla `M.CHIP_R`). Poi `pytest -q` completo.
4. Crea `CHANGELOG-fase5-ui.md`: esiti test (come `CHANGELOG-fase4.md`), tabella del punto 2, file modificati, decisioni (colonna Barcode nascosta, destra di Scarico, ecc.), elenco "non incluso" e "non verificato" (Windows, font Segoe UI, mouse, scala reale dello schermo dell'utente).
5. Non scrivere "tutto OK" se un'area è ancora diversa: indicala.