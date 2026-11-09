from PIL import Image
from magazzino_profili.tests.test_correzioni_dati import factory
from magazzino_profili.ui.scheda_profilo import SchedaProfilo


def test_profilo_storico_mostra_miniatura_e_anteprima_in_alto(factory,catalogo_isolato,qtbot):
    file=catalogo_isolato/'AB12.png'
    Image.new('RGB',(40,80),'black').save(file)
    w=SchedaProfilo(factory);qtbot.addWidget(w);w.resize(1280,760);w.show()
    assert w._tabella.rowCount()==1
    assert not w._tabella.item(0,0).icon().isNull()
    w._tabella.selectRow(0)
    qtbot.wait(30)
    assert w._percorso_immagine==str(file)
    assert not w._anteprima.pixmap().isNull()
    assert w._anteprima.pixmap().height()<=w._anteprima.height()
    assert w.apri_immagine_btn.isEnabled()
    assert not w._anteprima.visibleRegion().isEmpty()
