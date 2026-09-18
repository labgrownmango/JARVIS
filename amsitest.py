"""Ein blockierter Befehl darf sich nicht als fehlende Hardware tarnen.

Dreimal hat der Virenschutz auf diesem Rechner PowerShell-Code abgefangen.
Keiner der Aufrufe war Jarvis' eigener - aber der Schreck war berechtigt:
_powershell() gab bei JEDEM Fehlschlag "" zurueck, und _temperaturen() las
daraus "dieser Rechner hat keinen Sensor" und merkte sich das bis zum
Neustart. Ein einziger abgefangener Aufruf haette Jarvis dauerhaft blind
gemacht, ohne dass es irgendwo aufgefallen waere.

Geprueft wird deshalb der Unterschied, auf den es ankommt: leeres Ergebnis
von einem Befehl, der lief - gegen einen, der gar nicht erst durchkam.
"""
import subprocess

from jarvis import tools

fehler = 0


def pruefe(bedingung: bool, text: str, zusatz: str = "") -> None:
    global fehler
    fehler += not bedingung
    print(f"  {'ok    ' if bedingung else 'FEHLER'} {text}")
    if not bedingung and zusatz:
        print(f"         {zusatz}")


print("=== Der Normalfall bleibt normal ===")
ausgabe, grund = tools._powershell_roh("Write-Output 42")
pruefe(ausgabe == "42", f"Ausgabe kommt an ({ausgabe!r})")
pruefe(grund == "", f"kein Fehlergrund gemeldet ({grund!r})")

print("\n=== Leer, aber gelaufen - das ist eine echte Aussage ===")
ausgabe, grund = tools._powershell_roh("$null")
pruefe(ausgabe == "", "nichts ausgegeben")
pruefe(grund == "", "trotzdem kein Fehlergrund - der Befehl lief ja",
       f"grund={grund!r}")

print("\n=== Gescheitert - das ist KEINE Aussage ueber die Hardware ===")
ausgabe, grund = tools._powershell_roh("throw 'geht nicht'")
pruefe(grund != "", f"Fehlergrund gemeldet ({grund[:60]!r})")

ausgabe, grund = tools._powershell_roh("Start-Sleep -Seconds 30", sekunden=3)
pruefe("Zeitlimit" in grund, f"Zeitlimit wird benannt ({grund!r})")

print("\n=== Der Virenschutz wird als solcher erkannt ===")
# Kein echter Schadcode - nur eine Ausgabe, die klingt wie eine
# AMSI-Meldung. Geprueft wird das Erkennen der Meldung, nicht das Ausloesen.
echt = subprocess.run


def gefaelscht(befehl, **rest):
    class Ergebnis:
        returncode = 1
        stdout = ""
        stderr = ("Dieses Skript enthaelt boesartigen Inhalt und wurde "
                  "von Ihrer Antivirensoftware blockiert.")
    return Ergebnis()


subprocess.run = gefaelscht
try:
    ausgabe, grund = tools._powershell_roh("egal")
    pruefe("blockiert" in grund,
           f"als Blockade erkannt, nicht als leeres Ergebnis ({grund[:70]!r})")

    print("\n=== Und das Wichtigste: nichts Falsches merken ===")
    tools._fest_cache.pop("temperatur_geht", None)
    antwort = tools._temperaturen()
    pruefe("temperatur_geht" not in tools._fest_cache,
           "gemerkt wird nichts - der Befehl kam ja nicht durch",
           f"gemerkt: {tools._fest_cache.get('temperatur_geht')!r}")
    pruefe("blockiert" in antwort.lower(),
           "Jarvis sagt, dass der Befehl blockiert wurde",
           antwort[:120])
    pruefe("keine Temperatur auslesbar" not in antwort,
           "und behauptet NICHT, es gaebe keinen Sensor", antwort[:120])

    tools._fest_cache.pop("gpu", None)
    tools._gpu_werte()
    pruefe("gpu" not in tools._fest_cache,
           "dasselbe bei der Grafikkarte: nichts gemerkt",
           f"gemerkt: {tools._fest_cache.get('gpu')!r}")
finally:
    subprocess.run = echt
    tools._fest_cache.pop("temperatur_geht", None)
    tools._fest_cache.pop("gpu", None)

print("\n=== Gescheiterte Aufrufe sind nachlesbar ===")
pruefe(len(tools._ps_fehler) > 0,
       f"{len(tools._ps_fehler)} Fehlschlaege aufgezeichnet")
pruefe(len(tools._ps_fehler) <= 20, "die Liste waechst nicht unbegrenzt")

print("\n=== Nach der Blockade misst er wieder richtig ===")
# Wichtig: der Zustand von eben darf nicht haengenbleiben.
antwort = tools._temperaturen()
pruefe("blockiert" not in antwort.lower(),
       "mit echtem PowerShell wieder eine normale Antwort", antwort[:110])

print(f"\n  {fehler} Fehler")
raise SystemExit(1 if fehler else 0)
