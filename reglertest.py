"""Prüft Lautstärke und Helligkeit - und stellt beides wieder her."""
import time

from jarvis import regler, tools

print("=== Lautstärke ===")
anfang, war_stumm = regler.lautstaerke_lesen()
print(f"  vorher: {anfang} Prozent, stumm: {war_stumm}")

print(f"  {tools.set_volume()}")
print(f"  {tools.set_volume(prozent=30)}")
time.sleep(0.5)
print(f"  {tools.set_volume(direction='lauter')}")
print(f"  {tools.set_volume(direction='leiser', steps=20)}")
print(f"  {tools.set_volume(direction='stumm')}")
time.sleep(0.5)
print(f"  {tools.set_volume(direction='ton')}")

regler.lautstaerke_setzen(anfang)
regler.stumm_setzen(war_stumm)
print(f"  wiederhergestellt: {regler.lautstaerke_lesen()[0]} Prozent")
assert regler.lautstaerke_lesen()[0] == anfang

print("\n=== Helligkeit ===")
print(f"  {tools.set_brightness()}")
print("  -> wird jetzt kurz dunkler")
print(f"  {tools.set_brightness(prozent=55)}")
time.sleep(1.5)
print(f"  {tools.set_brightness(richtung='dunkler')}")
time.sleep(1.5)
print(f"  {tools.set_brightness(richtung='heller')}")
time.sleep(1.0)
print(f"  {tools.set_brightness(richtung='zurueck')}")

print("\n=== Welcher Weg wird genutzt? ===")
wert, weg = regler.helligkeit_lesen()
print(f"  {wert} Prozent über: {weg}")

print("\n=== Unsinnige Werte ===")
print(f"  {tools.set_volume(prozent=500)}")
regler.lautstaerke_setzen(anfang)
print(f"  {tools.set_brightness(prozent=-5)}")
tools.set_brightness(richtung="zurueck")

print(f"\nEndstand: {regler.lautstaerke_lesen()[0]} Prozent Lautstärke")
print("Fertig.")
