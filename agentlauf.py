"""Lässt einen echten Agenten eine mehrschrittige Aufgabe zu Ende bringen."""
import time

import psutil

from jarvis.agenten import HANGAR

vorher = psutil.Process().memory_info().rss / 1e6
print(f"Speicher vorher: {vorher:.1f} MB\n")

agent, meldung = HANGAR.starten(
    "Sammle das aktuelle Wetter fuer Berlin, Hamburg und Muenchen. "
    "Nenne im Bericht alle drei Temperaturen und welche Stadt die waermste ist.")
print(meldung)

while agent.laeuft:
    print(f"  {agent.name}: {agent.zustand}, {agent.dauer:.0f}s", end="\r")
    time.sleep(2)

print(f"\n\n{agent.name} fertig nach {agent.dauer:.0f}s ({agent.zustand})")
print("-" * 70)
print(agent.bericht)
print("-" * 70)

waehrend = psutil.Process().memory_info().rss / 1e6
bericht = HANGAR.abholen(agent.name)
import gc
gc.collect()
nachher = psutil.Process().memory_info().rss / 1e6

print(f"\nSpeicher: {vorher:.1f} -> {waehrend:.1f} MB waehrend der Arbeit, "
      f"{nachher:.1f} MB nach dem Aufraeumen")
print(f"Hangar danach: {len(HANGAR.agenten)} Agenten")
assert not HANGAR.agenten
