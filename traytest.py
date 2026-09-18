"""Prüft, ob das Symbol in der Taskleiste wirklich erscheint."""
import threading
import time

from jarvis import tray

print("=== Verfügbar? ===")
print(" ", tray.verfuegbar())

print("\n=== Symbol zeichnen ===")
bild = tray._symbol()
print(f"  {bild.size[0]}x{bild.size[1]} {bild.mode}")

print("\n=== Anmelden bei Windows ===")
beendet = []
t = tray.Tray("http://127.0.0.1:8765", beim_beenden=lambda: beendet.append(1))
symbol = t.bauen()

faden = threading.Thread(target=symbol.run, daemon=True)
faden.start()

for i in range(20):
    time.sleep(0.5)
    if getattr(symbol, "visible", False):
        break
print(f"  nach {(i+1)*0.5:.1f}s sichtbar: {symbol.visible}")
print(f"  Titel: {symbol.title}")
print(f"  Menuepunkte: {[str(m.text) for m in symbol.menu]}")
assert symbol.visible, "Windows hat das Symbol nicht angenommen"

print("\n=== Beenden über das Menü ===")
t._beenden()
time.sleep(1)
print(f"  Rückmeldung angekommen: {bool(beendet)}")
print(f"  Symbol noch sichtbar: {getattr(symbol, 'visible', False)}")
assert beendet

print("\nFertig. Hinweis: Windows 11 versteckt neue Symbole hinter dem")
print("Pfeil '^' in der Taskleiste - von dort einmal herausziehen.")
