"""Pagina ICON sintetica: nessun server o movimento reale."""
import os
import json
import subprocess
from contextlib import nullcontext
from time import monotonic, sleep
from types import SimpleNamespace

import pytest

from magazzino_profili.services import richiamo_vassoio as servizio
from magazzino_profili.ui.vista_icon import _script_riga, _script_ricerca, _script_invio


def test_pannello_rientro_apre_icon_senza_selezionare_un_pezzo(monkeypatch, qapp):
    from PySide6.QtWidgets import QDialog, QWidget
    from magazzino_profili.ui.vista_icon import RichiamoIcon

    parent = QWidget()
    controller = RichiamoIcon(None, parent)
    controller._vista = QWidget(parent)
    caricamenti = []
    controller._pagina = SimpleNamespace(load=lambda url: caricamenti.append(url.toString()))
    controller._origine_sessione = "http://localhost"
    monkeypatch.setattr(servizio, "configurazione", lambda: ("icon", "http://localhost"))

    def durante_dialogo(dialogo):
        assert controller._pannello_aperto
        assert controller._vista.parentWidget() is dialogo
        controller.apri_pannello_rientro()

    monkeypatch.setattr(QDialog, "exec", durante_dialogo)
    controller.apri_pannello_rientro()
    assert caricamenti == ["http://localhost/"]
    assert controller._vista.parentWidget() is parent
    assert not controller._pannello_aperto


def test_richiamo_riga_storica_con_uds_esplicito(monkeypatch):
    pezzo = SimpleNamespace(id=42, barcode="ABC", unitario=False, quantita=12,
                            stato=None, numero_vassoio="0001",
                            profilo=SimpleNamespace(codice="ABC", descrizione="Profilo"))
    monkeypatch.setattr(servizio, "pezzo_per_barcode", lambda sessione, barcode: pezzo)
    monkeypatch.setattr(servizio, "leggi_sezione", lambda nome: ({}, None))
    factory = nullcontext
    assert servizio.candidato(factory, "ABC", chiave="pezzo:42").uds == "0001"
    pezzo.stato = "Scaricato"
    with pytest.raises(ValueError, match="non è più disponibile"):
        servizio.candidato(factory, "ABC")
    pezzo.stato = None
    pezzo.numero_vassoio = None
    with pytest.raises(ValueError, match="Nessun vassoio associato"):
        servizio.candidato(factory, "ABC")


def test_uds_ambiguo_e_mappa():
    with pytest.raises(ValueError):
        servizio.codice_uds('1')
    assert servizio.codice_uds('1', {'1': '0001'}) == '0001'
    assert servizio.codice_uds('0001') == '0001'
    with pytest.raises(ValueError):
        servizio.codice_uds('Da confermare')


def test_script_javascript_sintatticamente_validi():
    scripts = [_script_riga('http://localhost', '0001'),
               _script_ricerca('http://localhost', '0001'),
               servizio.script_login_icon('http://localhost', 'utente-finto', 'password-finta')]
    risultato = subprocess.run(['node', '-e',
        'for (const s of JSON.parse(process.argv[1])) new Function(s);', json.dumps(scripts)],
        capture_output=True, text=True, check=False)
    assert risultato.returncode == 0, risultato.stderr


def test_riga_icon_simulata_ambigua_e_univoca():
    script = _script_riga('http://localhost', '0001')
    codice = r'''
      const script = JSON.parse(process.argv[1]);
      global.location = {origin:'http://localhost'};
      global.window = {$:{sendMove(){throw Error('Il rilevamento non deve muovere');}}};
      const link = {id:'mov_0',getAttribute(){return "javascript:$.sendMove({ uds: '0001', magaz: 'SILO2', cnt: '0' })";},
                    classList:{contains(){return false;}}};
      let links = [link];
      global.document = {querySelector(){return {};},querySelectorAll(){return links;}};
      const primo = eval(script);
      links = [link, link];
      const ambiguo = eval(script);
      if (primo.esito !== 'pronta' || primo.riga.magaz !== 'SILO2' ||
          ambiguo.esito !== 'riga_non_disponibile' || ambiguo.numero !== 2) process.exit(1);
    '''
    risultato = subprocess.run(['node', '-e', codice, json.dumps(script)],
        capture_output=True, text=True, check=False)
    assert risultato.returncode == 0, risultato.stderr


def test_invio_finto_una_volta_e_riga_cambiata():
    riga = {'uds':'0001','magaz':'SILO2','cnt':'0'}
    script = _script_invio('http://localhost', '0001', riga)
    codice = r'''
      const script = JSON.parse(process.argv[1]);
      global.location = {origin:'http://localhost',href:'http://localhost/'};
      let chiamate = [];
      let silo = 'SILO2';
      const dollar = () => ({off(){return this;},on(){return this;}});
      dollar.sendMove = x => chiamate.push(x);
      global.window = {$:dollar};
      const link = {id:'mov_0',getAttribute(){return `javascript:$.sendMove({ uds: '0001', magaz: '${silo}', cnt: '0' })`;},
                    classList:{contains(){return false;}}};
      global.document = {querySelector(){return {textContent:'vecchio messaggio'};},querySelectorAll(){return [link];}};
      const primo = eval(script);
      silo = 'SILO3';
      const cambiato = eval(script);
      if (primo.esito !== 'funzione_invocata' || chiamate.length !== 1 ||
          chiamate[0].magaz !== 'SILO2' || cambiato.esito !== 'riga_cambiata') process.exit(1);
    '''
    risultato = subprocess.run(['node', '-e', codice, json.dumps(script)],
        capture_output=True, text=True, check=False)
    assert risultato.returncode == 0, risultato.stderr


def test_login_finto_compila_campi_nascosti():
    script = servizio.script_login_icon('http://localhost', 'utente-finto', 'password-finta')
    codice = r'''
      const script = JSON.parse(process.argv[1]);
      global.location = {origin:'http://localhost',href:'http://localhost/'};
      const utente = {value:''}, password = {value:''};
      global.HTMLFormElement = class {submit(){this.inviato=true;}};
      const form = new HTMLFormElement();
      form.method='post'; form.action='http://localhost/Account/Login';
      form.querySelector = s => s === '#hiddenUsername' ? utente : password;
      global.document = {querySelector(){return form;}};
      if (eval(script) !== true || !form.inviato || utente.value !== 'utente-finto' ||
          password.value !== 'password-finta') process.exit(1);
      location.origin='http://altra-origine';
      form.inviato=false;
      if (eval(script) !== false || form.inviato) process.exit(2);
    '''
    risultato = subprocess.run(['node', '-e', codice, json.dumps(script)],
        capture_output=True, text=True, check=False)
    assert risultato.returncode == 0, risultato.stderr


def test_simulazione_predefinita_senza_webengine(monkeypatch):
    monkeypatch.setattr(servizio, 'leggi_sezione', lambda _nome: ({}, None))
    assert servizio.configurazione() == ('simulazione', 'http://localhost')


def test_simulazione_conferma_annullamento_e_doppio_clic(monkeypatch):
    from PySide6.QtWidgets import QApplication, QWidget, QMessageBox
    from magazzino_profili.ui.vista_icon import RichiamoIcon
    app = QApplication.instance() or QApplication([])
    parent = QWidget()
    controller = RichiamoIcon(None, parent)
    c = servizio.Candidato('ABC', 'P1', 'Profilo', '0001', 7)
    monkeypatch.setattr(servizio, 'candidato', lambda *_a, **_k: c)
    monkeypatch.setattr(servizio, 'configurazione', lambda: ('simulazione', 'http://localhost'))
    log = []
    monkeypatch.setattr(servizio, 'registra', lambda *a: log.append(a))
    messaggi = []
    monkeypatch.setattr(QMessageBox, 'information', lambda *a: messaggi.append(a[-1]))
    risposte = [QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes]

    def conferma(*_a):
        controller.avvia('ABC')  # secondo clic durante la conferma: ignorato
        return risposte.pop(0)

    monkeypatch.setattr(QMessageBox, 'question', conferma)
    controller.avvia('ABC')
    controller.avvia('ABC')
    assert len(log) == 2
    assert 'Annullato' in messaggi[0]
    assert 'Simulazione' in messaggi[1]
    assert controller._pagina is None
    parent.deleteLater()


def test_selezione_cambiata_dopo_conferma_blocca_richiamo(monkeypatch):
    from PySide6.QtWidgets import QApplication, QWidget, QMessageBox
    from magazzino_profili.ui.vista_icon import RichiamoIcon
    app = QApplication.instance() or QApplication([])
    parent = QWidget()
    controller = RichiamoIcon(None, parent)
    c = servizio.Candidato('ABC', 'P1', '', '0001', 1)
    monkeypatch.setattr(servizio, 'candidato', lambda *_a, **_k: c)
    monkeypatch.setattr(servizio, 'configurazione', lambda: ('simulazione', 'http://localhost'))
    monkeypatch.setattr(servizio, 'registra', lambda *_a: None)
    monkeypatch.setattr(QMessageBox, 'question', lambda *_a: QMessageBox.StandardButton.Yes)
    esiti = []
    monkeypatch.setattr(QMessageBox, 'information', lambda *a: esiti.append(a[-1]))
    controller.avvia('ABC', selezione=lambda: False)
    assert 'Selezione' in esiti[0]
    parent.deleteLater()


def test_credenziale_assente_interrompe_login(monkeypatch):
    from PySide6.QtWidgets import QApplication, QWidget
    from magazzino_profili.ui.vista_icon import RichiamoIcon
    app = QApplication.instance() or QApplication([])
    parent = QWidget()
    controller = RichiamoIcon(None, parent)
    controller._attivo = True
    controller._token = 3
    controller._login_tentato = False
    monkeypatch.setattr(servizio, 'credenziale_windows', lambda: None)
    esiti = []
    monkeypatch.setattr(controller, '_termina', lambda msg, token: esiti.append(msg))
    controller._login(True, 3)
    assert 'assente' in esiti[0]
    parent.deleteLater()


def test_rifiuto_e_chiusura_dopo_invio_sono_esiti_incerti(monkeypatch):
    from PySide6.QtWidgets import QApplication, QWidget
    from magazzino_profili.ui.vista_icon import RichiamoIcon
    app = QApplication.instance() or QApplication([])
    parent = QWidget()
    controller = RichiamoIcon(None, parent)
    controller._attivo = True
    controller._inviato = True
    controller._token = 4
    controller._candidato = servizio.Candidato('ABC', 'P1', '', '0001', 1)
    esiti = []
    monkeypatch.setattr(controller, '_termina', lambda msg, token: esiti.append(msg))
    controller._messaggio({'testo':'', 'risposta':{'status':403}}, 4, 0)
    assert 'errore' in esiti[0]
    controller.interrompi_per_chiusura()
    assert 'Esito sconosciuto' in esiti[1]
    parent.deleteLater()


def test_timeout_dopo_invio_non_riprova(monkeypatch):
    from PySide6.QtWidgets import QApplication, QWidget
    from PySide6.QtCore import QTimer
    from magazzino_profili.ui.vista_icon import RichiamoIcon
    app = QApplication.instance() or QApplication([])
    parent = QWidget()
    controller = RichiamoIcon(None, parent)
    controller._token = 2
    controller._inviato = True
    esiti = []
    monkeypatch.setattr(controller, '_termina', lambda msg, token: esiti.append(msg))
    monkeypatch.setattr(QTimer, 'singleShot', lambda ms, callback: callback())
    controller._scadenza(2, 1)
    assert esiti == ['Esito sconosciuto — controlla ICON prima di riprovare']
    parent.deleteLater()


def test_pagina_simulata_individua_riga_e_ricerca():
    os.environ.setdefault('QTWEBENGINE_DISABLE_SANDBOX', '1')
    from PySide6.QtWidgets import QApplication, QWidget
    from PySide6.QtWebEngineCore import QWebEnginePage
    from PySide6.QtCore import QUrl
    from magazzino_profili.ui.vista_icon import RichiamoIcon

    app = QApplication.instance() or QApplication([])
    parent = QWidget()
    controller = RichiamoIcon(None, parent)
    pagina = QWebEnginePage()
    controller._pagina = pagina
    html = '''<form action="/Search/Search_UDS_main_doSearch"><input type="text" id="cerca"><button type="submit">Cerca</button></form>
      <div id="move_msg_content"></div>
      <a id="mov_0" href="javascript:$.sendMove({ uds: '0001', magaz: 'SILO2', cnt: '0' })">→</a>
      <script>window.$ = {sendMove: function(x) {window.chiamate = (window.chiamate || 0) + 1; window.parametri=x;}};
      document.querySelector('form').addEventListener('submit', e => e.preventDefault());</script>'''
    finito = []
    pagina.loadFinished.connect(lambda ok: finito.append(ok))
    pagina.setHtml(html, QUrl('http://localhost/'))

    def attendi(lista):
        limite = monotonic() + 10
        while not lista and monotonic() < limite:
            app.processEvents()
            sleep(.01)
        assert lista
        return lista[0]

    assert attendi(finito)
    risultati = []
    controller._esegui_json(_script_ricerca('http://localhost', '0001'), risultati.append)
    ricerca = attendi(risultati)
    assert isinstance(ricerca, dict), repr(ricerca)
    assert ricerca['esito'] == 'ricerca_avviata'
    risultati.clear()
    controller._esegui_json(_script_riga('http://localhost', '0001'), risultati.append)
    riga = attendi(risultati)
    assert riga['riga']['magaz'] == 'SILO2'
    assert riga['riga']['uds'] == '0001'
    risultati.clear()
    pagina.runJavaScript('window.chiamate || 0', 0, risultati.append)
    assert attendi(risultati) == 0
    pagina.deleteLater()
