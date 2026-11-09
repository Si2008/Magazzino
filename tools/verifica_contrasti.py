"""Misura WCAG sRGB sulle coppie realmente usate dal tema, senza avviare l'app."""
from pathlib import Path
import json
import sys

RADICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RADICE))
from magazzino_profili.ui import tema


def misure():
    risultati = []
    def aggiungi(modo, stato, primo, secondo, minimo=4.5):
        rapporto = tema.rapporto_contrasto(primo, secondo)
        risultati.append(dict(tema=modo, coppia=stato, testo=primo, sfondo=secondo,
            rapporto=round(rapporto, 4), minimo=minimo,
            esito="superato" if rapporto >= minimo else "fallito"))
    for modo, t in (("chiaro", tema.CHIARO), ("scuro", tema.SCURO)):
        for nome in ("testo", "testo_dim", "testo_debole", "accento", "ok", "avviso", "pericolo"):
            for base in ("sfondo", "superficie", "carta", "carta2"):
                aggiungi(modo, nome+" / "+base, getattr(t,nome), getattr(t,base))
        for nome in ("accento", "ok", "avviso", "pericolo"):
            composito = tema.composito_su(getattr(t,nome+"_vel"), t.carta).name()
            for testo in ("testo", "testo_dim", nome):
                aggiungi(modo, testo+" / velo "+nome, getattr(t,testo), composito)
            if nome != "avviso":
                for stato, colore in (("normale", getattr(t,nome)), ("hover", tema.hover_pieno(getattr(t,nome),t))):
                    aggiungi(modo, "pulsante "+nome+" "+stato, getattr(t,nome+"_inchiostro"), colore)
        for base in ("sfondo", "superficie", "carta", "carta2"):
            aggiungi(modo, "bordo campo / "+base, t.bordo_campo, getattr(t,base),3.0)
    return risultati


if __name__ == "__main__":
    righe = misure()
    if len(sys.argv)>1:
        Path(sys.argv[1]).write_text(json.dumps(righe, ensure_ascii=False, indent=2),encoding="utf-8")
    falliti = [r for r in righe if r["esito"] != "superato"]
    print(f"Coppie verificate: {len(righe)}; superate: {len(righe)-len(falliti)}; fallite: {len(falliti)}")
    if falliti:
        print(json.dumps(falliti, ensure_ascii=False))
        sys.exit(1)
