"""Führt alle Testskripte aus - mit Fortschritt, damit man sieht, dass es läuft.

    pruefen.py           alles (dauert ein paar Minuten)
    pruefen.py schnell   ohne die langsamen (Ton, Modelle, Wartezeiten)
    pruefen.py <name>    nur die, deren Name das enthaelt
"""
import subprocess
import sys
import time
from pathlib import Path

HIER = Path(__file__).parent
PYTHON = HIER / ".venv/Scripts/python.exe"

# Die langsamen - sie spielen Ton ab, rufen Modelle auf oder warten absichtlich
LANGSAM = {"sprachtest.py", "stimmtest.py", "stimmvergleich.py",
           "weckworttest.py", "reglertest.py", "grenztest.py",
           "systemtest.py", "prozesstest.py", "demotest.py", "nachttest.py",
           "stimmwechseltest.py", "zeittest.py", "netztest.py",
           "gespraechstest.py", "browsertest.py", "ichtest.py",
           # bildtest ruft seit der Bildreihe das echte Modell auf: die
           # Bildregel liess sich nur messen, nicht lesen.
           "bildtest.py"}

ALLE = ["paketetest.py", "selbsttest.py", "sprachtest.py", "tagtest.py",
        "zeittest.py",
        "verlauftest.py", "autostarttest.py", "traytest.py", "wachtest.py",
        "fragetest.py", "weckworttest.py", "sicherheitstest.py",
        "prozesstest.py", "systemtest.py", "reglertest.py", "grenztest.py",
        "stimmwechseltest.py", "nachttest.py", "agententest.py",
        "abbruchtest.py",
        "fallbacktest.py", "befehlstest.py", "denktest.py", "verbotstest.py",
        "zugangstest.py", "wikitest.py", "rechnertest.py", "bildtest.py",
        "posttest.py", "melditest.py", "medientest.py", "sicherungstest.py", "browsertest.py",
        "amsitest.py", "weckgrundtest.py", "adresstest.py", "programmtest.py",
        "stiltest.py", "quellentest.py", "chattest.py", "medizintest.py",
        "jahrtest.py",
        "mdtest.py", "hoertest.py", "sinntest.py",
        "uebersetztest.py", "ichtest.py", "gespraechstest.py",
        "netztest.py", "demotest.py"]


def main() -> int:
    wahl = sys.argv[1].lower() if len(sys.argv) > 1 else ""
    if wahl == "schnell":
        skripte = [s for s in ALLE if s not in LANGSAM]
    elif wahl:
        skripte = [s for s in ALLE if wahl in s.lower()]
    else:
        skripte = list(ALLE)

    # Was es hier nicht gibt, wird uebersprungen statt gemeldet. Auf einem
    # zweiten Rechner fehlen einzelne Tests, und das ist kein Fehler.
    skripte = [s for s in skripte if (HIER / s).exists()]
    if not skripte:
        print(f"Nichts gefunden zu '{wahl}'.")
        return 1

    print(f"{len(skripte)} Skripte\n")
    # JARVIS_ARCHIV=0: mehrere Tests legen ein echtes Brain an und stellen ihm
    # eine Frage. Ohne das landet jede davon im Gespraechsarchiv - und dann
    # stehen mitten im eigenen Verlauf "Erzähl mir was", "Hallo" und "Test".
    # Hier zentral, damit kein einzelner Test es vergessen kann.
    # PYTHONIOENCODING: Tests drucken Modellantworten, und die enthalten
    # Sonderzeichen, die es in cp1252 nicht gibt - gemeldet von Mini-Jost ein
    # U+202F (schmales geschuetztes Leerzeichen) mitten in einer Antwort.
    # Ohne das hier stirbt der Test an einem UnicodeEncodeError, und zwar
    # ausgerechnet in der Zeile, die den GRUND zeigen soll. Statt eines
    # Ergebnisses stand ein Rueckverfolgungsprotokoll da.
    #
    # "replace" statt "strict": ein Zeichen, das die Konsole nicht kann, wird
    # zu einem Fragezeichen. Das ist haesslich und voellig ausreichend - ein
    # Testlauf darf nicht an der Schriftart der Konsole scheitern.
    umgebung = {"JARVIS_SIMPLE_INPUT": "1", "JARVIS_ARCHIV": "0",
                "PYTHONIOENCODING": "utf-8:replace"}
    import os
    umwelt = {**os.environ, **umgebung}

    fehlgeschlagen, zeiten = [], []
    anfang = time.perf_counter()

    for nummer, skript in enumerate(skripte, 1):
        print(f"  [{nummer:>2}/{len(skripte)}] {skript:22} ", end="", flush=True)
        start = time.perf_counter()
        # encoding HIER genauso wie PYTHONIOENCODING oben - sonst schreiben
        # die Tests UTF-8 und dieser Laeufer liest cp1252. Gemessen: der
        # ganze Durchlauf starb an
        #
        #   UnicodeDecodeError: 'charmap' codec can't decode byte 0x9d
        #
        # und zwar nicht in einem Test, sondern im Lesethread von
        # subprocess. Die halbe Reparatur war schlimmer als keine: sie hat
        # das Problem von der Schreib- auf die Leseseite verschoben.
        lauf = subprocess.run([str(PYTHON), skript], cwd=HIER, env=umwelt,
                              capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        dauer = time.perf_counter() - start
        zeiten.append((dauer, skript))

        if lauf.returncode == 0:
            print(f"ok      {dauer:5.1f}s")
        else:
            print(f"FEHLER  {dauer:5.1f}s")
            fehlgeschlagen.append((skript, lauf))

    gesamt = time.perf_counter() - anfang
    print(f"\n{len(skripte) - len(fehlgeschlagen)} von {len(skripte)} in "
          f"{gesamt:.0f}s")

    if zeiten:
        print("\nDie langsamsten:")
        for dauer, name in sorted(zeiten, reverse=True)[:5]:
            print(f"  {dauer:5.1f}s  {name}")

    for skript, lauf in fehlgeschlagen:
        print(f"\n--- {skript} ---")
        zeilen = (lauf.stdout + lauf.stderr).strip().splitlines()

        # Nur das Ende zu zeigen reichte nicht: bei langen Skripten steht die
        # eigentliche Fehlerzeile weit oben, und man sucht sie jedes Mal von
        # Hand. Deshalb erst die Treffer, dann der Schluss.
        #
        # Die Trefferzeile allein reichte aber auch nicht: die Tests schreiben
        # ihre Begruendung in die ZEILEN DANACH ("uebernommen=... zweifelt=...",
        # dann der Antworttext). Die fielen hier heraus, und dann musste der
        # ganze Test noch einmal von Hand laufen, nur um zu sehen, WARUM er
        # durchfiel. Also kommen die zwei Folgezeilen mit.
        marker = ("FEHLER", "FALSCH", "NEIN  ", "AssertionError", "Traceback",
                  "Error:")
        zeigen: list[int] = []
        for i, zeile in enumerate(zeilen):
            if any(m in zeile for m in marker):
                zeigen += [n for n in range(i, min(i + 3, len(zeilen)))
                           if n not in zeigen]
        if zeigen:
            for nummer, i in enumerate(zeigen[:24]):
                # Eine Luecke sichtbar machen, statt entfernte Zeilen
                # buendig untereinander zu setzen - das las sich wie ein
                # zusammenhaengender Block und war es nicht.
                if nummer and i != zeigen[nummer - 1] + 1:
                    print("  !   ...")
                print(f"  ! {zeilen[i]}")
            if len(zeigen) > 24:
                print(f"  ! ... und {len(zeigen) - 24} weitere Zeilen")
            print("  ---")
        for zeile in zeilen[-10:]:
            print(f"  {zeile}")

    return 1 if fehlgeschlagen else 0


if __name__ == "__main__":
    raise SystemExit(main())
