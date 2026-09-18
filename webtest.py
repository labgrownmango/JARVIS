"""Prüft die Weboberfläche: alle Endpunkte, Werkzeug-Änderung, Chat."""
import json
import time

import httpx

BASIS = "http://127.0.0.1:8765"
c = httpx.Client(base_url=BASIS, timeout=180)

print("=== Endpunkte ===")
for pfad in ["/", "/stil.css", "/jarvis.js", "/api/zustand", "/api/werkzeuge",
             "/api/einstellungen", "/api/agenten", "/api/protokoll",
             "/api/modelle"]:
    r = c.get(pfad)
    print(f"  {r.status_code}  {pfad:24} {len(r.content):>7} Bytes")
    assert r.status_code == 200, pfad

d = c.get("/api/werkzeuge").json()
print(f"\n  Werkzeuge: {d['aktiv']} von {d['gesamt']} aktiv")
print(f"  Erstes: {d['werkzeuge'][0]['name']} mit "
      f"{len(d['werkzeuge'][0]['parameter'])} Parametern")

e = c.get("/api/einstellungen").json()["eintraege"]
print(f"  Einstellungen: {len(e)} Werte, "
      f"{sum(1 for x in e if x['geheim'])} davon geheim")
print(f"  Beispiel: {e[1]['schluessel']} = {e[1]['wert'][:40]}")

print("\n=== Werkzeug abschalten und wieder an ===")
c.put("/api/werkzeuge", json={"aenderungen": {"get_news": {"aktiv": False}}})
nachher = c.get("/api/werkzeuge").json()
print(f"  nach dem Abschalten: {nachher['aktiv']} aktiv")
assert nachher["aktiv"] == d["gesamt"] - 1
c.post("/api/werkzeuge/zuruecksetzen", json={"name": ""})
print(f"  nach dem Zuruecksetzen: {c.get('/api/werkzeuge').json()['aktiv']} aktiv")

print("\n=== Parameter-Standardwert ===")
c.put("/api/werkzeuge", json={"aenderungen": {
    "look_at_screen": {"parameter": {"verzoegerung": {"standard": "5"}}}}})
from jarvis import werkzeugliste
print(f"  Standardwerte fuer look_at_screen: "
      f"{werkzeugliste.standardwerte('look_at_screen')}")
c.post("/api/werkzeuge/zuruecksetzen", json={"name": ""})

print("\n=== Chat ===")
start = time.monotonic()
stuecke, status_gesehen = [], []
with c.stream("POST", "/api/chat", json={"text": "Wie spaet ist es?"}) as r:
    for zeile in r.iter_lines():
        if not zeile.startswith("data: "):
            continue
        n = json.loads(zeile[6:])
        if n["typ"] == "status":
            status_gesehen.append(n["wert"])
        elif n["typ"] == "text":
            stuecke.append(n["wert"])
        elif n["typ"] == "fehler":
            print("  FEHLER:", n["wert"])
print(f"  ({time.monotonic() - start:.1f}s) Status: {status_gesehen}")
print(f"  Antwort: {''.join(stuecke).strip()[:120]}")

print("\n=== Protokoll danach ===")
p = c.get("/api/protokoll").json()["eintraege"]
for eintrag in p[-6:]:
    print(f"  {eintrag['zeit']} [{eintrag['art']:8}] {eintrag['text'][:66]}")

print("\n=== Agent ueber die Oberflaeche ===")
r = c.post("/api/agenten", json={"aufgabe": "Nenne die Uhrzeit."}).json()
print(f"  {r['meldung']}")
zustand = c.get("/api/zustand").json()
print(f"  Zustand: {zustand}")

print("\nAlles erreichbar.")
