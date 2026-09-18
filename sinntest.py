"""Findet die Bedeutungssuche, was die Textsuche uebersieht?

Der Anlass: "worueber haben wir wegen dem Drucker geredet" fand nichts,
obwohl im Gespraech "Papierstau" stand. Ein Mensch haette es gefunden.

Geprueft wird gegen ein erfundenes Archiv mit bekanntem Inhalt - dann ist
die richtige Antwort nachpruefbar und nicht Geschmackssache. Das echte
Archiv wird nicht angefasst.

Antwortet das Einbettungsmodell nicht, wird der Test uebersprungen statt rot:
es ist ein freier Endpunkt im Netz und darf belegt sein. Was dann NICHT
uebersprungen wird, ist der Rueckfall auf die Textsuche - dass der
funktioniert, ist gerade dann wichtig.
"""
import json
import tempfile
from pathlib import Path

from jarvis import bedeutung, config, verlauf

config.ARCHIV_AN = True
fehler = 0
uebersprungen = 0

ordner = Path(tempfile.mkdtemp(prefix="jarvis-sinntest-"))
verlauf.DATEI = ordner / "verlauf.jsonl"
bedeutung.DATEI = ordner / "einbettungen.jsonl"
bedeutung._speicher = None

# Ein Archiv, in dem jede Frage eine eindeutig richtige Antwort hat - und in
# dem das gesuchte Wort NIE woertlich vorkommt.
ARCHIV = [
    ("du", "Der Drucker zieht das Papier schief ein und es staut sich."),
    ("jarvis", "Papierstau bei schiefem Einzug deutet auf die Zufuhrwalze."),
    ("du", "Wie warm wird es morgen in Hamburg?"),
    ("jarvis", "Zwanzig Grad und leichter Regen, Sir."),
    ("du", "Was kostet eine RTX 5090 ungefaehr?"),
    ("jarvis", "Zwischen zweitausend und zweitausendvierhundert Euro."),
    ("du", "Ich bin hundemuede und gehe gleich ins Bett."),
    ("jarvis", "Nachtmodus ist an, Sir."),
    ("du", "Erklaer mir, wie das Weckwort funktioniert."),
    ("jarvis", "Ein kleines Netz horcht dauerhaft auf den Klang."),
]
with verlauf.DATEI.open("w", encoding="utf-8") as fh:
    for nummer, (rolle, text) in enumerate(ARCHIV):
        fh.write(json.dumps(
            {"zeit": f"2026-09-10T10:{nummer:02d}:00", "sitzung": "test",
             "chat": "test", "rolle": rolle, "text": text},
            ensure_ascii=False) + "\n")


def pruefe(bedingung: bool, text: str, zusatz: str = "") -> None:
    global fehler
    fehler += not bedingung
    print(f"  {'ok    ' if bedingung else 'FEHLER'} {text}")
    if not bedingung and zusatz:
        print(f"         {zusatz}")


print("=== Die Textsuche findet es nicht - das ist der Anlass ===")
# Keines dieser Woerter steht woertlich im Archiv.
for wort in ("Druckerproblem", "Grafikkarte", "Schlaf"):
    treffer = verlauf.suchen(wort, grenze=5)
    pruefe(not treffer, f"'{wort}' findet die Textsuche nicht ({len(treffer)})")

print("\n=== Antwortet das Einbettungsmodell? ===")
da = bedeutung.verfuegbar()
print(f"         {bedeutung.MODELL}: {'ja' if da else 'nein'}")

if not da:
    uebersprungen += 1
    print("  ~~     uebersprungen - freier Endpunkt, darf belegt sein")
else:
    print("\n=== Nach Bedeutung gefunden ===")
    FAELLE = [
        ("Druckerproblem", "Papier", "der Papierstau"),
        ("Grafikkarte", "5090", "die RTX 5090"),
        # Ein einzelnes Wort ist die duennste Frage, die vorkommt - und
        # damit der schwerste Fall. Gemessen liegt der richtige Treffer
        # hier auf Platz 1, aber knapp ueber der Schwelle.
        ("Schlaf", ("muede", "Nachtmodus"), "das Schlafengehen"),
        # Gefunden werden darf die Frage ODER die Antwort - beides ist die
        # Stelle im Gespraech, um die es ging. Die erste Fassung dieses
        # Tests verlangte ausdruecklich die Antwort und wertete den Fund
        # der Frage als Fehler. Das war meine falsche Erwartung.
        ("Temperatur draussen", ("Grad", "warm"), "das Wetter"),
    ]
    for frage, muss, was in FAELLE:
        treffer, weg = verlauf.suchen_nach_sinn(frage, grenze=4)
        if weg != "Bedeutung":
            # Das Einbettungsmodell ist ein freier Endpunkt und darf mitten
            # im Lauf belegt sein. Dann greift der Rueckfall auf die
            # Textsuche - das ist gewolltes Verhalten und kein Fehler. Die
            # erste Fassung wertete es trotzdem als roten Test, weil die
            # Textsuche das Gesuchte naturgemaess nicht findet: genau
            # deshalb gibt es die Bedeutungssuche ja.
            uebersprungen += 1
            print(f"  ~~     '{frage}' - Modell antwortete nicht, "
                  f"Rueckfall auf Textsuche")
            continue
        texte = " ".join(e["text"] for e in treffer)
        erwartet = (muss,) if isinstance(muss, str) else muss
        ok = any(m.lower() in texte.lower() for m in erwartet)
        pruefe(ok, f"'{frage}' findet {was}",
               texte[:100] or "(nichts gefunden)")

    print("\n=== Unsinn findet nichts ===")
    treffer, weg = verlauf.suchen_nach_sinn(
        "Kaeseblatt Tiefkuehltruhe Zahnradbahn", grenze=4)
    if weg != "Bedeutung":
        uebersprungen += 1
        print("  ~~     Modell antwortete nicht - uebersprungen")
    else:
        pruefe(not treffer,
               f"zusammenhanglose Frage bleibt ohne Treffer ({len(treffer)})",
               " | ".join(e["text"][:40] for e in treffer))

    print("\n=== Der Zwischenspeicher wird benutzt ===")
    # Zweimal dieselbe Suche darf das Modell nicht zweimal befragen.
    vorher = bedeutung.DATEI.stat().st_size if bedeutung.DATEI.exists() else 0
    verlauf.suchen_nach_sinn("Druckerproblem", grenze=4)
    nachher = bedeutung.DATEI.stat().st_size if bedeutung.DATEI.exists() else 0
    pruefe(vorher == nachher,
           f"keine neuen Vektoren beim zweiten Mal ({vorher} -> {nachher})")
    pruefe(vorher > 0, "beim ersten Mal wurden welche abgelegt")

print("\n=== Ohne Modell bleibt das Archiv durchsuchbar ===")
# Der Rueckfall ist der Teil, der immer funktionieren muss.
echt = bedeutung.frage_vektor
bedeutung.frage_vektor = lambda f: None
try:
    treffer, weg = verlauf.suchen_nach_sinn("Papier", grenze=4)
    pruefe(weg == "Text", f"faellt auf die Textsuche zurueck (Weg: {weg})")
    pruefe(bool(treffer), f"und findet dort etwas ({len(treffer)})")
finally:
    bedeutung.frage_vektor = echt

print(f"\n  {fehler} Fehler"
      + (f", {uebersprungen} uebersprungen" if uebersprungen else ""))
raise SystemExit(1 if fehler else 0)
