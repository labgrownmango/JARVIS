"""Findet Jarvis ein Programm, das dasteht - und sagt er sonst das Richtige?

Der Anlass kam von Mini-Jost, drei Antworten hintereinander:

    "oeffne youtube in brave.exe"  ->  "Brave ist nicht installiert."
    "oeffne brave"                 ->  "Brave ist auf diesem Rechner nicht
                                        installiert."
    "oeffne youtube.com"           ->  "Ich kann keine Webseiten direkt
                                        oeffnen."

Brave lief zu dem Zeitpunkt. Zwei verschiedene Fehler steckten darin:

1. Das angehaengte ".exe" wurde nirgends abgeschnitten. Im Startmenue heisst
   der Eintrag "Brave", nicht "Brave.exe" - die Teilwortsuche lief ins Leere.
   Gemessen auf diesem Rechner: "msedge" wurde gefunden, "msedge.exe" nicht.

2. Brave installiert sich haeufig NUR ins Benutzerprofil. Dann steht es
   weder im Suchpfad noch im systemweiten Startmenue, und in den App Paths
   nur, wenn das Installationsprogramm sich dort eingetragen hat.

Die dritte Antwort war etwas anderes: der alte Wortlaut von vor dem Umbau.
Der Rechner lief noch mit einer aelteren tools.py, die _seite_oeffnen gar
nicht hatte. Dagegen hilft kein Test hier, nur das Paket - aber der letzte
Abschnitt haelt wenigstens fest, dass die Faehigkeit da ist.

Braucht kein Netz und startet nichts.
"""
import os
from pathlib import Path

from jarvis import tools

fehler = 0


def pruefe(bedingung: bool, text: str, zusatz: str = "") -> None:
    global fehler
    fehler += not bedingung
    print(f"  {'ok    ' if bedingung else 'FEHLER'} {text}")
    if not bedingung and zusatz:
        print(f"         {zusatz}")


print("=== Ein angehaengtes .exe darf nichts kaputtmachen ===")
# Ein Programm, das es auf JEDEM Windows gibt - sonst prueft der Test nichts.
for kurz in ("notepad", "msedge", "explorer"):
    ohne = tools._programm_finden(kurz)
    if ohne is None:
        print(f"  ~~     {kurz} gibt es hier nicht - uebersprungen")
        continue
    mit = tools._programm_finden(kurz + ".exe")
    pruefe(mit is not None, f"{kurz}.exe wird ueberhaupt gefunden")
    pruefe(mit == ohne, f"{kurz}.exe findet dasselbe wie {kurz}",
           f"ohne: {ohne}   mit: {mit}")

print("\n=== Die Rangfolge bleibt trotzdem heil ===")
# "editor" darf nicht den Registrierungs-Editor treffen, nur weil der das
# Wort zufaellig enthaelt. Das war der Grund fuer KURZ_EXE.
treffer = tools._programm_finden("editor")
pruefe(treffer is not None and "notepad" in treffer[1].lower(),
       f"'editor' bleibt der Editor: {treffer}")

print("\n=== Die Browserorte sind sauber aufgeschrieben ===")
for name, orte in tools._BROWSERORTE.items():
    pruefe(bool(orte), f"{name}: mindestens ein Ort")
    for ort in orte:
        aufgeloest = os.path.expandvars(ort)
        # Ein "%" ueberlebt nur, wenn die Umgebungsvariable nicht existiert -
        # dann zeigt der Eintrag nirgendwohin und faellt nie auf.
        pruefe("%" not in aufgeloest,
               f"{name}: {Path(ort).parent.name} loest sich auf",
               f"stehengeblieben: {aufgeloest}")
        pruefe(aufgeloest.lower().endswith(".exe"),
               f"{name}: zeigt auf eine .exe", aufgeloest)

print("\n=== Ein Browser, der hier wirklich liegt ===")
# Edge ist auf jedem Windows da. Wenn die Tabelle fuer IHN stimmt, ist die
# Form der Eintraege richtig - fuer Brave kann dieser Rechner es nicht
# pruefen, da ist keines installiert.
edge = [p for p in (os.path.expandvars(o) for o in tools._BROWSERORTE["msedge"])
        if Path(p).is_file()]
if edge:
    pruefe(True, f"Edge liegt, wo die Tabelle es sagt: {edge[0]}")
else:
    print("  ~~     Edge an keinem der Orte - uebersprungen")

print("\n=== Ein unbekanntes Programm wird nicht erfunden ===")
pruefe(tools._programm_finden("gibtesnichtxyz") is None,
       "erfundener Name gibt None")

print("\n=== Mit Adresse: kein 'kann ich nicht' mehr ===")
# Der alte Wortlaut lautete "Das Oeffnen einer Internetseite liegt
# ausserhalb meiner Befugnisse." Genau das soll nicht zurueckkommen.
geoeffnet = []
echt = os.startfile if hasattr(os, "startfile") else None
try:
    os.startfile = lambda ziel, *a, **k: geoeffnet.append(ziel)  # type: ignore
    antwort = tools._seite_oeffnen("gibtesnichtxyz", "youtube.com")
    pruefe("standardbrowser" in antwort.lower(),
           f"weicht auf den Standardbrowser aus: {antwort}")
    pruefe(geoeffnet and geoeffnet[0] == "https://youtube.com",
           f"und zwar mit der ergaenzten Adresse: {geoeffnet}")
finally:
    if echt is not None:
        os.startfile = echt  # type: ignore

print("\n=== Eine Befehlszeile ist kein Programmpfad ===")
# APPS["browser"] lautet 'start "" "https://www.google.de"'. Frueher wurde
# daraus Popen(['start "" "https://www.google.de"', 'https://youtube.com'])
# - ein Programm dieses Namens gibt es nicht, der Aufruf scheiterte, und der
# Standardbrowser sprang mit der GOOGLE-Adresse ein. Gemeldet von Mini-Jost:
# "der Browser wurde gestartet und fuehrt youtube.com aus" - und der Browser
# zeigte etwas anderes.
import subprocess  # noqa: E402

gestartet: list = []
echt_popen = tools.subprocess.Popen
echt_start = os.startfile if hasattr(os, "startfile") else None


class _Attrappe:
    def __init__(self, *a, **k):
        gestartet.append(("Popen", a, k))


try:
    tools.subprocess.Popen = _Attrappe  # type: ignore
    os.startfile = lambda z, *a, **k: gestartet.append(("startfile", z))  # type: ignore

    for name in ("browser", "gibtesnichtxyz"):
        gestartet.clear()
        antwort = tools.open_app(name, "youtube.com")
        wege = [w[0] for w in gestartet]
        pruefe(wege == ["startfile"],
               f"{name!r}+Adresse geht ueber den Standardbrowser: {wege}")
        pruefe(gestartet and gestartet[0][1] == "https://youtube.com",
               f"{name!r}: und zwar mit youtube.com, nicht mit google.de",
               f"{gestartet}")

    # Ein echtes Programm bekommt die Adresse dagegen als Argument.
    if tools._programm_finden("msedge"):
        gestartet.clear()
        tools.open_app("msedge", "youtube.com")
        pruefe(gestartet and gestartet[0][0] == "Popen",
               f"msedge bekommt die Adresse als Argument: {gestartet}")
        if gestartet and gestartet[0][0] == "Popen":
            argumente = gestartet[0][1][0]
            pruefe(isinstance(argumente, list)
                   and str(argumente[0]).lower().endswith(".exe"),
                   f"und das erste Argument ist eine .exe: {argumente[0]!r}")
            pruefe(not gestartet[0][2].get("shell"),
                   "ohne shell=True")
finally:
    tools.subprocess.Popen = echt_popen  # type: ignore
    if echt_start is not None:
        os.startfile = echt_start  # type: ignore

print("\n=== Eine Verknuepfung wird nie mit einer Adresse aufgerufen ===")
# _programm_finden("edge") liefert "Microsoft Edge.lnk", und eine .lnk nimmt
# kein Argument entgegen. Die erste Fassung dieses Tests verlangte deshalb
# den Standardbrowser - das war zu eng gedacht: fuer die gaengigen Browser
# steht die echte .exe in _BROWSERORTE, und die ist der bessere Weg. Geprueft
# wird also die Absicht, nicht der Weg: an Popen geht NIE eine .lnk.
treffer = tools._programm_finden("edge")
if treffer is not None and str(treffer[1]).lower().endswith(".lnk"):
    gestartet.clear()
    echt_start2 = os.startfile
    try:
        tools.subprocess.Popen = _Attrappe  # type: ignore
        os.startfile = lambda z, *a, **k: gestartet.append(("startfile", z))  # type: ignore
        antwort = tools.open_app("edge", "youtube.com")
        pruefe(bool(gestartet), f"etwas ist passiert: {antwort}")
        if gestartet and gestartet[0][0] == "Popen":
            erstes = str(gestartet[0][1][0][0]).lower()
            pruefe(not erstes.endswith(".lnk"),
                   f"keine .lnk an Popen: {erstes}")
            pruefe(erstes.endswith(".exe"),
                   f"sondern die echte .exe: {erstes}")
        else:
            pruefe(gestartet[0][0] == "startfile",
                   f"sonst der Standardbrowser: {gestartet}")
    finally:
        tools.subprocess.Popen = echt_popen  # type: ignore
        os.startfile = echt_start2  # type: ignore
else:
    print("  ~~     'edge' ist hier keine Verknuepfung - uebersprungen")

print("\n=== Eine Datei, die daliegt, muss noch nicht starten ===")
# Gemeldet von Mini-Jost: dort liegt Brave ZWEIMAL - eine kaputte
# Alt-Installation im Benutzerprofil und eine funktionierende unter
# %ProgramFiles%. Beide bestehen is_file(). Genommen wurde die erste, Popen
# warf WinError 14001 (ungueltige Side-by-Side-Konfiguration), danach sprang
# der Standardbrowser ein - und es sah aus, als waere Brave nicht gefunden
# worden. Dabei war es gefunden, nur die Leiche.
#
# Die Reihenfolge umzudrehen waere ein Pflaster: auf dem naechsten Rechner
# liegt die kaputte Fassung woanders. Geprueft wird deshalb, dass ALLE
# Kandidaten der Reihe nach probiert werden.
LEICHE = r"C:\Windows\System32\notepad.exe"     # existiert, wird "kaputt"
HEIL = r"C:\Windows\System32\xcopy.exe"         # existiert, "startet"

alt_orte = dict(tools._BROWSERORTE)
versuche: list = []


class _ZweiterGeht:
    def __init__(self, befehl, *rest, **kw):
        versuche.append(befehl[0] if isinstance(befehl, list) else befehl)
        if str(befehl[0]).lower() == LEICHE.lower():
            raise OSError(14001, "Ungueltige Side-by-Side-Konfiguration")


if Path(LEICHE).is_file() and Path(HEIL).is_file():
    try:
        tools._BROWSERORTE = dict(alt_orte)
        tools._BROWSERORTE["pruefbrowser"] = (LEICHE, HEIL)
        tools.subprocess.Popen = _ZweiterGeht  # type: ignore
        antwort = tools.open_app("pruefbrowser", "youtube.com")
        print(f"         {antwort}")
        pruefe(len(versuche) == 2,
               f"beide Kandidaten wurden probiert ({len(versuche)})",
               f"{versuche}")
        pruefe(versuche and str(versuche[0]).lower() == LEICHE.lower(),
               "der erste zuerst - die Reihenfolge bleibt")
        pruefe(len(versuche) > 1 and str(versuche[1]).lower() == HEIL.lower(),
               "und nach dem Fehlschlag der zweite")
        pruefe("ist offen mit" in antwort,
               f"die Antwort meldet Erfolg, nicht den Standardbrowser",
               antwort)
    finally:
        tools._BROWSERORTE = alt_orte
        tools.subprocess.Popen = echt_popen  # type: ignore
else:
    print("  ~~     die Testprogramme fehlen - uebersprungen")

print("\n=== Auch hier darf .exe nichts kaputtmachen ===")
# _seite_oeffnen hatte den zweiten, unabhaengigen Teil desselben Fehlers:
# _programm_finden schnitt ".exe" intern ab, der Rueckgriff auf _BROWSERORTE
# fragte aber mit dem ungekuerzten Namen. "oeffne youtube in brave.exe" lief
# deshalb weiter in den Standardbrowser.
#
# Hier laesst sich das an "edge.exe" zeigen: im Startmenue liegt nur eine
# .lnk, die echte msedge.exe steht ausschliesslich in _BROWSERORTE.
if "edge" in tools._BROWSERORTE and tools._browserpfade("edge"):
    for name in ("edge", "edge.exe"):
        versuche.clear()
        gestartet.clear()
        echt_start3 = os.startfile
        try:
            tools.subprocess.Popen = _Attrappe  # type: ignore
            os.startfile = lambda z, *a, **k: gestartet.append(("startfile", z))  # type: ignore
            antwort = tools.open_app(name, "youtube.com")
        finally:
            tools.subprocess.Popen = echt_popen  # type: ignore
            os.startfile = echt_start3  # type: ignore
        wege = [w[0] for w in gestartet]
        pruefe(wege == ["Popen"],
               f"{name!r}: startet den Browser selbst statt auszuweichen",
               f"{wege} - {antwort}")
else:
    print("  ~~     kein Edge an den bekannten Orten - uebersprungen")

print("\n=== Und die Schranke haelt weiter ===")
for schlecht in ("javascript:alert(1)", "file:///C:/Windows", "data:text/html,x"):
    antwort = tools._seite_oeffnen("msedge", schlecht)
    pruefe("nur http und https" in antwort.lower(),
           f"{schlecht} wird abgelehnt", antwort[:80])

print(f"\n  {fehler} Fehler")
raise SystemExit(1 if fehler else 0)
