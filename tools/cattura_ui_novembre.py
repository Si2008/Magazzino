"""Renderizza le schermate su dati sintetici; nessun accesso al DB operativo."""
from pathlib import Path
import json
import os
import sys
import tempfile

RADICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RADICE))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["MAGAZZINO_NO_ANIM"] = "1"
os.environ["MAGAZZINO_CONFIG"] = str(RADICE / "config-anteprima-inesistente.toml")
os.environ["MAGAZZINO_CATALOGO_IMMAGINI"] = str(RADICE / "catalogo_immagini")

from PySide6.QtCore import QSettings
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication, QDialog, QVBoxLayout
from sqlalchemy import create_engine
from magazzino_profili.db import crea_session_factory
from magazzino_profili.domain import Base, Profilo, Pezzo, Colore
from magazzino_profili.sicurezza import Ruolo
from magazzino_profili.ui import tema
from magazzino_profili.ui.finestra_principale import FinestraPrincipale
from magazzino_profili.ui.scheda_profilo import SchedaProfilo


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else RADICE / "docs/verifica-ui-20261106"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="magazzino-preferenze-anteprima-") as preferenze:
        QSettings.setDefaultFormat(QSettings.IniFormat)
        QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, preferenze)
        app = QApplication([])
        # La piattaforma offscreen nel sandbox non enumera i font Windows.
        # Caricamento limitato al processo di verifica, senza installare font.
        for nome in ("segoeui.ttf", "segoeuib.ttf", "seguisb.ttf", "consola.ttf", "consolab.ttf"):
            font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / nome
            if font.is_file():
                QFontDatabase.addApplicationFont(str(font))
        if "Segoe UI" not in QFontDatabase.families():
            raise RuntimeError("Font di verifica non caricato: screenshot non attendibili")
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        factory = crea_session_factory(engine)
        with factory() as s:
            c = Colore(codice_normalizzato="BIANCO", nome_visualizzato="Bianco")
            a = Colore(codice_normalizzato="AN007", nome_visualizzato="Antracite")
            p = Profilo(codice="AZ2001", descrizione="Profilo dimostrativo", lunghezza_standard_mm=6000)
            q = Profilo(codice="SENZA-PNG", descrizione="Profilo senza sezione", lunghezza_standard_mm=6000)
            s.add_all([c, a, p, q]); s.flush()
            for profilo, colore, lung, vassoio, codice in ((p,c,6000,"4","P001"),(p,a,3200,"7","P002"),(q,c,4200,"9","P003")):
                s.add(Pezzo(profilo_id=profilo.id, colore_id=colore.id, lunghezza_mm=lung,
                    numero_vassoio=vassoio, quantita=1, unitario=True, stato="Caricato", barcode=codice))
            s.commit()
        schermate = []
        def salva(widget, nome, modo):
            app.processEvents(); app.processEvents()
            file = output / f"{nome}-{modo}.png"
            if not widget.grab().save(str(file)):
                raise RuntimeError("Cattura non riuscita: " + nome)
            schermate.append(dict(schermata=nome, tema=modo, file=file.name,
                                  larghezza=widget.width(), altezza=widget.height(), dati="sintetici"))
        for modo, t in (("chiaro", tema.CHIARO),("scuro", tema.SCURO)):
            tema.ATTUALE = t
            w = FinestraPrincipale(factory, Ruolo.AMMINISTRATORE, "anteprima")
            w.setWindowTitle("Magazzino Profili · DATI SINTETICI")
            w.resize(1366, 768); w.show(); app.processEvents()
            inv = w.scheda_inventario
            inv._tabella.selectRow(0)
            salva(w, "inventario", modo)
            for n in range(inv._tabella.rowCount()):
                if inv._tabella.item(n, 1).text().startswith("SENZA-PNG"):
                    inv._tabella.selectRow(n)
            salva(w, "inventario-senza-immagine", modo)
            for nome in ("carico", "scarico"):
                pagina = getattr(w, "scheda_" + nome)
                w._tab.setCurrentWidget(pagina)
                pagina.ricerca_profili.cerca.setText("AZ2001")
                pagina.ricerca_profili._filtra()
                pagina.ricerca_profili.tabella.selectRow(0)
                if nome == "carico":
                    pagina.colore.setText("BIANCO"); pagina.numero_vassoio.setText("4")
                    pagina._aggiorna_anteprima()
                else:
                salva(w, nome, modo)
            editor = QDialog(w); editor.setWindowTitle("Gestisci profili · DATI SINTETICI")
            layout = QVBoxLayout(editor); profili = SchedaProfilo(factory, editor)
            layout.addWidget(profili); editor.resize(1280, 740); editor.show()
            profili._tabella.selectRow(0)
            salva(editor, "gestione-profili", modo)
            editor.close(); editor.deleteLater()
            w._esci_davvero = True; w.close(); w.deleteLater(); app.processEvents()
        engine.dispose()
        (output / "schermate.json").write_text(json.dumps(schermate, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Create {len(schermate)} schermate sintetiche in {output}")


if __name__ == "__main__":
    main()
