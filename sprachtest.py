"""Prüft die Spracherkennung und ihren Zeitaufwand."""
import time

from jarvis.sprache import erkenne
from jarvis.voice import lautschrift

FAELLE = [
    # (Satz, erwartet)
    ("Guten Morgen, Sir.", "de"),
    ("Der Arbeitsspeicher liegt bei 87 Prozent.", "de"),
    ("Mir geht es gut, Sir. Und Ihnen?", "de"),
    ("Bedeckt, etwa 18 Grad, leichter Nieselregen.", "de"),
    ("Ich öffne den Browser.", "de"),               # englisches Wort, deutscher Satz
    ("Das Update ist fertig.", "de"),
    ("Good morning, Sir.", "en"),
    ("The weather is quite good today.", "en"),
    ("I am afraid I cannot do that.", "en"),
    ("All systems are running normally.", "en"),
    ("Shall I open the browser for you?", "en"),
    ("Ja.", "de"),
    ("Okay.", "de"),                                # zu kurz zum Entscheiden
    ("", "de"),
]

print(f"{'Satz':50} {'erkannt':8} {'erwartet':9} ")
print("-" * 78)
fehler = 0
for satz, erwartet in FAELLE:
    ergebnis = erkenne(satz)
    marke = "ok" if ergebnis == erwartet else "FALSCH"
    if ergebnis != erwartet:
        fehler += 1
    print(f"{satz[:50]:50} {ergebnis:8} {erwartet:9} {marke}")

print(f"\n{fehler} Fehler von {len(FAELLE)}")

print("\n=== Lautschrift greift nur auf Deutsch ===")
for satz in ("Guten Morgen, Sir.", "Good morning, Sir."):
    sprache = erkenne(satz)
    gesprochen = lautschrift(satz) if sprache == "de" else satz
    print(f"  [{sprache}] {satz!r} -> {gesprochen!r}")

print("\n=== Zeitaufwand der Erkennung ===")
probe = "Der Arbeitsspeicher liegt bei siebenundachtzig Prozent, Sir."
runden = 10_000
start = time.perf_counter()
for _ in range(runden):
    erkenne(probe)
dauer = (time.perf_counter() - start) / runden
print(f"  {dauer * 1e6:.1f} Mikrosekunden pro Satz")
print(f"  bei 20 Sätzen pro Antwort: {dauer * 20 * 1000:.3f} Millisekunden")
assert dauer < 0.001, "zu langsam"
assert fehler == 0, f"{fehler} Fehlerkennungen"
print("\nAlles wie erwartet.")
