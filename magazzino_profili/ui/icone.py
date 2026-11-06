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
