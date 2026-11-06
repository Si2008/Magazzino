"""Feed di aggiornamento (Fase 13 completa) — rotte ``/update/...``.

Il server web dell'app serve il manifest firmato e l'installer della
versione più recente:

- ``GET /update/manifest.json`` → il file ``manifest.json`` della cartella
  rilasci (prodotto e firmato da ``firme/firma_manifest.py``);
- ``GET /update/{nome}`` → l'installer, SOLO se il nome corrisponde
  ``MagazzinoProfili-<X.Y.Z>.exe`` (nessun altro nome, nessun listing,
  nessuna path traversal).

Se la cartella rilasci non esiste o è vuota il manifest restituisce 404:
l'app desktop tratta il feed assente come "nessun aggiornamento" e
continua a funzionare (procedura di recovery in
``services.aggiornamenti.testo_recupero``).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

# Unica forma di nome accettata per i file serviti da /update/{nome}.
NOME_INSTALLER = re.compile(r"MagazzinoProfili-[0-9]+\.[0-9]+\.[0-9]+\.exe$")


def crea_router(cartella_rilasci: str | Path) -> APIRouter:
    """Costruisce le rotte del feed su una cartella rilasci determinata."""
    cartella = Path(cartella_rilasci).resolve()

    def _assente(motivo: str) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": motivo})

    router = APIRouter()

    @router.get(
        "/update/manifest.json", include_in_schema=False, response_model=None
    )
    def manifest() -> FileResponse | JSONResponse:
        file = cartella / "manifest.json"
        if not file.is_file():
            return _assente("Nessun aggiornamento pubblicato.")
        return FileResponse(file, media_type="application/json")

    @router.get("/update/{nome}", include_in_schema=False, response_model=None)
    def installer(nome: str) -> FileResponse | JSONResponse:
        if not NOME_INSTALLER.fullmatch(nome):
            return _assente("Risorsa non trovata.")
        file = (cartella / nome).resolve()
        # Doppia tutela anti path traversal: la regex sopra esclude già
        # qualsiasi separatore, qui si verifica anche l'inclusione.
        if os.path.commonpath([str(cartella), str(file)]) != str(cartella):
            return _assente("Risorsa non trovata.")
        if not file.is_file():
            return _assente("Risorsa non trovata.")
        return FileResponse(file, media_type="application/octet-stream")

    return router
