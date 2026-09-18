"""Prüft das Ausweichen auf das nächste Modell der Rangliste -
ohne echte API-Aufrufe."""
import os

os.environ["JARVIS_RETRIES"] = "2"

import jarvis.config as config

config.RETRIES_429 = 2
# Kein Testgespraech im echten Archiv - siehe abbruchtest.py
config.ARCHIV_AN = False

from jarvis.brain import Brain

ERSATZ = "ersatz/modell"
meldungen: list[str] = []


def zeige(s: str) -> None:
    meldungen.append(s)
    print("   Status:", s)


print("=== Fall 1: belegt, dann Ausweichen auf das nächste Modell ===")
brain = Brain()
brain.rangliste = [brain.model, ERSATZ]     # so sieht es nach dem Pingen aus
versuche = []


def immer_belegt(messages):
    versuche.append(brain.model)
    if brain.model == ERSATZ:
        return "STREAM-VOM-ERSATZMODELL"
    raise RuntimeError("Error code: 429 - Too Many Requests")


brain._einmal = immer_belegt
ergebnis = brain._stream([], brain._gen, zeige)
print("   Ergebnis:", ergebnis)
print("   Versuche:", versuche)
assert ergebnis == "STREAM-VOM-ERSATZMODELL"
assert len(versuche) == 4, versuche          # 3 x Hauptmodell + 1 x Ersatz
# Nach dem Wechsel kommt ein "denkt", damit die Statuszeile nicht
# fälschlich "belegt" stehen lässt
assert meldungen == ["wartet:3", "wartet:6", "denkt"], meldungen

print("\n=== Fall 2: belegt, kein weiteres Modell frei ===")
brain2 = Brain()
brain2.rangliste = [brain2.model]            # nichts mehr dahinter
brain2._einmal = lambda m: (_ for _ in ()).throw(
    RuntimeError("Error code: 429 - Too Many Requests"))
try:
    brain2._stream([], brain2._gen, lambda s: None)
    print("   FEHLER: hätte scheitern müssen")
except RuntimeError as exc:
    print("   Saubere Meldung:", exc)

print("\n=== Fall 3: anderer Fehler wird durchgereicht, nicht wiederholt ===")
brain3 = Brain()
zaehler = []


def anderer_fehler(m):
    zaehler.append(1)
    raise RuntimeError("Error code: 500 - Internal Server Error")


brain3._einmal = anderer_fehler
try:
    brain3._stream([], brain3._gen, lambda s: None)
except RuntimeError as exc:
    print(f"   Durchgereicht nach {len(zaehler)} Versuch:", exc)
assert len(zaehler) == 1

print("\n=== Fall 3b: eine kaputte Antwort WIRD wiederholt ===")
# Gemeldet aus dem Betrieb: auf "seit wann ist Nuristan ein Land?" stand im
# Fenster "FEHLER list index out of range", und die unveraenderte Frage
# gleich danach wurde sauber beantwortet. Die Meldung stammt aus der
# OpenAI-Bibliothek: kommt eine Antwort ohne 'choices' zurueck, greift sie
# ins Leere. Das ist keine Absage des Anbieters, sondern eine kaputte
# Uebertragung - und die ist beim naechsten Versuch meist weg.
#
# Der Unterschied zu Fall 3 ist Absicht: ein 500 ist eine Antwort ("ich
# kann nicht"), eine abgerissene Uebertragung ist gar keine.
from jarvis.brain import _voruebergehend  # noqa: E402

for exc, soll in [
        (IndexError("list index out of range"), True),
        (TimeoutError("The read operation timed out"), True),
        (RuntimeError("Connection reset by peer"), True),
        (RuntimeError("Error code: 500 - Internal Server Error"), False),
        (RuntimeError("Error code: 503 - Service Unavailable"), False),
        (RuntimeError("Error code: 401 - Unauthorized"), False),
        (ValueError("Kein API-Key gefunden"), False),
]:
    ist = _voruebergehend(exc)
    zeichen = "ok    " if ist == soll else "FEHLER"
    print(f"   {zeichen} {type(exc).__name__}: {str(exc)[:44]:46} -> {ist}")
    assert ist == soll, (exc, ist, soll)

brain3b = Brain()
zaehler3b = []


def kaputte_antwort(m):
    zaehler3b.append(1)
    if len(zaehler3b) < 3:
        raise IndexError("list index out of range")
    return "STREAM-BEIM-DRITTEN-VERSUCH"


brain3b._einmal = kaputte_antwort
ergebnis3b = brain3b._stream([], brain3b._gen, lambda s: None)
print(f"   Nach {len(zaehler3b)} Versuchen: {ergebnis3b}")
assert ergebnis3b == "STREAM-BEIM-DRITTEN-VERSUCH"
assert len(zaehler3b) == 3, zaehler3b

print("\n=== Fall 4: Rangliste nach Reihenfolge und nach Tempo ===")
brain4 = Brain()
brain4.ping = [
    {"modell": "a/langsam-gut", "zustand": "frei", "dauer": 9.0},
    {"modell": "b/schnell-mies", "zustand": "frei", "dauer": 0.4},
    {"modell": "c/belegt", "zustand": "belegt", "dauer": 0.2},
]
config.MODELS = ["a/langsam-gut", "b/schnell-mies", "c/belegt"]

for regel, erwartet in (("reihenfolge", "a/langsam-gut"),
                        ("schnellste", "b/schnell-mies")):
    config.MODELL_WAHL = regel
    frei = [e for e in brain4.ping if e["zustand"] == "frei"]
    frei.sort(key=(lambda e: e["dauer"]) if regel == "schnellste"
              else (lambda e: config.MODELS.index(e["modell"])))
    gewaehlt = frei[0]["modell"]
    print(f"   {regel:12} -> {gewaehlt}")
    assert gewaehlt == erwartet
print("   Belegte Modelle stehen in keiner der beiden Ranglisten.")

print("\nAlles wie erwartet.")
