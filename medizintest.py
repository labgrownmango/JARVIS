"""Medizinische Fragen: PubMed statt Websuche - und LIVIVO ehrlich.

Der Grund für ein eigenes Werkzeug: bei "hilft Metformin gegen
Herzinfarkt" liefert eine allgemeine Suche Ratgeberseiten, Kliniken, die
sich selbst bewerben, und Foren. PubMed verzeichnet die Fachliteratur
selbst - mit Zeitschrift, Jahr und einer festen Adresse je Arbeit.

LIVIVO (ZB MED) wäre für deutschlandbezogene Fragen das Richtige, steht
aber hinter einer Bot-Prüfung. Gemessen am 14.09.2026: jede Adresse,
auch /api/, liefert einem Programm nur die Prüfseite. Das auszuhebeln
kommt nicht in Frage. Also wird die Suche im Browser geöffnet, und
Jarvis sagt ehrlich, dass er sie nicht gelesen hat.
"""
from pathlib import Path

from jarvis import config, tools

HIER = Path(__file__).parent
fehler = 0


def pruefe(bedingung: bool, text: str, zusatz: str = "") -> None:
    global fehler
    fehler += not bedingung
    print(f"  {'ok    ' if bedingung else 'FEHLER'} {text}")
    if not bedingung and zusatz:
        print(f"         {zusatz}")


print("=== Eingetragen? ===")
for name in ("pubmed", "livivo"):
    pruefe(name in tools.REGISTRY, f"{name} ist im Register")
    pruefe(any(f["function"]["name"] == name for f in tools.schema()),
           f"{name} steht im Schema")

beschreibung = [f for f in tools.schema()
                if f["function"]["name"] == "pubmed"][0]["function"]["description"]
pruefe("ENGLISCH" in beschreibung,
       "das Schema sagt, dass PubMed englisch sucht",
       "sonst kommt 'Bluthochdruck' als Suchwort an und findet nichts")
pruefe("keine Diagnose" in beschreibung, "und dass es keine Diagnose ist")

print("\n=== Leere Fragen fangen ===")
pruefe("Wonach" in tools.pubmed(""), "pubmed fragt zurück")
pruefe("Wonach" in tools.livivo(""), "livivo fragt zurück")

print("\n=== PubMed liefert echte Literaturstellen ===")
antwort = tools.pubmed("metformin cardiovascular outcomes", 3)
if "nicht erreichbar" in antwort or "antwortet nicht" in antwort:
    print(f"  (PubMed gerade nicht erreichbar - übersprungen: {antwort[:70]})")
else:
    print("  " + antwort.split("|| HINWEIS")[0].strip()[:300].replace(
        "\n", "\n  "))
    zeilen = [z for z in antwort.splitlines() if z.startswith("- ")]
    pruefe(len(zeilen) >= 1, f"{len(zeilen)} Treffer")
    for zeile in zeilen:
        pruefe(zeile.count("|") >= 3,
               "Titel, Autor, Zeitschrift/Jahr und Adresse getrennt",
               zeile[:90])
        pruefe("https://pubmed.ncbi.nlm.nih.gov/" in zeile,
               "feste Adresse zur Arbeit", zeile[:90])
    pruefe("keine Diagnose" in antwort,
           "der Hinweis steht am Ergebnis, nicht nur im Prompt")
    pruefe("Erfinde keine Ergebnisse" in antwort,
           "und warnt davor, Ergebnisse zu erfinden")

    # Die Quellen müssen in der Fußzeile landen - sonst steht da eine
    # Studienaussage ohne Beleg, und das ist bei Medizin das Schlimmste.
    gemeldet = tools.quellen()
    pruefe(any("pubmed.ncbi.nlm.nih.gov" in (q.get("url") or "")
               for q in gemeldet),
           f"die Quellen sind gemeldet ({len(gemeldet)})")

print("\n=== Unsinnsbegriffe werden nicht schöngeredet ===")
leer = tools.pubmed("qwertzuiop asdfghjkl", 3)
pruefe("findet nichts" in leer or "nichts Brauchbares" in leer
       or "nicht erreichbar" in leer, "kein Treffer heisst kein Treffer",
       leer[:90])

print("\n=== LIVIVO: die Bot-Prüfung wird nicht umgangen ===")
werkzeuge = (HIER / "jarvis" / "tools.py").read_text(encoding="utf-8")
stelle = werkzeuge.split("def livivo")[0][-1400:]
pruefe("Bot-Pruefung" in stelle or "not a bot" in stelle,
       "der Grund steht im Quelltext, nicht nur in einem Chat")
pruefe("_seite_oeffnen" in werkzeuge.split("def livivo")[1][:800],
       "LIVIVO wird geöffnet, nicht ausgelesen")
pruefe("haettest du sie gelesen" in werkzeuge,
       "und Jarvis wird verboten, so zu tun, als hätte er gelesen")

print("\n=== Die Regel steht im Systemprompt ===")
for stueck, was in (
        ("Medizinische Fragen", "der Abschnitt ist da"),
        ("NICHT die allgemeine Websuche", "die Websuche ist ausgeschlossen"),
        ("gehen an pubmed", "PubMed für allgemeine Fragen"),
        ("nimmst du livivo", "LIVIVO für Deutschland"),
        ("keine Diagnose", "keine Diagnose"),
        ("Eine einzelne Studie ist kein Beweis", "eine Studie ist kein Beweis")):
    pruefe(stueck in config.SYSTEM_PROMPT, was)

print(f"\n  {fehler} Fehler")
raise SystemExit(1 if fehler else 0)
