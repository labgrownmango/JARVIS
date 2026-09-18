#!/usr/bin/env python3
# Annahme: Skript soll nur Dateien im Temp-Verzeichnis löschen, nicht verschieben oder überschreiben,
# ohne vorherige Benutzerauskunft. Es wird ein Unterordner "geloescht" verwendet.

import argparse
import os
import sys
import time
import shutil
from pathlib import Path

def get_temp_dir() -> Path:
    """Ermittelt das System-Temp-Verzeichnis."""
    temp = os.getenv('TEMP') or os.getenv('TMP') or tempfile.gettempdir()
    return Path(temp)

def find_old_files(temp_dir: Path, days: int = 30):
    """Gibt eine Liste von Dateien zurück, die älter als `days` sind."""
    cutoff = time.time() - days * 86400
    old_files = []
    for entry in temp_dir.iterdir():
        if entry.is_file():
            try:
                mtime = entry.stat().st_mtime
            except OSError:
                continue  # Datei nicht zugreifbar
            if mtime < cutoff:
                old_files.append(entry)
    return old_files

def safe_move(file_path: Path, target_dir: Path):
    """Verschiebt die Datei in target_dir, benennt bei Konflikt um."""
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / file_path.name
    if target.exists():
        # Füge Zeitstempel hinzu, um Kollision zu vermeiden
        timestamp = time.strftime("%Y%m%d%H%M%S")
        target = target_dir / f"{file_path.stem}_{timestamp}{file_path.suffix}"
    try:
        shutil.move(str(file_path), str(target))
    except Exception as e:
        print(f"Fehler beim Verschieben von {file_path}: {e}", file=sys.stderr)

def preview_files(files):
    """Zeigt eine Vorschau der zu löschenden Dateien."""
    if not files:
        print("Keine Dateien älter als 30 Tage gefunden.")
        return
    print(f"Folgende {len(files)} Dateien würden gelöscht werden:")
    for f in files:
        print(f"  {f}")
    print()

def confirm_action(count: int) -> bool:
    """Fragt den Benutzer, ob er fortfahren möchte."""
    print(f"{count} Dateien würden gelöscht werden.")
    ans = input("Möchten Sie fortfahren? (ja/nein): ").strip().lower()
    return ans == "ja"

def main():
    parser = argparse.ArgumentParser(description="Löscht alte Dateien im Temp-Verzeichnis.")
    parser.add_argument("--wirklich", action="store_true",
                        help="Tatsächliche Löschung durchführen (Standard ist Vorschau).")
    args = parser.parse_args()

    temp_dir = get_temp_dir()
    if not temp_dir.is_dir():
        print(f"Temp-Verzeichnis {temp_dir} nicht gefunden.", file=sys.stderr)
        sys.exit(1)

    old_files = find_old_files(temp_dir)

    if not args.wirklich:
        preview_files(old_files)
        sys.exit(0)

    if not old_files:
        print("Keine Dateien zum Löschen gefunden.")
        sys.exit(0)

    if not confirm_action(len(old_files)):
        print("Abbruch ohne Änderungen.")
        sys.exit(0)

    # Verschiebe Dateien in Unterordner "geloescht"
    target_dir = temp_dir / "geloescht"
    for f in old_files:
        safe_move(f, target_dir)

    print(f"{len(old_files)} Dateien wurden in {target_dir} verschoben.")

if __name__ == "__main__":
    main()
