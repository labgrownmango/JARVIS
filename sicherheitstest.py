"""Prüft die Sicherung gegen löschenden Code - ohne API."""
from jarvis.tools import _sicherheitspruefung as pruefe

SCHLAEGT_AN = [
    ("os.remove löscht ohne zu fragen",
     "import os\nfor f in liste:\n    os.remove(f)\n"),
    ("shutil.move verschiebt ohne zu fragen",
     "import shutil\nshutil.move(a, b)\n"),
    ("rmtree loescht ganze Baeume",
     "import shutil\nshutil.rmtree(ordner)\n"),
    ("Path.unlink",
     "from pathlib import Path\nPath('x.txt').unlink()\n"),
    ("PowerShell Remove-Item",
     "Get-ChildItem $pfad | Remove-Item\n"),
    ("SQL DELETE FROM",
     "DELETE FROM kunden WHERE alt = 1;\n"),
]

SCHWEIGT = [
    ("nur lesen",
     "import os\nfor f in os.scandir('.'):\n    print(f.name)\n"),
    ("loescht, fragt aber vorher",
     "import os\nif input('Wirklich? ') == 'ja':\n    os.remove(f)\n"),
    ("loescht nur mit --wirklich",
     "p.add_argument('--wirklich', action='store_true')\n"
     "if args.wirklich:\n    shutil.move(a, b)\n"),
    ("dry_run als Standard",
     "def main(dry_run=True):\n    if not dry_run:\n        os.unlink(f)\n"),
    ("PowerShell mit WhatIf",
     "Remove-Item $p -WhatIf\n"),
    ("Kopieren ist harmlos",
     "import shutil\nshutil.copy2(a, b)\n"),
]

fehler = 0
print("=== Muss anschlagen ===")
for name, code in SCHLAEGT_AN:
    ergebnis = pruefe(code)
    ok = bool(ergebnis)
    fehler += not ok
    print(f"  {'ok    ' if ok else 'FEHLER'} {name:38} {ergebnis or '(nichts)'}")

print("\n=== Muss schweigen ===")
for name, code in SCHWEIGT:
    ergebnis = pruefe(code)
    ok = not ergebnis
    fehler += not ok
    print(f"  {'ok    ' if ok else 'FEHLER'} {name:38} "
          f"{ergebnis or '(still)'}")

print(f"\n{fehler} Fehler")
assert fehler == 0
print("Die Sicherung greift und schlaegt nicht grundlos an.")
