"""Prüft die Sicherung.

Gedächtnis, Gesprächsarchiv und geschriebener Code sind gewachsen, nicht
erzeugt - kein Neuinstallieren bringt sie zurück. Zwei Dinge müssen deshalb
stimmen: dass das Richtige drin ist, und dass das Falsche draußen bleibt.
Eine Sicherung, die 4,2 GB Wikipedia mitschleppt, legt nach zehn Läufen die
Platte still; eine, die die .env mitkopiert, streut das Mailpasswort über
den Rechner.
"""
import tempfile
import zipfile
from pathlib import Path

from jarvis import config, sicherung

fehler = 0

# Der Test schreibt in einen eigenen Ordner. Vorher lief er auf dem echten:
# er legte dort eine Sicherung an und rief dann aufraeumen(behalten=1) auf -
# und damit loeschte ein TESTLAUF alle echten Sicherungen bis auf die
# neueste. Als kurz darauf beim Aufraeumen eines Chats 375 Nachrichten
# verschwanden, war genau die Sicherung weg, die sie enthalten hatte.
#
# Gesichert wird weiterhin aus den echten Daten - nur eben woanders hin.
# Sonst pruefte der Test nicht mehr, was wirklich mitgenommen wird.
TESTORDNER = Path(tempfile.mkdtemp(prefix="jarvis-sicherungstest-"))
sicherung.ORDNER = TESTORDNER
print(f"  (Sicherungen gehen nach {TESTORDNER})\n")


def pruefe(bedingung: bool, text: str, zusatz: str = "") -> None:
    global fehler
    fehler += not bedingung
    print(f"  {'ok    ' if bedingung else 'FEHLER'} {text}")
    if not bedingung and zusatz:
        print(f"         {zusatz}")


print("=== Anlegen ===")
meldung = sicherung.anlegen("Test")
print(f"  {meldung}")
pruefe("Gesichert" in meldung, "eine Sicherung entsteht")

neueste = sorted(sicherung.ORDNER.glob("jarvis_*.zip"))[-1]
with zipfile.ZipFile(neueste) as archiv:
    inhalt = archiv.namelist()
    kaputt = archiv.testzip()
print(f"  {len(inhalt)} Einträge, {neueste.stat().st_size/1024:.0f} KB")
pruefe(kaputt is None, "das Archiv ist heil", str(kaputt))

print("\n=== Das Richtige ist drin ===")
for erwartet in ("data/gedaechtnis.jsonl", "data/verlauf.jsonl"):
    vorhanden = (config.ROOT / erwartet).exists()
    if vorhanden:
        pruefe(erwartet in inhalt, f"{erwartet} gesichert")
    else:
        print(f"  ~~     {erwartet} gibt es hier nicht - übersprungen")

print("\n=== Das Falsche bleibt draußen ===")
# Die Wikipedia ist 4,2 GB gross und jederzeit neu ladbar. Zehn Sicherungen
# davon waeren 42 GB auf einer Platte mit 72 GB frei.
pruefe(not any("zim" in n for n in inhalt), "keine Wikipedia-Datei")
pruefe(not any(n.endswith(".env") for n in inhalt),
       "keine .env - dort steht das Mailpasswort im Klartext")
pruefe(not any("__pycache__" in n for n in inhalt),
       "kein __pycache__ - entsteht beim nächsten Start neu")
pruefe(not any(n.endswith(".pyc") for n in inhalt), "keine .pyc-Dateien")
gross = [n for n in inhalt
         if zipfile.ZipFile(neueste).getinfo(n).file_size > 50_000_000]
pruefe(not gross, "nichts über 50 MB", str(gross))

print("\n=== Es wird aufgeräumt ===")
# Damit es hier etwas zu raeumen GIBT, ohne auf echte Sicherungen
# angewiesen zu sein: zwei leere Archive mit aelteren Namen danebenlegen.
for name in ("jarvis_2020-01-01_0000.zip", "jarvis_2020-01-02_0000.zip"):
    with zipfile.ZipFile(sicherung.ORDNER / name, "w") as leer:
        leer.writestr("leer.txt", "")
vorher = len(list(sicherung.ORDNER.glob("jarvis_*.zip")))
entfernt = sicherung.aufraeumen(behalten=1)
nachher = len(list(sicherung.ORDNER.glob("jarvis_*.zip")))
print(f"  {vorher} -> {nachher} (entfernt: {entfernt})")
pruefe(vorher == 3, f"drei Sicherungen zum Aufräumen da ({vorher})")
pruefe(nachher == 1, "alte Sicherungen werden gelöscht")
pruefe(entfernt == 2, f"und zwar genau die zwei alten ({entfernt})")

print("\n=== Abstand wird eingehalten ===")
pruefe(not sicherung.faellig(),
       "direkt nach einer Sicherung ist keine fällig")
alt = config.SICHERUNG_ABSTAND
config.SICHERUNG_ABSTAND = 0
pruefe(sicherung.faellig(), "mit abgelaufenem Abstand ist eine fällig")
config.SICHERUNG_ABSTAND = alt

aus = config.SICHERUNG_AN
config.SICHERUNG_AN = False
config.SICHERUNG_ABSTAND = 0
pruefe(not sicherung.faellig(), "abgeschaltet heißt abgeschaltet")
config.SICHERUNG_AN, config.SICHERUNG_ABSTAND = aus, alt

print("\n=== Zurückholen fasst nichts an ===")
# Wiederherstellen ist ein Eingriff, den ein Mensch sehen soll, bevor er
# wirkt. Deshalb landet alles in einem eigenen Ordner.
neueste = sorted(sicherung.ORDNER.glob("jarvis_*.zip"))[-1]
gedaechtnis = config.ROOT / "data" / "gedaechtnis.jsonl"
vorher_inhalt = gedaechtnis.read_bytes() if gedaechtnis.exists() else b""
# Auch das Auspacken bleibt im Testordner - sonst waechst data/
# wiederhergestellt/ mit jedem Testlauf um eine Kopie des ganzen Archivs.
antwort = sicherung.zurueckholen(neueste.stem, TESTORDNER / "ausgepackt")
print(f"  {antwort[:100]}")
pruefe("unberuehrt" in antwort, "sagt ausdrücklich, dass nichts ersetzt wurde")
if gedaechtnis.exists():
    pruefe(gedaechtnis.read_bytes() == vorher_inhalt,
           "die laufende Datei ist unverändert")
pruefe("gibt es nicht" in sicherung.zurueckholen("gibtsnicht42"),
       "unbekannte Sicherung wird gemeldet")

print("\n=== Übersicht ===")
print(f"  {sicherung.uebersicht()}")
pruefe("Sicherung" in sicherung.uebersicht(), "die Übersicht sagt etwas")

print(f"\n  {fehler} Fehler")
raise SystemExit(1 if fehler else 0)
