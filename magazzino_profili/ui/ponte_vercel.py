"""Connessioni HTTPS in uscita: nessuna porta pubblica o programma di tunnel."""
import base64
import json
import time
import threading
import urllib.request
import urllib.error
from PySide6.QtCore import QObject,QTimer,Signal
from .lavori import Lavoro
from ..services.collegamento_remoto import PAGINA_TELEFONO


def _json(url,dati=None):
    req=urllib.request.Request(url,data=json.dumps(dati).encode() if dati is not None else None,
        headers={'Content-Type':'application/json','Cache-Control':'no-store'})
    with urllib.request.urlopen(req,timeout=15) as r:return json.load(r)


def esegui_giro(origine,pc,fermo=None):
    from urllib.parse import urlsplit
    from ..services.percorsi_remoti import percorso_api_consentito
    if urlsplit(origine).hostname!='127.0.0.1':raise ValueError('Origine locale non valida')
    if fermo is not None and fermo.is_set():return 0
    lavori=_json(PAGINA_TELEFONO+'/api/ponte?modo=pc&pc='+pc)['lavori']
    for lavoro in lavori:
        if fermo is not None and fermo.is_set():break
        if time.time()*1000 > lavoro.get('scadenza',float('inf')):continue
        metodo,percorso=lavoro['metodo'],lavoro['percorso']
        if not percorso_api_consentito(metodo,percorso):continue
        dati=lavoro.get('dati')
        req=urllib.request.Request(origine+percorso,
            data=json.dumps(dati).encode() if dati is not None else None,
            method=metodo,headers={'Content-Type':'application/json'})
        try:
            try:risposta=urllib.request.urlopen(req,timeout=10)
            except urllib.error.HTTPError as errore:risposta=errore
            with risposta as r:
                contenuto=r.read(2_000_001)
                if len(contenuto)>2_000_000:raise ValueError('Risposta troppo grande per il collegamento remoto')
                risultato=dict(stato=r.status,tipo=r.headers.get('Content-Type','application/json'),
                    contenuto=base64.b64encode(contenuto).decode())
        except (OSError,ValueError) as errore:
            risultato=dict(stato=502,tipo='application/json',contenuto=base64.b64encode(
                json.dumps({'detail':'Servizio locale non disponibile. Verificare la giacenza prima di riprovare.'}).encode()).decode())
        _json(PAGINA_TELEFONO+'/api/ponte?modo=risposta',dict(pc=pc,id=lavoro['id'],**risultato))
    return len(lavori)


class PonteVercel(QObject):
    errore=Signal(str)
    def __init__(self,parent=None):
        super().__init__(parent);self._worker=None;self._origine=None;self._pc=None
        self._ultimo=time.monotonic();self._notificato=False
        self._fermo=threading.Event()
        self._timer=QTimer(self);self._timer.setInterval(2000);self._timer.timeout.connect(self._giro)

    def avvia(self,origine,pc):
        self._origine,self._pc=origine,pc;self._ultimo=time.monotonic()
        self._fermo.clear()
        self._timer.start();self._giro()

    def _giro(self):
        if self._worker and self._worker.isRunning():return
        if time.monotonic()-self._ultimo>120:
            self._timer.stop();self.errore.emit('Collegamento telefono inattivo: genera un nuovo QR');return
        origine,pc=self._origine,self._pc
        lavoro=Lavoro(lambda:esegui_giro(origine,pc,self._fermo),self);self._worker=lavoro
        lavoro.riuscito.connect(self._riuscito)
        lavoro.fallito.connect(self._fallito)
        lavoro.finished.connect(lambda:setattr(self,'_worker',None));lavoro.finished.connect(lavoro.deleteLater)
        lavoro.start()

    def _riuscito(self,n):
        self._notificato=False
        if n:self._ultimo=time.monotonic()

    def _fallito(self,messaggio):
        if not self._notificato:self.errore.emit('Collegamento Vercel non disponibile: '+messaggio)
        self._notificato=True

    def ferma(self,timeout=0):
        self._timer.stop()
        self._fermo.set()
        return not self._worker or not self._worker.isRunning() or self._worker.wait(timeout)
