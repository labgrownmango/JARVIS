"""Hörtest: mehrere Sätze am Stück, deutsche und englische Stimme,
und ein gemischter Satz ohne Pause in der Mitte."""
import time

from jarvis import config
from jarvis.sprache import erkenne
from jarvis.voice import SentenceSpeaker, make_speaker

print("=== Startzeit der Sprachausgabe ===")
start = time.perf_counter()
speaker = make_speaker()
print(f"  bereit nach {time.perf_counter() - start:.2f}s "
      f"(die englische Stimme lädt nebenher weiter)")
print(f"  Sprachwechsel: {'an' if config.SPRACHWECHSEL else 'aus'}")

print("\n=== Einzelne Sätze ===")
SAETZE = [
    "Systeme online. Wie kann ich helfen, Sir?",
    "Zweiter Satz. Wenn Sie diesen hören, ist der Fehler behoben.",
    "Good morning, Sir. All systems are running normally.",
    "Vierter Satz, wieder auf Deutsch. Alle Systeme bereit.",
]
for i, satz in enumerate(SAETZE, 1):
    print(f"  {i}. [{erkenne(satz)}] {satz}")
    speaker.say(satz)
speaker.wait()

print("\n=== Gemischter Satz mit Markierung (muss fliessend klingen) ===")
saetze = SentenceSpeaker(speaker)
roh = "Der Befehl heisst <en>save as</en>, Sir. Und der zweite heisst <en>open recent</en>."
print(f"  roh      : {roh}")
print(f"  sichtbar : {saetze.feed(roh)}{saetze.flush()}")
speaker.wait()
time.sleep(0.3)

geladen = sorted(getattr(speaker, "_stimmen", {}))
print(f"\nGeladene Stimmen: {geladen}")
print("Erwartet: vier Sätze einzeln (einer davon englisch), dann zwei")
print("gemischte Sätze - in denen darf keine Pause vor 'save as' sein.")
