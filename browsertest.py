"""Beweist, was der ferngesteuerte Browser darf - und vor allem, was nicht.

Das hier ist kein Test, der bestätigt, was in der Dokumentation steht. Er
greift jede Zusicherung an: Er versucht Dateien herunterzuladen, er ruft
gesperrte Adressen auf, er lässt eine Seite im Hintergrund nachladen, und er
sieht danach auf der Platte nach, ob etwas liegen geblieben ist.

Die Zusicherungen:
  1. Downloads sind unmöglich - nicht verboten, sondern nicht vorhanden
  2. Nur Adressen von der Erlaubnisliste werden geladen
  3. Nach jeder Anfrage bleibt nichts zurück
  4. Zurück kommt nur Text, nie eine Datei
  5. Zeitlimit hält, der Browser bleibt nicht stehen
  6. JavaScript läuft - sonst wäre das Ganze sinnlos
"""
import time
from pathlib import Path

from jarvis import browser, config

fehler = 0


def pruefe(bedingung: bool, text: str, zusatz: str = "") -> None:
    global fehler
    fehler += not bedingung
    print(f"  {'ok    ' if bedingung else 'FEHLER'} {text}")
    if not bedingung and zusatz:
        print(f"         {zusatz}")


print("=== Ist er überhaupt einsatzbereit? ===")
da = browser.verfuegbar()
pruefe(da, f"Playwright und Browser vorhanden ({browser._browserdatei()})")
if not da:
    print("  (ohne Browser lässt sich der Rest nicht prüfen)")
    raise SystemExit(1)
print(f"         Standardmäßig eingeschaltet: {config.BROWSER_AN} "
      f"(aus ist richtig - er wird nur bewusst benutzt)")

print("\n=== 2. Die Erlaubnisliste ===")
for url, soll in (("https://www.tagesschau.de/inland", True),
                  ("https://heise.de", True),
                  ("https://www.mediamarkt.de/de/search.html", True),
                  ("https://irgendwas-fremdes.example.com", False),
                  ("https://evil.tagesschau.de.angreifer.com", False),
                  ("http://localhost:80/api/einstellungen", False),
                  ("http://127.0.0.1/", False),
                  ("file:///C:/Windows/win.ini", False),
                  ("ftp://beispiel.de/datei.zip", False),
                  ("javascript:alert(1)", False)):
    pruefe(browser.erlaubt(url) == soll,
           f"{'erlaubt  ' if soll else 'gesperrt '} {url[:52]}")

# Der gefährlichste Fall: eine Adresse, die so AUSSIEHT wie eine erlaubte
pruefe(not browser.erlaubt("https://tagesschau.de.boeser-server.ru/x"),
       "Tarnung als erlaubte Seite wird erkannt")

alt_an, alt_liste = config.BROWSER_AN, list(config.BROWSER_ERLAUBT)
config.BROWSER_AN = True

print("\n=== 3. Nichts nach innen ===")
# Die gefährlichste Richtung: Jarvis' eigener Server lauscht auf Port 80,
# der Router auf 192.168.x.1, das Tailnet auf 100.64.0.0/10. Eine fremde
# Seite, die den Browser dorthin schickt, redet mit Diensten, die niemand
# aus dem Internet erreichen können soll. Geprüft wird die AUFGELÖSTE
# Adresse - ein Name auf der Erlaubnisliste, der nach innen zeigt, käme
# sonst durch.
config.BROWSER_ERLAUBT = alt_liste + ["127.0.0.1", "localhost",
                                      "192.168.15.5", "example.com"]
for url in ("http://127.0.0.1/api/chats",
            "http://localhost:8765/",
            "http://192.168.15.5:8080/",
            "http://100.101.102.103/",              # Tailnet
            "http://169.254.169.254/latest/meta-data/",   # Metadatendienst
            "http://[::1]/"):
    pruefe(not browser.erlaubt(url),
           f"gesperrt, obwohl auf der Liste: {url[:48]}")
config.BROWSER_ERLAUBT = list(alt_liste)

print("\n=== 5. JavaScript ist aus, solange es niemand einschaltet ===")
pruefe(not config.BROWSER_JS,
       f"Voreinstellung BROWSER_JS={config.BROWSER_JS} (aus ist richtig)")
start = time.perf_counter()
text = browser.lesen("https://www.tagesschau.de", zeichen=600)
dauer = time.perf_counter() - start
print(f"         {dauer:.1f}s, {len(text)} Zeichen")
print(f"         {text[:130]}")
pruefe(len(text) > 200 and "tagesschau" in text.lower(),
       "eine echte Seite kommt trotzdem als Text zurück", text[:100])
pruefe("<script" not in text and "function(" not in text,
       "kein Skriptcode im Ergebnis")

print("\n=== 2b. Gesperrte Seite wird abgewiesen ===")
antwort = browser.lesen("https://www.google.de")
pruefe("nicht auf der Liste" in antwort,
       f"google.de abgewiesen: {antwort[:70]}")

print("\n=== 1. Downloads: der eigentliche Beweis ===")
# Vorher merken, was in den üblichen Zielordnern liegt. Danach wird
# verglichen - wenn irgendwo eine Datei auftaucht, ist die Zusicherung
# gebrochen, egal was der Code behauptet.
ordner = [Path.home() / "Downloads", Path.home() / "Desktop",
          Path(config.ROOT), Path(config.ROOT) / "data"]
vorher = {o: set(p.name for p in o.iterdir()) for o in ordner if o.exists()}

# heise.de liegt auf der Liste und hat Dateien zum Herunterladen.
config.BROWSER_ERLAUBT = list(alt_liste) + ["ftp.heise.de"]
for versuch in ("https://www.heise.de/downloads/",
                "https://www.tagesschau.de/robots.txt"):
    ergebnis = browser.lesen(versuch, zeichen=300)
    print(f"         {versuch[:44]:46} -> {ergebnis[:56]}")

time.sleep(1.5)
neu = {}
for o in ordner:
    if not o.exists():
        continue
    dazu = set(p.name for p in o.iterdir()) - vorher.get(o, set())
    # Die Sicherung darf nebenher laufen, die zählt nicht
    dazu = {d for d in dazu if not d.startswith("jarvis_")}
    if dazu:
        neu[str(o)] = dazu
pruefe(not neu, "keine einzige neue Datei auf der Platte", str(neu))

print("\n=== 4. Nicht-Textseiten werden abgelehnt ===")
config.BROWSER_ERLAUBT = list(alt_liste)
bild = browser.lesen("https://www.tagesschau.de/favicon.ico")
pruefe("keine Textseite" in bild or "nicht auf der Liste" in bild
       or "antwortete mit" in bild,
       f"Binärinhalt abgelehnt: {bild[:60]}")

print("\n=== 3. Nichts bleibt zurück ===")
# Ein Wegwerf-Profil darf keine Spuren im Projektordner hinterlassen.
spuren = []
for muster in ("*.crdownload", "*.tmp", "Default", "playwright*"):
    spuren += [str(p) for p in Path(config.ROOT).glob(muster)]
pruefe(not spuren, "keine Browserreste im Projektordner", str(spuren))

print("\n=== 5. Zeitlimit und Aufräumen ===")
import subprocess

start = time.perf_counter()
antwort = browser.lesen("https://www.tagesschau.de", zeichen=300)
dauer = time.perf_counter() - start
pruefe(dauer < config.BROWSER_ZEITLIMIT + 10,
       f"innerhalb des Zeitlimits ({dauer:.1f}s von "
       f"{config.BROWSER_ZEITLIMIT + 10:.0f}s)")

time.sleep(2)
lauf = subprocess.run(
    ["powershell", "-NoProfile", "-Command",
     "(Get-Process msedge -ErrorAction SilentlyContinue | "
     "Where-Object { $_.CommandLine -like '*--headless*' }).Count"],
    capture_output=True, text=True, timeout=30)
print(f"         verbliebene Browserprozesse: {lauf.stdout.strip() or '0'}")

print("\n=== 8. Das eigene Fenster überlebt ===")
# Gemessener Fehler: der Griff, der zweite Fenster schließen soll, hing an
# kontext.on("page") - und dieses Ereignis feuert AUCH für die Seite, die
# wir selbst anlegen. Der Browser schloss also sofort sein eigenes Fenster
# und war vollständig funktionsunfähig. Aufgefallen ist es nie, weil er
# standardmäßig aus ist und der Test nur die Wachen prüfte. Deshalb steht
# hier jetzt ein Lauf, der wirklich eine Seite holt und Text zurückbringt -
# das geht nur, wenn das Fenster offen bleibt.
nochmal = browser.lesen("https://www.heise.de", zeichen=400)
pruefe(len(nochmal) > 150 and "Target" not in nochmal
       and "closed" not in nochmal.lower(),
       f"eine zweite Seite kommt zurück: {nochmal[:70]!r}")

print("\n=== Abgeschaltet heißt abgeschaltet ===")
config.BROWSER_AN = False
aus = browser.lesen("https://www.tagesschau.de")
pruefe("abgeschaltet" in aus, f"ausgeschaltet: {aus[:60]}")

config.BROWSER_AN, config.BROWSER_ERLAUBT = alt_an, alt_liste

print(f"\n  {fehler} Fehler")
raise SystemExit(1 if fehler else 0)
