"""Prüft die technischen Daten und misst, was das Abfragen kostet."""
import time

import psutil

from jarvis import tools

ich = psutil.Process()
vorher = ich.memory_info().rss / 1e6

print("=== Einzelne Bereiche ===")
for bereich in ("cpu", "ram", "festplatte", "gpu", "temperatur",
                "netzwerk", "akku", "system"):
    start = time.perf_counter()
    antwort = tools.system_info(bereich)
    dauer = time.perf_counter() - start
    print(f"\n  [{bereich}] {dauer:5.2f}s")
    print(f"  {antwort}")

print("\n=== Zweite Abfrage: greift das Merken? ===")
for bereich in ("gpu", "temperatur"):
    start = time.perf_counter()
    tools.system_info(bereich)
    print(f"  [{bereich}] jetzt {time.perf_counter() - start:5.2f}s")

print("\n=== Alles auf einmal ===")
start = time.perf_counter()
alles = tools.system_info()
print(f"  ({time.perf_counter() - start:.2f}s, {len(alles)} Zeichen)")
print(" ", alles[:400], "...")

print("\n=== Unbekannter Bereich ===")
print(" ", tools.system_info("quatsch")[:130])

print("\n=== Was kostet das Abfragen? ===")
print(f"  Start des Skripts: {vorher:.1f} MB")
# Erst jetzt messen: die einmaligen Importe und der Prozessorname aus der
# Registrierung sind vorbei, ab hier zaehlen nur noch die Abfragen selbst.
import gc
gc.collect()
vor_schleife = ich.memory_info().rss / 1e6

start = time.perf_counter()
for _ in range(200):
    tools.system_info("ram")
dauer = (time.perf_counter() - start) / 200
gc.collect()
nach_schleife = ich.memory_info().rss / 1e6

print(f"  Eine RAM-Abfrage: {dauer*1000:.2f} Millisekunden")
print(f"  Vor 200 Abfragen {vor_schleife:.1f} MB, danach {nach_schleife:.1f} MB "
      f"({nach_schleife-vor_schleife:+.2f} MB)")
assert nach_schleife - vor_schleife < 5, "haelt zu viel vor"
print("  Es wird nichts vorgehalten - die Werte kommen frisch vom System.")
