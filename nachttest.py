"""Prüft den Nachtmodus: Farben, Zeitfenster und ob Jarvis Müdigkeit
auch in Worten erkennt, die nicht im Prompt stehen."""
import datetime as dt
import time

import httpx

from jarvis import config, regler, tools

print("=== Blaulichtfilter schalten ===")
print(" ", tools.set_night_mode(True))
an, staerke = regler.nachtmodus_lesen()
print(f"  Zustand: an={an}, Stärke {staerke}")
time.sleep(2)
print(" ", tools.set_night_mode(False))
print(f"  Zustand: {regler.nachtmodus_lesen()}")

print("\n=== Zusammen mit Abdunkeln ===")
tools.set_brightness(prozent=70)
tools.set_night_mode(True)
print(f"  Helligkeit {regler._gamma_stand}, Wärme {regler._waerme} - "
      f"beides gleichzeitig")
time.sleep(2)
regler.gamma_zuruecksetzen()
print(f"  zurückgesetzt: {regler._gamma_stand}, {regler._waerme}")

print("\n=== Zeitfenster 22:00 bis 6:30 ===")
for stunde, minute, erwartet in ((21, 59, False), (22, 0, True), (23, 30, True),
                                 (2, 0, True), (6, 29, True), (6, 30, False),
                                 (14, 0, False)):
    ist = regler.nachtzeit(dt.datetime(2026, 9, 12, stunde, minute))
    marke = "ok" if ist == erwartet else "FALSCH"
    print(f"  {marke:6} {stunde:02d}:{minute:02d} -> Nachtmodus {ist}")
    assert ist == erwartet, (stunde, minute)

print("\n=== Erkennung im Programm (unabhängig vom Modell) ===")
from jarvis.sprache import muedigkeit

JA = ["Ich bin müde.", "Puh, ich bin komplett am Ende heute.",
      "Ich glaub ich hau mich gleich aufs Ohr.",
      "Boah, mir reicht es fuer heute.", "Ich bin hundemuede.",
      "So, Feierabend.", "Meine Augen brennen langsam.",
      "Ich mach Schluss für heute.", "War ein langer Tag, ich geh ins Bett.",
      "*gähn* was steht morgen an?", "I'm exhausted.",
      "Ich bin fix und fertig.", "Ich muss morgen früh raus, ich penn gleich."]
NEIN = ["Wie spät ist es?", "Mach mal lauter.",
        "Mein Kollege war gestern total müde, hat er erzählt.",
        "Was hilft eigentlich gegen Müdigkeit?",
        "Der Rechner ist müde geworden, dauert ewig.",
        "Schreib mir ein Skript für Backups."]

fehler_lokal = 0
for satz in JA:
    ok = muedigkeit(satz)
    fehler_lokal += not ok
    print(f"  {'ok    ' if ok else 'NEIN  '} {satz}")
print()
for satz in NEIN:
    ok = not muedigkeit(satz)
    fehler_lokal += not ok
    print(f"  {'ok    ' if ok else 'FALSCH'} {satz}")
print(f"\n  {fehler_lokal} Fehler von {len(JA) + len(NEIN)}")

print("\n=== Erkennt das Modell Müdigkeit? (Formulierungen, die NICHT "
      "im Prompt stehen) ===")
H = {"Authorization": f"Bearer {config.API_KEY}"}
MODELL = "openai/gpt-oss-20b"

SOLL_SCHALTEN = [
    "Puh, ich bin komplett am Ende heute.",
    "Ich glaub ich hau mich gleich aufs Ohr.",
    "Boah, mir reicht es fuer heute.",
    "Ich bin hundemuede.",
]
SOLL_NICHT = [
    "Wie spaet ist es?",
    "Mein Kollege war gestern total muede, hat er erzaehlt.",
    "Was hilft eigentlich gegen Muedigkeit?",
]


def werkzeuge(text: str) -> str:
    # 700 statt 200 Tokens: gpt-oss denkt in einem eigenen Kanal, bevor es
    # etwas Sichtbares schreibt. Bei 200 war das Budget gemessen in drei von
    # zwoelf Faellen vorher aufgebraucht - zurueck kam eine Nachricht ohne
    # Werkzeug und ohne Text, und der Test las daraus "er hat nicht
    # geschaltet". Der Test haette dann sein eigenes Limit gemessen.
    # Ein Fehlercode wurde uebersprungen, ein Verbindungsabbruch nicht: der
    # flog als httpx.ReadTimeout bis nach oben durch und riss den ganzen
    # Testlauf mit. In der Reihe stand dann ein Rueckverfolgungsprotokoll
    # statt eines Ergebnisses - das sieht nach einem Codefehler aus, war
    # aber nur der Endpunkt. Gemessen am 14.09.2026, einmal in 48 Laeufen.
    try:
        r = httpx.post(f"{config.BASE_URL}/chat/completions", headers=H,
                       timeout=120,
                       json={"model": MODELL, "max_tokens": 700,
                             "tools": tools.schema(),
                             "messages": [
                                 {"role": "system",
                                  "content": config.SYSTEM_PROMPT},
                                 {"role": "user", "content": text}]})
    except Exception as exc:
        return f"[{type(exc).__name__}]"
    if r.status_code != 200:
        return f"[{r.status_code}]"
    m = r.json()["choices"][0]["message"]
    namen = ", ".join(a["function"]["name"]
                      for a in (m.get("tool_calls") or []))
    if namen:
        return namen
    # Kein Werkzeug UND kein Text ist keine Entscheidung, sondern ein
    # Aussetzer - und der darf nicht als Fehlentscheidung gezaehlt werden.
    return "(keins)" if (m.get("content") or "").strip() else "[leere Antwort]"


fehler = 0
uebersprungen = 0


def entscheidung(satz: str, muss_schalten: bool) -> None:
    global fehler, uebersprungen
    genutzt = werkzeuge(satz)
    if genutzt.startswith("["):
        uebersprungen += 1
        print(f"    ~~     {genutzt:24} {satz}")
        return
    ok = ("set_night_mode" in genutzt) == muss_schalten
    fehler += not ok
    print(f"    {'ok    ' if ok else 'NEIN  '} {genutzt:24} {satz}")


print("\n  Muss schalten:")
for satz in SOLL_SCHALTEN:
    entscheidung(satz, True)

print("\n  Darf NICHT schalten:")
for satz in SOLL_NICHT:
    entscheidung(satz, False)

print(f"\n  {fehler} Fehlentscheidungen von "
      f"{len(SOLL_SCHALTEN) + len(SOLL_NICHT)}"
      + (f", {uebersprungen} Aussetzer" if uebersprungen else ""))
regler.gamma_zuruecksetzen()
print("\nFertig.")
