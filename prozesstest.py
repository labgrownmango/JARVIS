"""Prüft Öffnen, Auflisten, Schließen und "Datei mit Programm öffnen"."""
import time
from pathlib import Path

import psutil

from jarvis import tools

print("=== Was läuft gerade ===")
print(" ", tools.list_processes(anzahl=6)[:220])

print("\n=== Windows-Kern ist geschützt ===")
for kritisch in ("explorer", "csrss.exe", "lsass", "winlogon", "System"):
    antwort = tools.close_app(kritisch)
    assert "ruehre ich nicht an" in antwort, (kritisch, antwort)
print("  alle fünf geschützt")

print("\n=== Laufzeitumgebungen werden nicht abgeschossen ===")
for mehrdeutig in ("python", "powershell", "node", "java", "cmd"):
    antwort = tools.close_app(mehrdeutig)
    ok = "Laufzeitumgebung" in antwort
    print(f"  {'ok    ' if ok else 'GEFAHR'} {mehrdeutig:12} {antwort[:56]}")
    assert ok, (mehrdeutig, antwort)

print("\n=== Programme finden, auch ausserhalb des Startmenues ===")
for gesucht in ("notepad", "firefox", "msedge", "explorer", "quatschxyz"):
    treffer = tools._programm_finden(gesucht)
    print(f"  {gesucht:12} -> {treffer[1][:66] if treffer else 'nicht gefunden'}")

print(f"  Registrierung kennt {len(tools._registrierung())} Programme")
print(f"  Startmenue kennt    {len(tools._startmenue())} Verknuepfungen")

print("\n=== Datei mit bestimmtem Programm öffnen ===")
probe = Path(tools.config.WERKSTATT) / "probe.html"
probe.parent.mkdir(parents=True, exist_ok=True)
probe.write_text("<h1>Jarvis-Probe</h1>", encoding="utf-8")

print(" ", tools.open_with("probe.html", "editor"))
time.sleep(2.5)
print("  laeuft Notepad jetzt?", tools.list_processes("notepad"))
print(" ", tools.close_app("notepad"))
time.sleep(1.5)

print("\n=== Nicht vorhandene Datei ===")
print(" ", tools.open_with("gibtsnicht.txt", "editor")[:100])

print("\n=== Öffnen und schliessen im Durchlauf ===")
print(" ", tools.open_app("rechner"))
time.sleep(2.5)
print("  laeuft:", tools.list_processes("calc"))
print(" ", tools.close_app("calculator"))

probe.unlink(missing_ok=True)
print("\nFertig.")
