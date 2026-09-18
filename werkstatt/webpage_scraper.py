# Dieses Skript laedt nichts aus dem Netz herunter - das ist hier nicht erlaubt.
# Stattdessen: Seite im Browser oeffnen und per "Speichern unter" als
# webpage.html ablegen, oder die Datei selbst herunterladen und den Pfad unten eintragen.
# Das Skript prueft dann nur, ob die Datei vorhanden und lesbar ist.

import sys
from pathlib import Path

ZIEL = Path("webpage.html")


def main() -> int:
    if not ZIEL.is_file():
        print(f"'{ZIEL}' nicht gefunden.")
        print("Bitte die Seite von Hand speichern (Browser: Strg+S) und erneut ausfuehren.")
        return 1

    try:
        inhalt = ZIEL.read_text(encoding="utf-8", errors="replace")
    except OSError as fehler:
        print(f"Datei konnte nicht gelesen werden: {fehler}")
        return 1

    print(f"'{ZIEL}' gefunden: {len(inhalt)} Zeichen.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
