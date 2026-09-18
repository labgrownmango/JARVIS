"""Steht in requirements.txt wirklich alles, was der Code importiert?

Der Anlass: auf einem frischen Rechner scheiterte der Start an
"No module named 'fastapi'" - und danach an zehn weiteren. Die Liste war
ueber Monate auseinandergelaufen, weil auf dem Entwicklungsrechner von Hand
nachinstalliert wurde. Gemerkt hat es niemand, weil dort ja alles lag.

Dieser Test sammelt alle Importe ein, filtert Standardbibliothek und eigene
Module heraus und vergleicht mit der Liste. Er braucht kein Netz und
nichts installiert - er liest nur den Code.
"""
import ast
import sys
from pathlib import Path

WURZEL = Path(__file__).parent
fehler = 0

# Importname -> Name auf PyPI, wo sie sich unterscheiden
PAKETNAME = {
    "win32api": "pywin32", "win32com": "pywin32", "win32gui": "pywin32",
    "win32con": "pywin32", "win32process": "pywin32", "pythoncom": "pywin32",
    "PIL": "Pillow", "bs4": "beautifulsoup4", "dotenv": "python-dotenv",
    "yaml": "PyYAML", "piper": "piper-tts", "faster_whisper": "faster-whisper",
}

# Nur fuer Tests gebraucht - die muessen nicht in die Liste, damit ein
# Nutzer nicht Testwerkzeug mitinstalliert.
NUR_TESTS = {"pytest"}


def pypi_name(importname: str) -> str:
    return PAKETNAME.get(importname, importname)


def importe_sammeln() -> dict[str, set[str]]:
    eigene = {p.stem for p in (WURZEL / "jarvis").glob("*.py")} | {"jarvis"}
    gefunden: dict[str, set[str]] = {}
    for pfad in list((WURZEL / "jarvis").glob("*.py")) + list(WURZEL.glob("*.py")):
        try:
            baum = ast.parse(pfad.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for knoten in ast.walk(baum):
            namen: list[str] = []
            if isinstance(knoten, ast.Import):
                namen = [a.name.split(".")[0] for a in knoten.names]
            elif isinstance(knoten, ast.ImportFrom):
                if knoten.level:                 # from . import ...
                    continue
                namen = [(knoten.module or "").split(".")[0]]
            for name in namen:
                if (not name or name in eigene
                        or name in sys.stdlib_module_names
                        or name in NUR_TESTS):
                    continue
                gefunden.setdefault(name, set()).add(pfad.name)
    return gefunden


def liste_lesen() -> set[str]:
    namen = set()
    for zeile in (WURZEL / "requirements.txt").read_text(
            encoding="utf-8").splitlines():
        zeile = zeile.split("#")[0].strip()
        if not zeile:
            continue
        name = zeile.split(">")[0].split("=")[0].split("<")[0].strip()
        namen.add(name.lower())
    return namen


print("=== Was der Code importiert ===")
importe = importe_sammeln()
vorhanden = liste_lesen()
print(f"  {len(importe)} fremde Pakete, {len(vorhanden)} Eintraege in der Liste")

print("\n=== Fehlt etwas in requirements.txt? ===")
fehlend = []
for name in sorted(importe):
    paket = pypi_name(name)
    if paket.lower() not in vorhanden and name.lower() not in vorhanden:
        fehlend.append((paket, name, sorted(importe[name])[:3]))

if fehlend:
    fehler += len(fehlend)
    for paket, name, woher in fehlend:
        print(f"  FEHLER {paket:22} (import {name}) - gebraucht in "
              f"{', '.join(woher)}")
else:
    print("  ok     jedes importierte Paket steht in der Liste")

print("\n=== Steht Ueberfluessiges drin? ===")
# Kein Fehler, nur ein Hinweis: manches wird indirekt gebraucht (comtypes
# von pycaw) oder ist Absicht.
benutzt = {pypi_name(n).lower() for n in importe} | {n.lower() for n in importe}
ungenutzt = sorted(v for v in vorhanden if v not in benutzt)
if ungenutzt:
    print(f"  ~~     nicht direkt importiert: {', '.join(ungenutzt)}")
    print("         (kann Absicht sein - etwa tzdata, das nur Daten liefert)")
else:
    print("  ok     nichts Ueberfluessiges")

print("\n=== Die Kernpakete sind wirklich da ===")
# Gegenprobe zur reinen Textpruefung: laesst sich importieren, was der
# Webserver zum Starten braucht?
for name in ("fastapi", "uvicorn", "httpx", "openai", "dotenv", "psutil"):
    try:
        __import__(name)
        print(f"  ok     {name}")
    except ImportError as exc:
        fehler += 1
        print(f"  FEHLER {name} laesst sich nicht importieren: {exc}")

print(f"\n  {fehler} Fehler")
raise SystemExit(1 if fehler else 0)
