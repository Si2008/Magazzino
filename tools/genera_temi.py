"""Genera le palette HTML dalla fonte unica ui/tema.py (nessun avvio dell'app)."""
import ast
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]


def palette():
    albero = ast.parse((RADICE / "magazzino_profili/ui/tema.py").read_text(encoding="utf-8"))
    default = {f.target.id: ast.literal_eval(f.value) for n in albero.body
               if isinstance(n, ast.ClassDef) and n.name == "Tema" for f in n.body
               if isinstance(f, ast.AnnAssign) and isinstance(f.value, ast.Constant)}
    return {n.targets[0].id: {**default, **{k.arg: ast.literal_eval(k.value) for k in n.value.keywords}}
        for n in albero.body if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
        and n.targets[0].id in ("CHIARO", "SCURO")}


def css_palette():
    temi = palette()
    def blocco(nome):
        p = temi[nome]
        valori = dict(p)
        valori.update(secondario=p["testo_dim"], tenue=p["carta2"],
                      errore=p["pericolo"], ombra="none")
        valori.update({"accento-tenue": p["accento_vel"], "su-accento": p["accento_inchiostro"],
                       "errore-bg": p["pericolo_vel"], "camera-fondo": p["carta2"],
                       "camera-testo": p["testo"], "camera-secondario": p["testo_dim"]})
        def css(v):
            if v.startswith("rgba"):
                r,g,b,a = (int(x) for x in v[5:-1].split(","))
                return f"rgba({r},{g},{b},{a/255:.5f})"
            return v
        return "\n".join(f"  --{k.replace('_','-')}: {css(v)};" for k,v in valori.items())
    return ("/* Generato da tools/genera_temi.py; fonte: magazzino_profili/ui/tema.py. */\n"
        + ":root { color-scheme: light;\n" + blocco("CHIARO") + "\n}\n"
        + ':root[data-tema="scuro"] { color-scheme: dark;\n' + blocco("SCURO") + "\n}\n"
        + '@media(prefers-color-scheme:dark) { :root:not([data-tema="chiaro"]) { color-scheme: dark;\n'
        + blocco("SCURO") + "\n} }\n")


def main():
    css = css_palette()
    for relativo in ("docs/palette-mockup.css", "magazzino_profili/web/static/palette.css",
                     "public/static/palette.css", "magazzino_profili/web/vercel/public/static/palette.css"):
        (RADICE / relativo).write_text(css, encoding="utf-8")
    # L'anteprima mobile incorpora lo stesso CSS nel proprio iframe srcdoc.
    import html
    preview = RADICE / "anteprima-telefono.html"
    if preview.is_file():
        testo = preview.read_text(encoding="utf-8")
        inizio = testo.find("<style>/* Generato da tools/genera_temi.py")
        if inizio >= 0:
            fine = testo.index("</style>", inizio)
            mobile = (RADICE / "magazzino_profili/web/static/telefono.css").read_text(encoding="utf-8")
            mobile = mobile.replace('@import url("palette.css");', "")
            testo = testo[:inizio] + "<style>" + html.escape(css + mobile, quote=True) + testo[fine:]
            preview.write_text(testo, encoding="utf-8")


if __name__ == "__main__":
    main()
