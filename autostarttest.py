"""Legt die Autostart-Verknüpfung an, liest sie zurück und räumt wieder auf."""
from jarvis import autostart

print("=== Vorher ===")
print(" ", autostart.zustand())
war_an = autostart.zustand()["an"]

print("\n=== Anlegen: Weboberfläche still im Hintergrund ===")
print(" ", autostart.einschalten("oberflaeche"))
lage = autostart.zustand()
print(f"  Zustand: {lage}")
assert lage["an"] and lage["art"] == "oberflaeche"
print(f"  Datei da: {autostart.pfad().exists()}, "
      f"{autostart.pfad().stat().st_size} Bytes")
print(f"  Verweist auf: {autostart._ziel_lesen(autostart.pfad())}")

print("\n=== Umstellen auf Weckwort ===")
print(" ", autostart.einschalten("weckwort"))
lage = autostart.zustand()
print(f"  Zustand: {lage}")
assert lage["art"] == "weckwort"
print(f"  Verweist auf: {autostart._ziel_lesen(autostart.pfad())}")

print("\n=== Unsinnige Betriebsart ===")
print(" ", autostart.einschalten("quatsch"))

print("\n=== Wieder abschalten ===")
print(" ", autostart.ausschalten())
print(f"  Zustand: {autostart.zustand()}")
assert not autostart.zustand()["an"]
print(" ", autostart.ausschalten())          # zweimal schadet nicht

if war_an:
    autostart.einschalten("oberflaeche")
    print("\n  (war vorher an - wieder eingeschaltet)")

print("\n=== Startet er auch OHNE Konsole? ===")
# Der Autostart benutzt pythonw.exe, damit kein schwarzes Fenster aufgeht.
# Dabei ist sys.stdout None - und uvicorn fragt beim Einrichten seiner
# Protokollierung sys.stdout.isatty() ab. Ergebnis war ein AttributeError,
# lautlos, bei jedem Hochfahren. Von Hand gestartet lief alles, deshalb fiel
# es lange nicht auf. Dieser Test startet deshalb wirklich ein pythonw.
import subprocess
import sys
import tempfile
from pathlib import Path

pythonw = Path(sys.executable).with_name("pythonw.exe")
if not pythonw.exists():
    print("  (kein pythonw.exe - übersprungen)")
else:
    bericht = Path(tempfile.gettempdir()) / "jarvis_konsolentest.txt"
    if bericht.exists():
        bericht.unlink()
    skript = f"""
import sys, traceback
sys.path.insert(0, r"{Path(__file__).parent}")
ergebnis = []
try:
    ergebnis.append("stdout ist " + ("None" if sys.stdout is None else "da"))
    from jarvis import web
    web._ausgabe_umleiten()
    ergebnis.append("nach dem Umleiten: " +
                    ("None" if sys.stdout is None else "da"))
    import uvicorn
    uvicorn.Config(web.app, log_level="warning")   # hier krachte es
    ergebnis.append("uvicorn richtet sich ein: ok")
except BaseException:
    ergebnis.append("FEHLER " + traceback.format_exc()[-300:])
open(r"{bericht}", "w", encoding="utf-8").write(chr(10).join(ergebnis))
"""
    hilfs = Path(tempfile.gettempdir()) / "jarvis_konsolentest.py"
    hilfs.write_text(skript, encoding="utf-8")
    subprocess.run([str(pythonw), str(hilfs)], timeout=120)

    if not bericht.exists():
        print("  FEHLER pythonw hat nicht einmal geschrieben")
        raise SystemExit(1)
    zeilen = bericht.read_text(encoding="utf-8").splitlines()
    for zeile in zeilen:
        print(f"    {zeile}")
    assert "stdout ist None" in zeilen[0], "Test lief mit Konsole - wertlos"
    assert any("uvicorn richtet sich ein: ok" in z for z in zeilen), \
        "Ohne Konsole startet die Oberfläche nicht"
    print("  ok     ohne Konsole startbar")

print("\nFertig - der Autostart bleibt aus, bis du ihn willst.")
