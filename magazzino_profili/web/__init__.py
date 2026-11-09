"""Interfaccia telefono ad accesso libero e privilegi massimi, HTTPS diretto o tunnel HTTPS con origine loopback."""

from .app import crea_app, leggi_sezione_web

__all__ = ["crea_app", "leggi_sezione_web"]
