"""Steht irgendwo eine Portnummer fest eingetippt?

Der Anlass, gemeldet vom zweiten Rechner: "Jarvis Oberflaeche.bat" hatte
8765 dreimal fest stehen, waehrend die Vorgabe inzwischen 80 ist. Folge -
die Laufpruefung griff ins Leere, der Browser oeffnete einen toten Port,
und danach startete ein zweiter Server daneben. Auf JEDEM Rechner.

Die Zahl einfach auszubessern waere ein Pflaster gewesen: sobald 80 belegt
ist, weicht Jarvis auf 8765 aus, und dann stimmt auch die neue Zahl nicht.
Richtig ist, dass die .bat fragt statt zu wissen.

Dieser Test haelt beides fest: dass jarvis.adresse richtig antwortet, und
dass in den .bat-Dateien keine Portnummer und kein Rechnername mehr steht.
Braucht kein Netz.
"""
import re
import socket
from pathlib import Path

from jarvis import adresse, config

WURZEL = Path(__file__).parent
fehler = 0


def pruefe(bedingung: bool, text: str, zusatz: str = "") -> None:
    global fehler
    fehler += not bedingung
    print(f"  {'ok    ' if bedingung else 'FEHLER'} {text}")
    if not bedingung and zusatz:
        print(f"         {zusatz}")


print("=== Die .bat-Dateien kennen keine Portnummer mehr ===")
for pfad in sorted(WURZEL.glob("*.bat")):
    text = pfad.read_text(encoding="utf-8", errors="replace")
    # Nur der ausfuehrbare Teil zaehlt - in Kommentaren (rem) darf die Zahl
    # stehen, dort erklaert sie ja gerade, warum sie nicht mehr im Code ist.
    code = "\n".join(z for z in text.splitlines()
                     if not z.strip().lower().startswith("rem"))
    zahlen = re.findall(r"\b(?:80|8765)\b", code)
    pruefe(not zahlen, f"{pfad.name}: keine feste Portnummer",
           f"gefunden: {zahlen}")

print("\n=== Und keinen Rechnernamen ===")
# "http://jarvis" steht in der hosts-Datei DIESES Rechners. Auf einem
# zweiten zeigt derselbe Name nirgendwohin - oder, wenn "jarvis" ein
# Tailscale-Name ist, auf einen ganz anderen Computer.
for pfad in sorted(WURZEL.glob("*.bat")):
    text = pfad.read_text(encoding="utf-8", errors="replace")
    code = "\n".join(z for z in text.splitlines()
                     if not z.strip().lower().startswith("rem"))
    pruefe("http://jarvis" not in code.lower(),
           f"{pfad.name}: oeffnet nicht http://jarvis",
           "auf einem zweiten Rechner waere das der falsche Computer")

print("\n=== Die Oberflaechen-Datei fragt wirklich nach ===")
bat = WURZEL / "Jarvis Oberflaeche.bat"
if bat.exists():
    text = bat.read_text(encoding="utf-8", errors="replace")
    code = "\n".join(z for z in text.splitlines()
                     if not z.strip().lower().startswith("rem"))
    pruefe("jarvis.adresse" in code, "ruft jarvis.adresse auf")
    pruefe("%ADRESSE%" in code, "benutzt die Antwort auch")
    # cmd reicht den Rueckgabewert aus `for /f ... in (`...`)` nicht
    # verlaesslich nach aussen. Ging es daneben, oeffnete sich der Browser
    # UND ein zweiter Server startete daneben - still und schwer zu finden.
    pruefe("errorlevel" not in code.lower(),
           "verlaesst sich NICHT auf errorlevel nach einer for-Schleife",
           "der Zustand gehoert in die Ausgabe, nicht in den Rueckgabewert")
    pruefe("--zustand" in code, "holt den Zustand aus der Ausgabe")
else:
    print("  ~~     Jarvis Oberflaeche.bat gibt es hier nicht")

print("\n=== --zustand sagt beides in einer Zeile ===")
import subprocess
import sys

lauf = subprocess.run([sys.executable, "-m", "jarvis.adresse", "--zustand"],
                      cwd=WURZEL, capture_output=True, text=True)
zeile = lauf.stdout.strip()
print(f"         {zeile!r}")
teile = zeile.split(" ", 1)
pruefe(len(teile) == 2, "genau zwei Angaben, durch ein Leerzeichen getrennt")
if len(teile) == 2:
    pruefe(teile[0] in ("laeuft", "neu"),
           f"erster Teil ist der Zustand: {teile[0]}")
    pruefe(teile[1].startswith("http://"),
           f"zweiter Teil ist die Adresse: {teile[1]}")
    # Der Rueckgabewert soll dasselbe sagen - nur verlaesst sich die .bat
    # nicht mehr darauf.
    pruefe((lauf.returncode == 0) == (teile[0] == "laeuft"),
           "Rueckgabewert und Ausgabe stimmen ueberein")

print("\n=== Ein belegter Port gilt als belegt ===")
# Der teuerste Fehler dieser Reihe: der laufende Server lauscht auf
# 0.0.0.0, und ein bind() auf 127.0.0.1 ist fuer Windows eine ANDERE
# Adresse - es gelingt also, auch ohne SO_REUSEADDR. Jarvis hielt seinen
# eigenen Port fuer frei, die Startdatei startete einen zweiten Server
# daneben, und danach landete jede Anfrage zufaellig bei einem von beiden.
from jarvis.web import _belegt, _freier_port  # noqa: E402

horcher2 = socket.socket()
horcher2.bind(("0.0.0.0", 0))
belegt2 = horcher2.getsockname()[1]
horcher2.listen(1)
# Ein zweiter, freier Port als Ausweichziel. Die erste Fassung dieses Tests
# setzte BEIDE auf den belegten - dann gibt es gar keinen freien, und dass
# _freier_port den Wunsch zurueckgibt, ist richtig so (uvicorn scheitert
# dann hoerbar, statt still danebenzustarten). Das war meine falsche
# Erwartung, nicht der Fehler des Codes.
frei = socket.socket()
frei.bind(("127.0.0.1", 0))
freier_port = frei.getsockname()[1]
frei.close()

try:
    pruefe(_belegt(belegt2), f"erkennt den Horcher auf 0.0.0.0:{belegt2}")
    pruefe(not _belegt(freier_port), f"und {freier_port} als frei")
    alt_p, alt_a = config.WEB_PORT, config.WEB_PORT_AUSWEICH
    config.WEB_PORT, config.WEB_PORT_AUSWEICH = belegt2, freier_port
    try:
        gewaehlt = _freier_port(belegt2)
        pruefe(gewaehlt == freier_port,
               f"weicht auf den freien Port aus ({gewaehlt})",
               "sonst startete ein zweiter Server neben dem laufenden")
    finally:
        config.WEB_PORT, config.WEB_PORT_AUSWEICH = alt_p, alt_a
finally:
    horcher2.close()

print("\n=== Der laufende Port wird erkannt ===")
# Ein Horcher auf einem freien Port - dann muss laufender_port() ihn finden.
horcher = socket.socket()
horcher.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
horcher.bind(("127.0.0.1", 0))
belegt = horcher.getsockname()[1]
horcher.listen(1)

alt_port, alt_ausweich = config.WEB_PORT, config.WEB_PORT_AUSWEICH
try:
    config.WEB_PORT = belegt
    pruefe(adresse.laufender_port() == belegt,
           f"findet den Horcher auf {belegt}")
    pruefe(adresse.adresse() == f"http://127.0.0.1:{belegt}",
           f"und baut die Adresse: {adresse.adresse()}")

    # Jetzt einer, auf dem niemand lauscht
    horcher.close()
    config.WEB_PORT, config.WEB_PORT_AUSWEICH = belegt, belegt
    pruefe(adresse.laufender_port() is None,
           "erkennt, dass niemand lauscht")
finally:
    horcher.close()
    config.WEB_PORT, config.WEB_PORT_AUSWEICH = alt_port, alt_ausweich

print("\n=== Port 80 kommt ohne Nummer in der Adresse ===")
pruefe(adresse.adresse(80) == "http://127.0.0.1",
       f"80 ohne Nummer: {adresse.adresse(80)}")
pruefe(adresse.adresse(8765) == "http://127.0.0.1:8765",
       f"8765 mit Nummer: {adresse.adresse(8765)}")

print("\n=== Fuer diesen Rechner immer 127.0.0.1 ===")
pruefe("127.0.0.1" in adresse.adresse(80, fuer_diesen_rechner=True),
       "der Kurzname wird nicht benutzt, wo er schaden koennte")

print(f"\n  {fehler} Fehler")
raise SystemExit(1 if fehler else 0)
