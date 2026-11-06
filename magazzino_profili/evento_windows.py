"""Segnale nativo di arresto, utilizzabile anche dall'eseguibile senza console."""
import ctypes
from ctypes import wintypes
from uuid import uuid4


def _api():
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
    api.CreateEventW.restype = wintypes.HANDLE
    api.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    api.OpenEventW.restype = wintypes.HANDLE
    for nome in ("SetEvent", "CloseHandle"):
        funzione = getattr(api, nome)
        funzione.argtypes = [wintypes.HANDLE]
        funzione.restype = wintypes.BOOL
    api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    api.WaitForSingleObject.restype = wintypes.DWORD
    return api


class EventoArresto:
    def __init__(self, nome=None):
        self.nome = nome or "Local\\MagazzinoTelefono-" + uuid4().hex
        self._api = _api()
        self._handle = (self._api.OpenEventW(0x00100000, False, self.nome) if nome
                        else self._api.CreateEventW(None, True, False, self.nome))
        if not self._handle:
            raise ctypes.WinError(ctypes.get_last_error())

    def segnala(self):
        if not self._api.SetEvent(self._handle):
            raise ctypes.WinError(ctypes.get_last_error())

    def attendi(self, millisecondi=0xFFFFFFFF):
        esito = self._api.WaitForSingleObject(self._handle, millisecondi)
        if esito not in (0, 258):
            raise ctypes.WinError(ctypes.get_last_error())
        return esito == 0

    def chiudi(self):
        if self._handle:
            self._api.CloseHandle(self._handle)
            self._handle = None
