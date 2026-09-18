#!/usr/bin/env python3
# Sortiert den Ordner "Downloads" nach Dateierweiterung, erstellt Unterordner und verschiebt Dateien.

import os
import shutil
from pathlib import Path
from datetime import datetime

def main():
    downloads = Path.home() / "Downloads"
    if not downloads.is_dir():
        print(f"Downloads-Verzeichnis {downloads} nicht gefunden.")
        return

    for item in downloads.iterdir():
        if item.is_file():
            ext = item.suffix.lower().lstrip('.')
            if not ext:  # Dateien ohne Erweiterung
                ext = "ohne_erweiterung"
            target_dir = downloads / ext
            try:
                target_dir.mkdir(exist_ok=True)
            except OSError as e:
                print(f"Fehler beim Erstellen von {target_dir}: {e}")
                continue

            target_path = target_dir / item.name
            # Falls Datei bereits existiert, eindeutigen Namen erzeugen
            if target_path.exists():
                base = target_path.stem
                suffix = target_path.suffix
                counter = 1
                while True:
                    new_name = f"{base}_{counter}{suffix}"
                    new_path = target_dir / new_name
                    if not new_path.exists():
                        target_path = new_path
                        break
                    counter += 1
            try:
                shutil.move(str(item), str(target_path))
                print(f"Verschoben: {item.name} → {target_path.relative_to(downloads)}")
            except Exception as e:
                print(f"Fehler beim Verschieben von {item.name}: {e}")

if __name__ == "__main__":
    main()
