"""Prüft das Code-Werkzeug: Zäune entfernen, Datei schreiben, Limits."""
import time

from jarvis import config, tools

tools.melde = lambda t: print(f"    ... {t}")

print("=== Zäune entfernen (ohne API) ===")
FAELLE = [
    ("```python\nprint('hallo')\n```", "print('hallo')"),
    ("```\nx = 1\n```", "x = 1"),
    ("print('ohne Zaun')", "print('ohne Zaun')"),
    ("```py\na = 1\nb = 2\n```", "a = 1\nb = 2"),
]
for roh, erwartet in FAELLE:
    ergebnis = tools._zaun_entfernen(roh)
    marke = "ok" if ergebnis == erwartet else "FALSCH"
    print(f"  {marke:6} {roh[:28]!r:34} -> {ergebnis[:30]!r}")
    assert ergebnis == erwartet, (roh, ergebnis)

print("\n=== Limit ===")
print(f"  Gespräch: {config.MAX_TOKENS} Tokens (kurz, wird vorgelesen)")
print(f"  Code    : {config.CODE_TOKENS} Tokens")
assert config.CODE_TOKENS > config.MAX_TOKENS

print("\n=== Leere Aufgabe ===")
print(f"  {tools.write_code('')}")

print("\n=== Echter Auftrag ===")
tools.aktuelles_modell = config.MODELS[0]
start = time.perf_counter()
ergebnis = tools.write_code(
    "Ein Skript, das alle Dateien in einem Ordner nach Endung zählt und die "
    "drei häufigsten ausgibt. Ordner als Argument, Standard das aktuelle "
    "Verzeichnis.",
    datei="endungen.py")
print(f"  ({time.perf_counter() - start:.1f}s) {ergebnis}")

pfad = config.WERKSTATT / "endungen.py"
if pfad.exists():
    inhalt = pfad.read_text(encoding="utf-8")
    print(f"\n  Datei liegt in werkstatt/, {len(inhalt)} Zeichen")
    assert "```" not in inhalt, "Zaun ist in der Datei gelandet"
    print("  Keine Zäune in der Datei.")

    print("\n=== Läuft der erzeugte Code? ===")
    import subprocess
    lauf = subprocess.run([".venv\\Scripts\\python.exe", str(pfad)],
                          capture_output=True, text=True, timeout=60)
    print(f"  Rückgabewert {lauf.returncode}")
    print("  " + (lauf.stdout or lauf.stderr)[:300].replace("\n", "\n  "))
