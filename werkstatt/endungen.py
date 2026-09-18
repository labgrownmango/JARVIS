#!/usr/bin/env python3
# Skript: zählt Dateiendungen in einem Ordner und gibt die drei häufigsten aus

import argparse
import os
import sys
from collections import Counter

def main() -> None:
    parser = argparse.ArgumentParser(description="Zähle Dateiendungen in einem Ordner.")
    parser.add_argument("ordner", nargs="?", default=".", help="Verzeichnis, das untersucht werden soll (Standard: aktuelles Verzeichnis)")
    args = parser.parse_args()

    # Prüfen, ob der Pfad existiert und ein Verzeichnis ist
    if not os.path.exists(args.ordner):
        print(f"Fehler: Der Pfad '{args.ordner}' existiert nicht.", file=sys.stderr)
        sys.exit(1)
    if not os.path.isdir(args.ordner):
        print(f"Fehler: Der Pfad '{args.ordner}' ist kein Verzeichnis.", file=sys.stderr)
        sys.exit(1)

    # Zähle Dateiendungen
    endungen = Counter()
    try:
        for entry in os.scandir(args.ordner):
            if entry.is_file():
                _, ext = os.path.splitext(entry.name)
                if ext:  # nur Dateien mit Endung berücksichtigen
                    endungen[ext.lower()] += 1
    except PermissionError as e:
        print(f"Zugriff verweigert: {e}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"Dateisystemfehler: {e}", file=sys.stderr)
        sys.exit(1)

    if not endungen:
        print("Keine Dateien mit Endung gefunden.")
        return

    # Ausgabe der drei häufigsten Endungen
    print("Top 3 Dateiendungen:")
    for ext, count in endungen.most_common(3):
        print(f"{ext:>10} : {count} Datei(en)")

if __name__ == "__main__":
    main()
