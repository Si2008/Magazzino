"""Tray e avvio Windows: opt-in dell'utente, nessuna modifica all'import."""
import os
import subprocess
import sys
from pathlib import Path
from PySide6.QtCore import QSettings
from ..percorsi_installazione import preferenze
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QStyle


def comando_avvio():
    if getattr(sys, "frozen", False):
        return [sys.executable, "--avvio-background"]
    interprete = Path(sys.executable).with_name("pythonw.exe")
    return [str(interprete if interprete.is_file() else sys.executable),
            str(Path(__file__).resolve().parents[2] / "MagazzinoApp.py"), "--avvio-background"]


def avvio_windows(abilita=None):
    if os.name != "nt":
        return False
    import winreg
    percorso = r"Software\Microsoft\Windows\CurrentVersion\Run"
    if abilita is None:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, percorso) as chiave:
                valore, _ = winreg.QueryValueEx(chiave, "MagazzinoProfili")
            return valore == subprocess.list2cmdline(comando_avvio())
        except FileNotFoundError:
            return False
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, percorso) as chiave:
        if abilita:
            winreg.SetValueEx(chiave, "MagazzinoProfili", 0, winreg.REG_SZ,
                             subprocess.list2cmdline(comando_avvio()))
        else:
            try:
                winreg.DeleteValue(chiave, "MagazzinoProfili")
            except FileNotFoundError:
                pass
    return bool(abilita)


def configura_tray(finestra, menu):
    precedente = getattr(finestra, "_tray", None)
    if precedente is not None:
        precedente.hide()
        precedente.deleteLater()
    impostazioni = preferenze("MagazzinoProfili", "Desktop")
    finestra._esci_davvero = False
    finestra._tray = None
    finestra._mantieni_background = impostazioni.value("mantieni_background", False, type=bool)
    azione = menu.addAction("Mantieni attivo alla chiusura")
    azione.setCheckable(True)
    disponibile = QSystemTrayIcon.isSystemTrayAvailable()
    azione.setEnabled(disponibile)
    azione.setChecked(finestra._mantieni_background and disponibile)
    def modifica(valore):
        finestra._mantieni_background = valore
        impostazioni.setValue("mantieni_background", valore)
    azione.toggled.connect(modifica)
    if disponibile:
        icona = finestra.windowIcon()
        if icona.isNull():
            icona = finestra.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        tray = QSystemTrayIcon(icona, finestra)
        tray.setToolTip("Magazzino Profili")
        contestuale = QMenu(finestra)
        def mostra():
            finestra.showNormal()
            finestra.activateWindow()
            finestra.raise_()
        def esci():
            finestra._esci_davvero = True
            finestra.close()
        contestuale.addAction("Apri magazzino", mostra)
        contestuale.addAction("Esci dal programma", esci)
        tray.setContextMenu(contestuale)
        tray.activated.connect(lambda motivo: mostra() if motivo == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        tray.show()
        finestra._tray = tray
    avvio = menu.addAction("Avvia Magazzino all'accesso a Windows")
    avvio.setCheckable(True)
    avvio.setEnabled(os.name == "nt")
    from ..percorsi_installazione import installata
    if installata():
        avvio.setEnabled(False)
        avvio.setToolTip("Il setup non modifica l'avvio automatico di Windows")
    try:
        avvio.setChecked(avvio_windows())
    except OSError:
        avvio.setEnabled(False)
    def cambia_avvio(valore):
        try:
            avvio_windows(valore)
        except OSError as errore:
            avvio.blockSignals(True)
            avvio.setChecked(not valore)
            avvio.blockSignals(False)
            finestra.mostra_toast(f"Avvio automatico non configurato: {errore}", "danger")
    avvio.toggled.connect(cambia_avvio)
