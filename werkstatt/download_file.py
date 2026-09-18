# HINWEIS: Dieses Skript laedt bewusst NICHTS aus dem Netz herunter.
# Grund: Ueber dieses Programm soll nichts auf dem Rechner landen, das
# nicht der Mensch selbst geholt hat.
# Stattdessen: Datei im Browser oder mit curl/wget von Hand laden und
# dann dieses Skript nutzen, um sie an den Zielort zu kopieren:
#   curl -O https://beispiel.de/datei.zip
#   python speichern.py datei.zip ziel/datei.zip

import argparse
import shutil
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Kopiert eine lokal vorhandene Datei an einen Zielort."
    )
    parser.add_argument("quelle", help="Pfad zur vorhandenen Datei")
    parser.add_argument("ziel", help="Zieldatei oder Zielverzeichnis")
    args = parser.parse_args()

    quelle = Path(args.quelle)
    ziel = Path(args.ziel)

    if not quelle.is_file():
        print(f"Fehler: Quelle '{quelle}' existiert nicht.", file=sys.stderr)
        return 1

    # Zielverzeichnis angegeben -> Dateinamen uebernehmen
    if ziel.is_dir():
        ziel = ziel / quelle.name

    if ziel.exists():
        antwort = input(f"'{ziel}' existiert bereits. Ueberschreiben? [ja/nein] ")
        if antwort.strip().lower() != "ja":
            print("Abgebrochen.")
            return 0

    try:
        ziel.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(quelle, ziel)
    except OSError as fehler:
        print(f"Fehler beim Kopieren: {fehler}", file=sys.stderr)
        return 1

    print(f"Gespeichert: {ziel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
