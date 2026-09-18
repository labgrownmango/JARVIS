"""Prüft die Rückfragen: Auswahlfrage, Freigabe, Zeitablauf, und ob ein
Agent wirklich wartet."""
import threading
import time

from jarvis import config, rueckfrage, tools

print("=== Auswahlfrage ===")
antwort = {}


def fragen_stellen():
    antwort["wert"] = rueckfrage.stellen(
        "Womit soll ich die Datei öffnen?",
        ["Editor", "Browser", "Standardprogramm"], von="Mk 1")


t = threading.Thread(target=fragen_stellen, daemon=True)
t.start()
time.sleep(0.4)

offen = rueckfrage.offene()
print(f"  offen: {len(offen)}")
f = offen[0]
print(f"  von {f.von}: {f.text}")
print(f"  Optionen: {f.optionen}  (plus eigene Antwort)")
print(f"  Rest: {f.rest:.0f}s von {f.zeitlimit:.0f}s")
assert f.art == rueckfrage.FRAGE

print("  -> es wird 'Editor' geantwortet")
rueckfrage.beantworten(f.id, "Editor")
t.join(3)
print(f"  Der Frager bekam: {antwort['wert']!r}")
assert antwort["wert"] == "Editor"
assert not rueckfrage.offene(), "Frage haengt noch"

print("\n=== Eigene Antwort statt Vorschlag ===")
antwort.clear()
t = threading.Thread(target=fragen_stellen, daemon=True)
t.start()
time.sleep(0.3)
rueckfrage.beantworten(rueckfrage.offene()[0].id, "Mit Notepad++, bitte")
t.join(3)
print(f"  bekam: {antwort['wert']!r}")

print("\n=== Freigabe: erlaubt ===")
erlaubt = {}


def freigabe_holen():
    erlaubt["wert"] = rueckfrage.genehmigen(
        "notepad.exe mit Gewalt beenden (2 Prozesse)",
        "Das Programm bekommt keine Gelegenheit mehr zu speichern.",
        von="Mk 1")


t = threading.Thread(target=freigabe_holen, daemon=True)
t.start()
time.sleep(0.3)
f = rueckfrage.offene()[0]
print(f"  {f.text}")
print(f"  Folgen: {f.auswirkungen}")
print(f"  Optionen: {f.optionen}")
assert f.art == rueckfrage.GENEHMIGUNG
rueckfrage.beantworten(f.id, "Einmal erlauben")
t.join(3)
print(f"  Ergebnis: {erlaubt['wert']}")
assert erlaubt["wert"] is True

print("\n=== Freigabe: abgelehnt ===")
erlaubt.clear()
t = threading.Thread(target=freigabe_holen, daemon=True)
t.start()
time.sleep(0.3)
rueckfrage.beantworten(rueckfrage.offene()[0].id, "Ablehnen")
t.join(3)
print(f"  Ergebnis: {erlaubt['wert']}")
assert erlaubt["wert"] is False

print("\n=== Niemand antwortet: was gilt dann? ===")
alt = config.RUECKFRAGE_ZEITLIMIT
config.RUECKFRAGE_ZEITLIMIT = 1.5
erlaubt.clear()
start = time.perf_counter()
t = threading.Thread(target=freigabe_holen, daemon=True)
t.start()
t.join(6)
print(f"  nach {time.perf_counter()-start:.1f}s: {erlaubt['wert']} "
      f"(Ablehnung ist die sichere Seite)")
assert erlaubt["wert"] is False

antwort.clear()
t = threading.Thread(target=fragen_stellen, daemon=True)
t.start()
t.join(6)
print(f"  Auswahlfrage ohne Antwort: {antwort['wert']!r}")
config.RUECKFRAGE_ZEITLIMIT = alt

print("\n=== Das Werkzeug, wie das Modell es sieht ===")
def spaeter():
    time.sleep(0.6)
    offen = rueckfrage.offene()
    if offen:
        rueckfrage.beantworten(offen[0].id, "Ja, mach das")


threading.Thread(target=spaeter, daemon=True).start()
print(" ", tools.ask_user("Soll ich fortfahren?", "Ja, mach das|Lieber nicht"))

print("\n=== Freigabe ist abschaltbar ===")
config.FREIGABE_NOETIG = False
print(f"  ohne Freigabepflicht: {tools.freigabe('irgendwas', 'egal')}")
config.FREIGABE_NOETIG = True

print("\nFertig.")
