"""Scritture atomiche e blocchi fra processi, senza dipendenze esterne."""
from contextlib import contextmanager
from pathlib import Path
import os
import tempfile
import threading

_registro_mutex = threading.Lock()
_mutex_cartelle = {}


@contextmanager
def destinazione_atomica(destinazione):
    """Il file precedente resta intatto anche se il produttore fallisce."""
    finale = Path(destinazione)
    finale.parent.mkdir(parents=True, exist_ok=True)
    fd, nome = tempfile.mkstemp(prefix="." + finale.name + "-", suffix=".tmp", dir=finale.parent)
    os.close(fd)
    provvisorio = Path(nome)
    try:
        yield provvisorio
        with provvisorio.open("r+b") as file:
            os.fsync(file.fileno())
        os.replace(provvisorio, finale)
    finally:
        provvisorio.unlink(missing_ok=True)


@contextmanager
def blocco_cartella(cartella, *, attendi=True):
    """Lock rilasciato dal sistema anche se il processo termina improvvisamente."""
    chiave = str(Path(cartella).resolve()).casefold() if os.name == "nt" else str(Path(cartella).resolve())
    with _registro_mutex:
        mutex = _mutex_cartelle.setdefault(chiave, threading.RLock())
    with mutex:
        percorso = Path(cartella) / ".magazzino.lock"
        percorso.parent.mkdir(parents=True, exist_ok=True)
        with percorso.open("a+b") as file:
            file.seek(0, os.SEEK_END)
            if file.tell() == 0:
                file.write(b"0")
                file.flush()
            file.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(file.fileno(), msvcrt.LK_LOCK if attendi else msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(file.fileno(), fcntl.LOCK_EX | (0 if attendi else fcntl.LOCK_NB))
            try:
                yield
            finally:
                file.seek(0)
                if os.name == "nt":
                    msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(file.fileno(), fcntl.LOCK_UN)
