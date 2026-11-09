"""Sessione ICON invisibile, condivisa e limitata all'origine configurata."""
from __future__ import annotations

import json
from time import monotonic
from urllib.parse import urlsplit

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtWidgets import QDialog, QLabel, QMessageBox, QVBoxLayout

from ..services import richiamo_vassoio as servizio


def _stessa_origine(url: str, origine: str) -> bool:
    a, b = urlsplit(url), urlsplit(origine)
    return (a.scheme.lower(), a.hostname, a.port or (443 if a.scheme == 'https' else 80)) == (
        b.scheme.lower(), b.hostname, b.port or (443 if b.scheme == 'https' else 80))


def _script_riga(origine, uds):
    dati = json.dumps(dict(origine=origine, uds=uds))
    return '''(() => {
      const dati = %s;
      if (location.origin !== dati.origine || typeof window.$?.sendMove !== 'function' ||
          !document.querySelector('#move_msg_content')) return {esito:'pagina_non_pronta'};
      const formato = /^javascript:\\s*\\$\\.sendMove\\(\\{\\s*uds:\\s*'([A-Za-z0-9_-]+)'\\s*,\\s*magaz:\\s*'([A-Za-z0-9_-]+)'\\s*,\\s*cnt:\\s*'(\\d+)'\\s*\\}\\)\\s*;?$/;
      const righe = [];
      for (const link of document.querySelectorAll('a[id^="mov_"][href]')) {
        let comando;
        try { comando = decodeURIComponent(link.getAttribute('href')); } catch { continue; }
        const m = formato.exec(comando);
        if (m && m[1] === dati.uds && link.id === 'mov_' + m[3])
          righe.push({uds:m[1],magaz:m[2],cnt:m[3],disabilitato:link.classList.contains('ui-disabled')});
      }
      if (righe.length !== 1 || righe[0].disabilitato) return {esito:'riga_non_disponibile',numero:righe.length};
      return {esito:'pronta',riga:righe[0]};
    })()''' % dati


def _script_ricerca(origine, uds):
    dati = json.dumps(dict(origine=origine, uds=uds))
    return '''(() => {
      const dati = %s;
      if (location.origin !== dati.origine || typeof window.$?.sendMove !== 'function')
        return {esito:'pagina_non_pronta'};
      const forms = [...document.forms].filter(f => {
        const u = new URL(f.action, location.href);
        return u.origin === dati.origine && u.pathname === '/Search/Search_UDS_main_doSearch';
      });
      if (forms.length !== 1) return {esito:'ricerca_non_verificata'};
      const form = forms[0];
      const campi = [...form.querySelectorAll('input[type="text"],input[type="search"]')]
        .filter(e => !e.disabled && e.offsetParent !== null);
      if (campi.length !== 1) return {esito:'ricerca_non_verificata'};
      campi[0].value = dati.uds;
      campi[0].dispatchEvent(new Event('input',{bubbles:true}));
      campi[0].dispatchEvent(new Event('change',{bubbles:true}));
      const submit = form.querySelector('[type="submit"]');
      if (submit) submit.click(); else form.requestSubmit();
      return {esito:'ricerca_avviata'};
    })()''' % dati


def _script_invio(origine, uds, riga):
    dati = json.dumps(dict(origine=origine, riga=riga))
    script = _script_riga(origine, uds)
    return '''(() => { const confermata = %s; const attuale = %s;
      if (attuale.esito !== 'pronta' || attuale.riga.magaz !== confermata.riga.magaz ||
          attuale.riga.cnt !== confermata.riga.cnt) return {esito:'riga_cambiata'};
      window.__magazzinoRichiamo = {uds:attuale.riga.uds,magaz:attuale.riga.magaz,risposta:null};
      window.$(document).off('ajaxComplete.magazzinoRichiamo').on('ajaxComplete.magazzinoRichiamo', (_e, xhr, settings) => {
        const u = new URL(settings.url, location.href);
        if (u.origin === confermata.origine && u.pathname === '/Search/Search_UDS_move' &&
            u.searchParams.get('CodiceUDS') === attuale.riga.uds &&
            u.searchParams.get('MagazzinoUDS') === attuale.riga.magaz) {
          window.__magazzinoRichiamo.risposta = {status:xhr.status};
          window.$(document).off('ajaxComplete.magazzinoRichiamo');
        }
      });
      document.querySelector('#move_msg_content').textContent = '';
      window.$.sendMove({uds:attuale.riga.uds,magaz:attuale.riga.magaz,cnt:attuale.riga.cnt});
      return {esito:'funzione_invocata'};
    })()''' % (dati, script)


class _PaginaIcon:
    """Creata soltanto quando la modalità ICON è realmente richiesta."""
    @staticmethod
    def crea(origine, parent):
        from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineUrlRequestInterceptor
        from PySide6.QtWebEngineWidgets import QWebEngineView

        class Filtro(QWebEngineUrlRequestInterceptor):
            def interceptRequest(self, info):
                if not _stessa_origine(info.requestUrl().toString(), origine):
                    info.block(True)

        class Pagina(QWebEnginePage):
            def acceptNavigationRequest(self, url, nav_type, is_main_frame):
                return _stessa_origine(url.toString(), origine)

            def createWindow(self, _type):
                return None

        profilo = QWebEngineProfile(parent)  # profilo senza nome: memoria soltanto
        filtro = Filtro(profilo)
        profilo.setUrlRequestInterceptor(filtro)
        vista = QWebEngineView(parent)
        pagina = Pagina(profilo, vista)
        vista.setPage(pagina)
        return profilo, filtro, vista, pagina


class RichiamoIcon(QObject):
    occupato = Signal(bool)

    def __init__(self, factory, parent):
        super().__init__(parent)
        self.factory, self.parent_widget = factory, parent
        self._pagina = None
        self._attivo = False
        self._pannello_aperto = False
        self._inviato = False
        self._token = 0

    def _prepara_pagina(self, origine):
        if self._pagina is None:
            self._profilo, self._filtro, self._vista, self._pagina = _PaginaIcon.crea(origine, self.parent_widget)
            self._origine_sessione = origine
            self._pagina.loadFinished.connect(lambda ok: self._caricata(ok, self._token))
        elif origine != self._origine_sessione:
            raise ValueError("L’indirizzo di ICON è cambiato. Riavvia il programma per applicarlo.")

    def apri_pannello_rientro(self):
        titolo = "Rimanda vassoio"
        if self._pannello_aperto:
            return
        if self._attivo:
            QMessageBox.information(self.parent_widget, titolo, "Attendi l’esito del richiamo in corso.")
            return
        try:
            modo, origine = servizio.configurazione()
            if modo != "icon":
                raise ValueError("Per accedere al pannello di rientro attiva la modalità ICON.")
            self._prepara_pagina(origine)
        except (ValueError, OSError, ImportError) as errore:
            QMessageBox.warning(self.parent_widget, titolo, str(errore))
            return

        dialogo = QDialog(self.parent_widget)
        dialogo.setWindowTitle(titolo + " · ICON")
        dialogo.resize(1050, 720)
        layout = QVBoxLayout(dialogo)
        istruzione = QLabel("Usa il comando di rientro di ICON per il vassoio in baia.", dialogo)
        istruzione.setWordWrap(True)
        layout.addWidget(istruzione)
        layout.addWidget(self._vista, 1)
        self._pannello_aperto = True
        try:
            self._pagina.load(QUrl(origine + "/"))
            self._vista.show()
            dialogo.exec()
        finally:
            self._vista.hide()
            self._vista.setParent(self.parent_widget)
            self._pannello_aperto = False
            dialogo.deleteLater()

    def avvia(self, barcode, *, chiave=None, selezione=None):
        if self._attivo or self._pannello_aperto:
            return
        try:
            candidato = servizio.candidato(self.factory, barcode, chiave=chiave)
            modo, origine = servizio.configurazione()
            if modo == "icon":
                self._prepara_pagina(origine)
        except (ValueError, OSError, ImportError) as errore:
            QMessageBox.warning(self.parent_widget, 'Chiama vassoio', str(errore))
            return
        self._attivo = True
        self._inviato = False
        self._in_conferma = False
        self._riga_inviata = {}
        self._token += 1
        token = self._token
        self._inizio = monotonic()
        self._candidato, self._modo, self._origine = candidato, modo, origine
        self._chiave, self._selezione = chiave, selezione
        self.occupato.emit(True)
        if modo == 'simulazione':
            self._riga_inviata = {'magaz': 'SIMULAZIONE'}
            self._conferma({'uds':candidato.uds,'magaz':'SIMULAZIONE','cnt':'0'}, token)
            return
        self._login_tentato = False
        self._ricerca_avviata = False
        self._scadenza(token, 20000, preparazione=True)
        self._pagina.load(QUrl(origine + '/'))

    def _scadenza(self, token, ms, *, preparazione=False):
        def scaduto():
            if token != self._token or (preparazione and self._in_conferma):
                return
            self._termina('Esito sconosciuto — controlla ICON prima di riprovare' if self._inviato
                          else 'ICON non ha risposto entro il tempo previsto', token)
        QTimer.singleShot(ms, scaduto)

    def _esegui_json(self, script, callback):
        def decodifica(valore):
            try:
                esito = json.loads(valore)
            except (TypeError, ValueError):
                esito = None
            callback(esito)
        self._pagina.runJavaScript(f"JSON.stringify({script})", 0, decodifica)

    def _caricata(self, ok, token):
        if token != self._token or not self._attivo:
            return
        if self._inviato:
            self._termina('Esito sconosciuto — controlla ICON prima di riprovare', token)
            return
        if not ok or not _stessa_origine(self._pagina.url().toString(), self._origine):
            self._termina('Pagina ICON non disponibile', token)
            return
        if self._ricerca_avviata:
            self._leggi_riga(token, 0)
            return
        self._pagina.runJavaScript("Boolean(document.querySelector('#_login_Form'))", 0,
            lambda login: self._login(login, token))

    def _login(self, login, token):
        if token != self._token or not self._attivo:
            return
        if login:
            if self._login_tentato:
                self._termina('Accesso ICON non riuscito', token)
                return
            credenziale = servizio.credenziale_windows()
            if not credenziale:
                self._termina('Credenziale Windows MagazzinoProfili/ICON assente', token)
                return
            if not _stessa_origine(self._pagina.url().toString(), self._origine):
                self._termina('Origine ICON non valida', token)
                return
            self._login_tentato = True
            script = servizio.script_login_icon(self._origine, *credenziale)
            self._pagina.runJavaScript(script, 0, lambda ok: None if ok else self._termina('Form di accesso ICON inatteso', token))
            return
        self._esegui_json(_script_ricerca(self._origine, self._candidato.uds),
            lambda risultato: self._ricerca(risultato, token))

    def _ricerca(self, risultato, token):
        if token != self._token or not self._attivo:
            return
        if not isinstance(risultato, dict) or risultato.get('esito') != 'ricerca_avviata':
            self._termina('Ricerca ICON non verificata sulla pagina', token)
            return
        self._ricerca_avviata = True
        QTimer.singleShot(600, lambda: self._leggi_riga(token, 0))

    def _leggi_riga(self, token, tentativi):
        if token != self._token or not self._attivo:
            return
        self._esegui_json(_script_riga(self._origine, self._candidato.uds),
            lambda esito: self._riga(esito, token, tentativi))

    def _riga(self, esito, token, tentativi):
        if token != self._token or not self._attivo or self._in_conferma:
            return
        if isinstance(esito, dict) and esito.get('esito') == 'pronta':
            self._conferma(esito['riga'], token)
        elif tentativi < 8 and isinstance(esito, dict) and esito.get('numero') == 0:
            QTimer.singleShot(400, lambda: self._leggi_riga(token, tentativi + 1))
        else:
            self._termina('Riga ICON assente, ambigua o non disponibile', token)

    def _conferma(self, riga, token):
        self._in_conferma = True
        c = self._candidato
        risposta = QMessageBox.question(self.parent_widget, 'Chiama vassoio',
            f'{c.codice} — {c.descrizione}\nUDS: {c.uds}\nSilo: {riga["magaz"]}\n\nConfermi il richiamo?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if token != self._token or not self._attivo:
            return
        if risposta != QMessageBox.StandardButton.Yes:
            self._termina('Annullato', token)
            return
        try:
            nuovo = servizio.candidato(self.factory, c.barcode, chiave=self._chiave)
            if nuovo != c or (self._selezione and not self._selezione()):
                raise ValueError('Selezione o disponibilità cambiata')
        except ValueError as errore:
            self._termina(str(errore), token)
            return
        if self._modo == 'simulazione':
            self._termina('Simulazione: richiamo confermato, nessun movimento inviato', token)
            return
        invio = _script_invio(self._origine, c.uds, riga)
        if not _stessa_origine(self._pagina.url().toString(), self._origine):
            self._termina('Origine ICON cambiata', token)
            return
        self._inviato = True  # callback incerta se naviga o si chiude
        self._riga_inviata = riga
        self._esegui_json(invio, lambda esito: self._dopo_invio(esito, token))
        self._scadenza(token, 15000)

    def _dopo_invio(self, esito, token):
        if token != self._token or not self._attivo:
            return
        if isinstance(esito, dict) and esito.get('esito') == 'riga_cambiata':
            self._inviato = False
            self._termina('Riga ICON cambiata prima del richiamo', token)
            return
        if not isinstance(esito, dict) or esito.get('esito') != 'funzione_invocata':
            self._termina('Esito sconosciuto — controlla ICON prima di riprovare', token)
            return
        QTimer.singleShot(600, lambda: self._osserva(token, 0))

    def _osserva(self, token, tentativi):
        if token != self._token or not self._attivo:
            return
        if not _stessa_origine(self._pagina.url().toString(), self._origine):
            self._termina('Esito sconosciuto — controlla ICON prima di riprovare', token)
            return
        self._esegui_json("({testo:document.querySelector('#move_msg_content')?.textContent || '', risposta:window.__magazzinoRichiamo?.risposta || null})",
            lambda stato: self._messaggio(stato, token, tentativi))

    def _messaggio(self, stato, token, tentativi):
        if token != self._token or not self._attivo:
            return
        testo = stato.get('testo', '') if isinstance(stato, dict) else ''
        risposta = stato.get('risposta') if isinstance(stato, dict) else None
        if risposta is not None and isinstance(testo, str) and testo.strip() and self._candidato.uds in testo:
            self._termina('Risposta ICON: ' + testo.strip()[:300], token)
        elif risposta is not None and risposta.get('status') != 200:
            self._termina('ICON ha restituito un errore; controlla lo stato del vassoio', token)
        elif tentativi < 20:
            QTimer.singleShot(500, lambda: self._osserva(token, tentativi + 1))
        else:
            self._termina('Esito sconosciuto — controlla ICON prima di riprovare', token)

    def _termina(self, esito, token):
        if token != self._token or not self._attivo:
            return
        self._attivo = False
        self._token += 1
        self.occupato.emit(False)
        if esito.startswith('Risposta ICON:'):
            esito_log = 'risposta_icon'
        elif esito.startswith('Esito sconosciuto'):
            esito_log = 'esito_sconosciuto'
        elif esito.startswith('Simulazione:'):
            esito_log = 'simulazione_confermata'
        elif esito == 'Annullato':
            esito_log = 'annullato'
        else:
            esito_log = 'interrotto'
        try:
            servizio.registra(self._origine, self._candidato.uds,
                getattr(self, '_riga_inviata', {}).get('magaz', ''), self._modo,
                esito_log, monotonic() - self._inizio)
        except OSError:
            esito += '\nIl log del richiamo non è stato scritto.'
        QMessageBox.information(self.parent_widget, 'Chiama vassoio', esito)

    def interrompi_per_chiusura(self):
        if self._attivo:
            self._termina('Esito sconosciuto — controlla ICON prima di riprovare' if self._inviato
                          else 'Richiamo annullato alla chiusura', self._token)
