"""Prueft die Escape-Notbremse an allen drei kritischen Stellen -
ohne echte API und ohne echte Tastatur."""
import os
import threading
import time

os.environ["JARVIS_SIMPLE_INPUT"] = "1"

from jarvis import config
from jarvis.brain import AbbruchError, Brain

config.MODELS = ["test/modell"]
config.RETRIES_429 = 3
# Brain() ohne eigenen Systemprompt archiviert - und dieser Test stellt fuenf
# Fragen. Die standen danach im echten Gespraechsarchiv und tauchten mitten
# in einem echten Gespraech wieder auf: "Erzähl mir was", "Hallo",
# "Wie spaet?", "Test", "neue Frage". Beim Lauf ueber pruefen.py setzt das
# schon die Umgebung; hier steht es fuer den Fall, dass jemand dieses
# Skript einzeln aufruft.
config.ARCHIV_AN = False


class LahmerStream:
    """Ein Stream, der endlos tropft - wie ein hängendes Modell.
    Zaehlt mit, wie oft er nach dem Schliessen noch gelesen wurde."""

    def __init__(self) -> None:
        self.geschlossen = False
        self.gelesen = 0

    def close(self) -> None:
        self.geschlossen = True

    def __iter__(self):
        while True:
            if self.geschlossen:
                raise ConnectionError("Verbindung geschlossen")
            self.gelesen += 1
            time.sleep(0.1)
            yield type("Chunk", (), {"choices": []})()


def nach(sekunden: float, fn) -> None:
    threading.Timer(sekunden, fn).start()


print("=== 1. Abbruch während das Modell antwortet ===")
brain = Brain()
stream = LahmerStream()
brain._einmal = lambda m: brain._merken(stream)
nach(1.0, brain.abbrechen)
start = time.monotonic()
antwort = brain.ask("Erzähl mir was")
dauer = time.monotonic() - start
print(f"   nach {dauer:.1f}s beendet, Antwort={antwort!r}")
print(f"   Verbindung geschlossen: {stream.geschlossen}")
print(f"   Verlauf danach: {len(brain.history)} Eintraege (muss 0 sein)")
assert antwort == "" and stream.geschlossen and len(brain.history) == 0
assert dauer < 3, "haette sofort abbrechen müssen"

print("\n=== 2. Abbruch während der Wartepause bei belegtem Modell ===")
brain2 = Brain()


def immer_belegt(m):
    raise RuntimeError("Error code: 429 - Too Many Requests")


brain2._einmal = immer_belegt
nach(1.0, brain2.abbrechen)
start = time.monotonic()
antwort = brain2.ask("Hallo")
dauer = time.monotonic() - start
print(f"   nach {dauer:.1f}s beendet (ohne Abbruch wären es 18s), "
      f"Antwort={antwort!r}")
assert dauer < 5, f"hat {dauer:.1f}s gebraucht"

print("\n=== 3. Abbruch zwischen zwei Werkzeug-Runden ===")
brain3 = Brain()
runden = []


class WerkzeugStream:
    def close(self): ...

    def __iter__(self):
        runden.append(1)
        time.sleep(0.4)                 # eine echte Runde dauert Sekunden
        teil = type("F", (), {"name": "get_time", "arguments": "{}"})()
        tc = type("T", (), {"index": 0, "id": "abc", "function": teil})()
        delta = type("D", (), {"content": None, "tool_calls": [tc]})()
        yield type("C", (), {"choices": [type("X", (), {"delta": delta})()]})()


brain3._einmal = lambda m: brain3._merken(WerkzeugStream())
nach(0.9, brain3.abbrechen)
antwort = brain3.ask("Wie spaet?")
print(f"   Runden gelaufen: {len(runden)} (ohne Abbruch wären es 5)")
print(f"   Antwort={antwort!r}, Verlauf={len(brain3.history)}")
assert antwort == "" and len(brain3.history) == 0
assert len(runden) < 5

print("\n=== 4. Ohne Abbruch laeuft alles normal weiter ===")
brain4 = Brain()


class KurzerStream:
    def close(self): ...

    def __iter__(self):
        for stueck in ["Alles", " in", " Ordnung."]:
            delta = type("D", (), {"content": stueck, "tool_calls": None})()
            yield type("C", (), {"choices": [type("X", (), {"delta": delta})()]})()


brain4._einmal = lambda m: brain4._merken(KurzerStream())
antwort = brain4.ask("Test")
print(f"   Antwort={antwort!r}, Verlauf={len(brain4.history)} Eintraege")
assert antwort == "Alles in Ordnung." and len(brain4.history) == 2

print("\n=== 5. Abbruch waehrend des Verbindungsaufbaus (der gemeldete Fall) ===")
# Hier gibt es noch keinen Stream zum Schliessen - frueher lief Escape ins Leere
brain5 = Brain()
brain5.history.append({"role": "user", "content": "alte Frage"})
brain5.history.append({"role": "assistant", "content": "alte Antwort"})


def haengt_im_aufbau(m):
    time.sleep(30)                      # wie ein Server, der nicht antwortet
    raise RuntimeError("zu spaet")


brain5._einmal = haengt_im_aufbau

fertig = threading.Event()
ergebnis = {}


def arbeiten():
    ergebnis["antwort"] = brain5.ask("neue Frage")
    fertig.set()


threading.Thread(target=arbeiten, daemon=True).start()
time.sleep(0.5)
start = time.monotonic()
brain5.abbrechen()                      # das macht die Escape-Taste
dauer = time.monotonic() - start
print(f"   abbrechen() kehrte nach {dauer:.3f}s zurueck (Eingabe sofort frei)")
print(f"   Verlauf: {len(brain5.history)} Eintraege "
      f"(die 2 alten muessen stehen, die neue Frage weg)")
assert dauer < 0.5, "abbrechen() darf nicht blockieren"
assert len(brain5.history) == 2, brain5.history
assert brain5.history[0]["content"] == "alte Frage"

print("   warte, ob der abgehaengte Aufruf noch Unfug macht ...")
fertig.wait(timeout=35)
print(f"   Verlauf danach: {len(brain5.history)} Eintraege, "
      f"Antwort={ergebnis.get('antwort')!r}")
assert len(brain5.history) == 2, "der Zombie hat den Verlauf angefasst"
assert ergebnis.get("antwort") == ""

print("\n=== 6. Abbruch waehrend ein Werkzeug laeuft ===")
# Die Eingabe ist sofort frei und das Ergebnis wird verworfen - aber ein
# laufendes Werkzeug arbeitete stur zu Ende. Gemessen bis zu zwei Sekunden,
# bei vielen erfolglosen Bildpruefungen laenger. Auf einem Rechner mit vier
# Kernen ist das spuerbar, deshalb horchen die langen Schleifen aufs Signal.
import threading
import time as _zeit

from jarvis import tools

tools.anfrage_beginnt()
print(f"   Signal am Anfang gesetzt: {tools.abgebrochen()} (muss False sein)")
assert not tools.abgebrochen()

# ZUERST das Zuverlaessige, ohne Netz: die Wartestelle selbst. Wenn das
# Signal steht, muss _abbruch.wait() sofort zurueckkommen statt die volle
# Sekunde zu warten. Daran ist nichts zu wackeln.
tools.abbrechen()
start = _zeit.perf_counter()
sofort = tools._abbruch.wait(1.0)
gewartet = _zeit.perf_counter() - start
print(f"   Wartestelle kam nach {gewartet * 1000:.0f} ms zurueck "
      f"(Signal erkannt: {sofort})")
assert sofort and gewartet < 0.2, "Die Wartestelle horcht nicht aufs Signal"
tools.anfrage_beginnt()

dauer = {}


def langes_werkzeug() -> None:
    start = _zeit.perf_counter()
    # ort_info wartet zwischen zwei Kartenabfragen eine Sekunde - so
    # verlangt es OpenStreetMap. Genau dort soll der Abbruch greifen.
    tools.ort_info(von="Köln", nach="München")
    dauer["mit_abbruch"] = _zeit.perf_counter() - start


# Und dann der ganze Weg - aber DREI Anlaeufe, und einer muss reichen.
#
# Gemessen im Reihenlauf: "Der Abbruch hat das Werkzeug nicht verkuerzt",
# allein aufgerufen ging derselbe Test durch. Kein Rueckschritt im Code -
# hier werden ZWEI echte Netzabfragen gegeneinander gehalten, und unter
# Last schwankt die Antwortzeit von Nominatim um mehr als die Sekunde, um
# die es geht. Ein Test, der die Leitung misst und das Ergebnis dem Code
# anlastet, schickt die Fehlersuche in die falsche Richtung.
gelungen = False
for anlauf in (1, 2, 3):
    tools.anfrage_beginnt()
    dauer.clear()
    faden = threading.Thread(target=langes_werkzeug, daemon=True)
    faden.start()
    _zeit.sleep(0.3)
    tools.abbrechen()
    faden.join(timeout=10)
    mit = dauer.get("mit_abbruch", 99)

    tools.anfrage_beginnt()
    start = _zeit.perf_counter()
    tools.ort_info(von="Köln", nach="München")
    normal = _zeit.perf_counter() - start
    print(f"   Anlauf {anlauf}: mit Abbruch {mit:.2f}s, ohne {normal:.2f}s")
    if mit < normal:
        gelungen = True
        break

assert gelungen, "Der Abbruch hat das Werkzeug in drei Anlaeufen nicht verkuerzt"

tools.anfrage_beginnt()
print(f"   neue Anfrage loescht das Signal: {not tools.abgebrochen()}")
assert not tools.abgebrochen()

print("\nAlle sechs Fälle bestanden.")
