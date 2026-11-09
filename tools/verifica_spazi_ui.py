"""Misura e renderizza i pannelli su SQLite sintetico, in entrambi i temi."""
from pathlib import Path
import json
import os
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ['QT_QPA_PLATFORM']='offscreen'
os.environ['MAGAZZINO_NO_ANIM']='1'
os.environ['MAGAZZINO_CONFIG']=str(ROOT/'config-verifica-assente.toml')
os.environ['MAGAZZINO_CATALOGO_IMMAGINI']=str(ROOT/'catalogo_immagini')


def main():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QCoreApplication,QEvent
    from PySide6.QtGui import QFontDatabase
    from sqlalchemy import create_engine
    from magazzino_profili.domain import Base,Profilo,Pezzo,Colore
    from magazzino_profili.db import crea_session_factory
    from magazzino_profili.ui import tema
    from magazzino_profili.ui.finestra_principale import FinestraPrincipale
    out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='magazzino-layout-') as tmp:
        os.environ['MAGAZZINO_PREFERENZE_TEST']=tmp
        app=QApplication([])
        for nome in ('segoeui.ttf','segoeuib.ttf','seguisb.ttf','consola.ttf','consolab.ttf'):
            font=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/nome
            if font.is_file():QFontDatabase.addApplicationFont(str(font))
        if 'Segoe UI' not in QFontDatabase.families():raise RuntimeError('Font Segoe UI non disponibile')
        e=create_engine('sqlite:///:memory:');Base.metadata.create_all(e);f=crea_session_factory(e)
        with f() as s,s.begin():
            c=Colore(codice_normalizzato='RAL7016',nome_visualizzato='Antracite');s.add(c);s.flush()
            for n in range(35):
                p=Profilo(codice='AZ2001' if n==0 else f'PROFILO{n:03}',descrizione='Profilo dimostrativo',lunghezza_standard_mm=6000)
                s.add(p);s.flush()
                s.add(Pezzo(profilo_id=p.id,colore_id=c.id,lunghezza_mm=6000-n*50,quantita=1,
                            barcode=f'PROVA-{n:04}',unitario=True,stato='Caricato',numero_vassoio=str(n+1)))
        risultati=[]
        for nome,t in (('chiaro',tema.CHIARO),('scuro',tema.SCURO)):
            tema.ATTUALE=t
            for larg,alt in ((1024,768),(1366,768),(1920,1080)):
                w=FinestraPrincipale(f,'AMMINISTRATORE','dati sintetici');w.resize(larg,alt);w.show();app.processEvents()
                for pagina in ('inventario','carico','scarico'):
                    p=getattr(w,'scheda_'+pagina);w._tab.setCurrentWidget(p);app.processEvents()
                    tab=p._tabella if pagina=='inventario' else p.ricerca_profili.tabella
                    tab.selectRow(0);app.processEvents();app.processEvents()
                    path=out/f'{pagina}-{nome}-{larg}.png'
                    if not w.grab().save(str(path)):raise RuntimeError('Screenshot non riuscito')
                    if hasattr(p,'divisione'):
                        colonne=p.divisione.sizes()
                    elif pagina=='inventario':
                        colonne=[p._tabella.parentWidget().width(),p._pannello_dettagli.width()]
                    else:
                        colonne=[p.layout().itemAt(i).widget().width() for i in (0,1)]
                    d=dict(pagina=pagina,tema=nome,risoluzione_richiesta=[larg,alt],finestra=[w.width(),w.height()],
                           colonne=colonne,immagine=path.name)
                    if pagina!='inventario':d.update(altezza_tabella=tab.height(),altezza_riga=tab.rowHeight(0),altezza_viewport=tab.viewport().height())
                    risultati.append(d)
                w._esci_davvero=True;w.close();w.deleteLater();app.processEvents();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        e.dispose()
        (out/'misure.json').write_text(json.dumps(risultati,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(risultati,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
