"""Build locale in una destinazione NUOVA: non modifica dati, config o release esistenti."""
import argparse
import ast
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destinazione", required=True, type=Path)
    args = parser.parse_args()
    radice = Path(__file__).resolve().parents[1]
    destinazione = args.destinazione.resolve()
    if destinazione.exists():
        raise SystemExit("La destinazione esiste già: scegliere una cartella nuova")
    versione = re.search(r'__version__ = "([0-9]+\.[0-9]+\.[0-9]+)"',
        (radice / "magazzino_profili/__init__.py").read_text(encoding="utf-8")).group(1)
    for file in (radice / "magazzino_profili").rglob("*.py"):
        ast.parse(file.read_text(encoding="utf-8-sig"))
    destinazione.mkdir(parents=True)
    numeri=tuple(map(int,versione.split('.')))+(0,)
    from PyInstaller.utils.win32.versioninfo import VSVersionInfo,FixedFileInfo,StringFileInfo,StringTable,StringStruct
    metadati=VSVersionInfo(ffi=FixedFileInfo(filevers=numeri,prodvers=numeri,mask=0x3f,flags=0,OS=0x40004,fileType=1,subtype=0,date=(0,0)),
        kids=[StringFileInfo([StringTable('041004B0',[StringStruct('FileVersion',versione+'.0'),StringStruct('ProductVersion',versione+'.0'),StringStruct('ProductName','Magazzino Profili')])])])
    risorsa_versione=destinazione/'version_info.txt';risorsa_versione.write_text(str(metadati),encoding='utf-8')
    ambiente = os.environ.copy()
    ambiente['MAGAZZINO_VERSION_INFO']=str(risorsa_versione)
    if os.name == "nt":
        # Evita DLL omonime di altri software nel PATH (es. ICU di Poppler).
        windows = Path(os.environ.get("WINDIR", "C:/Windows"))
        ambiente["PATH"] = os.pathsep.join(map(str, (
            Path(sys.executable).parent, Path(sys.base_prefix),
            Path(sys.base_prefix) / "DLLs", windows / "System32", windows)))
    with (destinazione / "compilazione.log").open("w", encoding="utf-8") as log:
        subprocess.run([sys.executable, "-B", "-m", "PyInstaller", "--workpath", str(destinazione / "lavoro"),
            "--distpath", str(destinazione / "programma"), str(radice / "MagazzinoProfili.spec")],
            cwd=radice, env=ambiente, stdout=log, stderr=subprocess.STDOUT, check=True)
        nome_cartella = "MagazzinoProfili-" + versione
        cartella = destinazione / nome_cartella
        # Spostamento limitato al nuovo output di questa compilazione, mai alle release dell'utente.
        origine = (destinazione / "programma/MagazzinoProfili").resolve()
        assert origine.is_relative_to(destinazione) and cartella.resolve().is_relative_to(destinazione)
        origine.rename(cartella)
        # Il percorso predefinito in config.example.toml è accanto al programma.
        # La copia incorporata resta disponibile anche come risorsa frozen.
        shutil.copytree(radice / "catalogo_immagini", cartella / "catalogo_immagini",
                        ignore=shutil.ignore_patterns(".gitkeep", "__pycache__"))
        shutil.copy2(radice/'config.example.toml',cartella/'config.example.toml')
        codice = (radice / "tools/launcher_windows.cs").read_text(encoding="utf-8")
        codice = codice.replace("@VERSIONE@", versione).replace("@CARTELLA@", nome_cartella)
        sorgente = destinazione / "avvio.cs"
        sorgente.write_text(codice, encoding="utf-8-sig")
        compilatore = Path(os.environ.get("WINDIR", "C:/Windows")) / "Microsoft.NET/Framework/v4.0.30319/csc.exe"
        if not compilatore.is_file():
            raise SystemExit("Compilatore C# locale assente. La cartella programma è stata creata; nessuna installazione globale eseguita")
        subprocess.run([str(compilatore), "/nologo", "/target:winexe", "/platform:anycpu",
            "/reference:System.Windows.Forms.dll", "/win32icon:" + str(radice / "icona.ico"),
            "/out:" + str(destinazione / (nome_cartella + ".exe")), str(sorgente)],
            stdout=log, stderr=subprocess.STDOUT, check=True)
    print("Build creata:", destinazione)


if __name__ == "__main__":
    main()
