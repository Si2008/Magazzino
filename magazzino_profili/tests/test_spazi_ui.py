"""Layout verificato su finestre vere Qt offscreen, solo dati sintetici."""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QScrollArea
from magazzino_profili.tests.test_ui_novembre import factory_ui, tema_ui
from magazzino_profili.ui.finestra_principale import FinestraPrincipale
from magazzino_profili.ui.tema import M


@pytest.fixture(autouse=True)
def font_layout(qapp):
    """Offscreen non enumera i font Windows: usa gli stessi font del desktop."""
    from pathlib import Path
    import os
    from PySide6.QtGui import QFontDatabase
    for nome in ('segoeui.ttf','segoeuib.ttf','seguisb.ttf','consola.ttf','consolab.ttf'):
        p=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/nome
        if p.is_file():QFontDatabase.addApplicationFont(str(p))
    if 'Segoe UI' not in QFontDatabase.families():
        pytest.skip('Font Segoe UI assente: misure del layout non verificabili')


@pytest.mark.parametrize('dimensioni',[(1024,768),(1366,768),(1920,1080)])
@pytest.mark.parametrize('pagina',['inventario','carico','scarico'])
def test_colonne_utilizzabili_e_ridimensionabili(tema_ui,qtbot,factory_ui,dimensioni,pagina):
    w=FinestraPrincipale(factory_ui,'AMMINISTRATORE','test');qtbot.addWidget(w)
    w.resize(*dimensioni);w.show()
    p=getattr(w,'scheda_'+pagina);w._tab.setCurrentWidget(p)
    qtbot.wait(10)
    assert (w.width(),w.height())==dimensioni
    sinistra,destra=p.divisione.sizes()
    assert sinistra>=M.COLONNA_MIN
    assert destra>= (M.ASIDE_MIN if pagina=='inventario' else M.COLONNA_MIN)
    assert not p.divisione.childrenCollapsible() and not p.divisione.opaqueResize()
    assert p.divisione.handleWidth()>=12
    if dimensioni[0]>=1366:
        p.divisione.moveSplitter(sinistra-50,1)
        qtbot.wait(5)
        assert p.divisione.sizes()[1]>=destra+40
    if pagina=='inventario':
        p._tabella.selectRow(0)
        qtbot.wait(5)
        assert p._pannello_dettagli.findChild(QScrollArea).horizontalScrollBar().maximum()==0
        codice=p._barcode_selezionato
        p.dettagli.setChecked(False);qtbot.wait(5)
        assert p._pannello_dettagli.isHidden()
        p.dettagli.setChecked(True);qtbot.wait(5)
        assert p._pannello_dettagli.isVisible() and p._pannello_dettagli.width()>=M.ASIDE_MIN
        assert p._barcode_selezionato==codice
    else:
        ricerca=p.ricerca_profili;tab=ricerca.tabella
        assert tab.rowHeight(0)==M.RIGA_PROFILI and M.RIGA_PROFILI>=72
        assert tab.maximumHeight()>10000
        assert tab.viewport().height()>=150
        if dimensioni[1]>=1080:assert tab.height()>400
        assert not p.dettagli_elenco.isChecked()
        item=tab.item(0,0)
        qtbot.mouseClick(tab.viewport(),Qt.LeftButton,pos=tab.visualItemRect(item).center())
        scelta=ricerca._righe[0]
        if pagina=='carico':assert p.codice.text()==scelta.codice
        else:assert p.barcode.text()==scelta.barcode
        p.dettagli_elenco.setChecked(True);qtbot.wait(5)
        assert any(a.isVisible() for a in p.pannello_profili.findChildren(QScrollArea))
        p.dettagli_elenco.setChecked(False)
    w._esci_davvero=True


def test_mockup_rispecchia_colonne_e_righe():
    from pathlib import Path
    html=(Path(__file__).resolve().parents[2]/'magazzino-mockup-grande.html').read_text(encoding='utf-8')
    assert '--sx:44fr;--dx:56fr' in html
    assert 'minmax(384px' in html and 'height:72px' in html
    assert 'ridimensiona' in html and 'Dettagli e ultimi movimenti' in html
