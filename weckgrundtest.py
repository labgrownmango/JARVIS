"""Nennt die Weckwort-Pruefung die RICHTIGE Ursache?

Vier Faelle, alle vier auf echten Rechnern aufgetreten:

  1. Paket fehlt          -> "nachinstallieren" ist richtig
  2. DLL blockiert        -> "nachinstallieren" ist FALSCH. Auf dem zweiten
                             Rechner war das Paket da, Windows liess nur
                             eine Bibliothek nicht laufen.
  3. Modelldateien fehlen -> auch hier hilft Nachinstallieren nicht. Das
                             trifft jeden frisch aufgesetzten Rechner:
                             openwakeword bringt seine Modelle nicht mit.
  4. irgendetwas anderes  -> Wortlaut zeigen statt raten

Eine falsche Ursache ist teurer als gar keine: wer "pip install" liest,
installiert ein vorhandenes Paket noch einmal und sucht den Fehler danach
an der falschen Stelle.
"""
import builtins

from jarvis import config, weckwort

fehler = 0
echt_import = builtins.__import__


def pruefe(bedingung: bool, text: str, zusatz: str = "") -> None:
    global fehler
    fehler += not bedingung
    print(f"  {'ok    ' if bedingung else 'FEHLER'} {text}")
    if not bedingung and zusatz:
        print(f"         {zusatz}")


def mit_importfehler(fehler_objekt):
    def gefaelscht(name, *rest, **kw):
        if name == "openwakeword":
            raise fehler_objekt
        return echt_import(name, *rest, **kw)
    return gefaelscht


print("=== 1. Paket fehlt ===")
builtins.__import__ = mit_importfehler(
    ImportError("No module named 'openwakeword'"))
try:
    geht, grund = weckwort.verfuegbar()
finally:
    builtins.__import__ = echt_import
print(f"         {grund[:130]}")
pruefe(not geht and "nachinstallieren" in grund.lower(),
       "schickt zum Nachinstallieren - hier richtig")

print("\n=== 2. DLL blockiert ===")
builtins.__import__ = mit_importfehler(
    ImportError("DLL load failed while importing _base: Der angegebene "
                "Prozedureinsprungspunkt wurde nicht gefunden."))
try:
    geht, grund = weckwort.verfuegbar()
finally:
    builtins.__import__ = echt_import
print(f"         {grund[:150]}")
pruefe(not geht, "wird abgelehnt")
pruefe("Smart App Control" in grund or "Virenschutz" in grund,
       "nennt die wahrscheinliche Ursache", grund[:120])
pruefe("nachinstallieren mit pip" not in grund.lower(),
       "schickt NICHT zum Nachinstallieren - das waere hier falsch",
       grund[:120])

print("\n=== 3. Modelldateien fehlen ===")
# Der Fall vom zweiten Rechner: Paket laedt, aber der Modellordner ist leer.
echt_dateien = weckwort._modelldateien
weckwort._modelldateien = lambda wort: (
    [f"{wort}_v0.1.onnx", "melspectrogram.onnx"], r"C:\irgendwo\models")
try:
    geht, grund = weckwort.verfuegbar()
finally:
    weckwort._modelldateien = echt_dateien
print(f"         {grund[:200]}")
pruefe(not geht, "wird abgelehnt")
pruefe("Modelldateien fehlen" in grund, "benennt die Ursache", grund[:120])
pruefe(config.WECKWORT in grund, "nennt die konkrete Datei", grund[:140])
pruefe("download_models" in grund,
       "nennt den Weg, sie zu holen", grund[:160])
pruefe("macht Jarvis es nicht von selbst" in grund,
       "sagt ausdruecklich, dass Jarvis nicht selbst herunterlaedt",
       grund[:160])
pruefe("nachinstallieren mit pip" not in grund.lower(),
       "schickt NICHT zum Nachinstallieren", grund[:120])

print("\n=== 4. Etwas anderes ===")
builtins.__import__ = mit_importfehler(
    ImportError("cannot import name 'Model' from 'openwakeword'"))
try:
    geht, grund = weckwort.verfuegbar()
finally:
    builtins.__import__ = echt_import
print(f"         {grund[:130]}")
pruefe(not geht and "cannot import name" in grund,
       "zeigt den Wortlaut, statt zu raten")

print("\n=== Auf DIESEM Rechner ===")
geht, grund = weckwort.verfuegbar()
print(f"         {'einsatzbereit' if geht else grund[:150]}")

print(f"\n  {fehler} Fehler")
raise SystemExit(1 if fehler else 0)
