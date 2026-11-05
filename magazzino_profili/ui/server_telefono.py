"""Processo telefono gestito dalla UI; parte soltanto su richiesta o opt-in."""
import os
import subprocess
import sys
from pathlib import Path
from PySide6.QtCore import QObject, QTimer, Signal


class ServerTelefono(QObject):
    messaggio = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.processo = None
        self._evento = None
        self.origine_locale = None
        from .ponte_vercel import PonteVercel
        self.ponte = PonteVercel(self)
        self.ponte.errore.connect(self.messaggio.emit)
        self._timer = QTimer(self)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(self._verifica)

    def avvia(self):
        if self.processo is not None and self.processo.poll() is None:
            self.messaggio.emit("Servizio telefono già avviato da questo programma")
            return
        from ..web.app import leggi_sezione_web
        from ..db.config import trova_config
        web = leggi_sezione_web()
        from ..services.telefono import leggi_url_pubblico
        from ..services.collegamento_remoto import PAGINA_TELEFONO
        remoto = (leggi_url_pubblico() or PAGINA_TELEFONO).rstrip('/') == PAGINA_TELEFONO
        if not remoto and not web.get("tls_proxy_locale") and not all(web.get(k) and Path(web[k]).is_file() for k in ("certificato_pem", "chiave_privata")):
            raise ValueError("Configura HTTPS o il tunnel locale prima di avviare il servizio telefono")
        ambiente = os.environ.copy()
        if remoto:
            import socket
            with socket.socket() as libero:
                libero.bind(('127.0.0.1',0));porta=libero.getsockname()[1]
            ambiente['MAGAZZINO_TELEFONO_PORTA_LOCALE']=str(porta)
            self.origine_locale=f'http://127.0.0.1:{porta}'
        ambiente["MAGAZZINO_CONFIG"] = str(trova_config())
        ambiente["MAGAZZINO_CONTROLLO_STDIN"] = "1"
        ambiente["PYTHONUNBUFFERED"] = "1"
        comando = ([sys.executable, "--server-telefono"] if getattr(sys, "frozen", False)
                   else [sys.executable, "-m", "magazzino_profili.web.app"])
        cwd = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2]
        log = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "magazzino_profili" / "telefono-server.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        if log.is_file() and log.stat().st_size > 5_000_000:
            os.replace(log, log.with_suffix(".precedente.log"))
        with log.open("ab") as output:
            if os.name == "nt":
                from ..evento_windows import EventoArresto
                if self._evento:
                    self._evento.chiudi()
                self._evento = EventoArresto()
                ambiente["MAGAZZINO_EVENTO_ARRESTO"] = self._evento.nome
            try:
                self.processo = subprocess.Popen(comando, cwd=cwd, env=ambiente,
                    stdin=subprocess.PIPE, stdout=output, stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            except BaseException:
                if self._evento:
                    self._evento.chiudi()
                    self._evento = None
                raise
        self._timer.start()
        self.messaggio.emit("Avvio servizio telefono richiesto. Usa Collega telefono per aprire la pagina Vercel" if remoto
                            else "Avvio servizio telefono richiesto")

    def _verifica(self):
        if self.processo is not None and self.processo.poll() is not None:
            codice = self.processo.returncode
            self.processo = None
            if self._evento:
                self._evento.chiudi()
                self._evento = None
            self._timer.stop()
            self.messaggio.emit(f"Servizio telefono terminato (codice {codice}). Consulta telefono-server.log")

    def ferma(self):
        if self.ponte.ferma() is False:return False
        self._timer.stop()
        if self.processo is not None and self.processo.poll() is None:
            # Solo il processo avviato da questa istanza, mai server esterni.
            try:
                if self._evento:
                    self._evento.segnala()
                else:
                    self.processo.stdin.write(b"arresta\n")
                    self.processo.stdin.flush()
            except (OSError, ValueError):
                pass  # può essere già uscito: wait/poll verificano l'esito
            try:
                self.processo.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.messaggio.emit("Servizio ancora in arresto: il processo non è stato forzato")
                return False
        self.processo = None
        if self._evento:
            self._evento.chiudi()
            self._evento = None
        return True
