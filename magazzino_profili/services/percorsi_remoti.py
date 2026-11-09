"""Allowlist del ponte: nessuna chiamata a URL o percorsi arbitrari sul PC."""
import re
from urllib.parse import urlsplit,unquote


def percorso_api_consentito(metodo,percorso):
    if not isinstance(percorso,str) or len(percorso)>2000:return False
    u=urlsplit(percorso)
    if u.scheme or u.netloc or u.fragment or any(ord(c)<32 for c in unquote(percorso)):return False
    if metodo=='POST':return u.path in ('/api/pezzi','/api/scarico','/api/carico','/api/scansione','/api/telefono/ping')
    if metodo!='GET':return False
    return u.path in ('/api/salute','/api/profili') or bool(re.fullmatch(
        r'/api/(?:pezzi/[A-Za-z0-9%-]+|barcode/[A-Za-z0-9%-]+/immagine|profili/[A-Za-z0-9%-]+/sezione|scansioni/[0-9]+)',u.path))
