"""Prüft die Wikipedia auf der Platte.

Wikimedia sperrt automatische Zugriffe von dieser Leitung aus - jede Adresse
antwortet mit 403, auch deren eigene Schnittstelle. Statt die Sperre zu umgehen
liegt die Wikipedia lokal: 3,9 GB, alle 5,1 Millionen Artikel mit Einleitung.
Kein Netz, keine Sperre, Antwort in Millisekunden.
"""
import time

from jarvis import config, tools

fehler = 0


def pruefe(bedingung: bool, text: str, zusatz: str = "") -> None:
    global fehler
    fehler += not bedingung
    print(f"  {'ok    ' if bedingung else 'FEHLER'} {text}")
    if not bedingung and zusatz:
        print(f"         {zusatz}")


print("=== Ist die Datei da? ===")
da = config.WIKIPEDIA_DATEI.exists()
pruefe(da, f"{config.WIKIPEDIA_DATEI.name} liegt auf der Platte")
if not da:
    print("  (ohne Datei lässt sich der Rest nicht prüfen)")
    raise SystemExit(1)
print(f"         {config.WIKIPEDIA_DATEI.stat().st_size/1e9:.2f} GB, "
      f"Stand {config.WIKIPEDIA_STAND}")

print("\n=== Treffer ===")
# Der zweite Wert ist ein Wort, das im Artikel stehen MUSS - so fällt auf,
# wenn zwar irgendein Artikel kommt, aber der falsche.
FAELLE = [
    ("Photosynthese", "Licht"),
    ("Marie Curie", "Nobelpreis"),
    ("Albert Einstein", "Physiker"),
    ("Zweiter Weltkrieg", "1939"),
    ("Iron Man", "Marvel"),
    # Umlaute in ASCII - so schreibt das Modell oft. Die Archivsuche kennt
    # diese Schreibweise nicht, deshalb werden Varianten durchprobiert.
    ("Koeln", "Köln"),
    ("Muenchen", "München"),
    ("Duesseldorf", "Düsseldorf"),
    ("Aegypten", "Ägypten"),
    ("Terroranschlaege am 11. September 2001", "2001"),
    # "Oesterreich" ist in der Wikipedia eine Weiterleitung auf die
    # Begriffsklärung. Der Artikel selbst ist der bessere Treffer.
    ("Oesterreich", "Republik"),
    ("Grosse Mauer", "Mauer"),
    ("nine eleven", "September"),
]
zeiten = []
for begriff, muss in FAELLE:
    start = time.perf_counter()
    antwort = tools.wikipedia(begriff, 600)
    zeiten.append((time.perf_counter() - start) * 1000)
    ok = "[bekannt]" in antwort and muss.lower() in antwort.lower()
    pruefe(ok, f"{begriff[:36]:38} {antwort.split(' - ', 1)[-1][:52]}",
           f"'{muss}' fehlt in der Antwort")

pruefe(max(zeiten) < 2000, f"langsamste Abfrage {max(zeiten):.0f} ms "
       f"(Schnitt {sum(zeiten)/len(zeiten):.0f} ms)")

print("\n=== Keine Begriffsklärung, wenn es den Artikel gibt ===")
for begriff in ("Oesterreich", "Österreich", "Photosynthese"):
    antwort = tools.wikipedia(begriff, 200)
    pruefe("Begriffskl" not in antwort, f"{begriff}: echter Artikel",
           antwort[:90])

print("\n=== Kein Formatmüll im Text ===")
# Wikipedia-Seiten bringen ihr Aussehen mit; Stilblöcke stehen mitten im
# Text. Ohne Herausschneiden läse das Modell Formatvorlagen statt Artikel.
for begriff in ("Photosynthese", "Albert Einstein", "Köln"):
    antwort = tools.wikipedia(begriff, 1500)
    dreck = [w for w in ("mw-parser-output", "font-family", "{", "<style",
                         "@media") if w in antwort]
    pruefe(not dreck, f"{begriff}: sauberer Text", str(dreck))

print("\n=== Der Titel steht nicht dreimal am Anfang ===")
antwort = tools.wikipedia("Iron Man", 200)
text = antwort.split(": ", 1)[-1]
pruefe(not text.lower().startswith("iron man iron man"),
       "Iron Man: Überschrift nicht verdoppelt", text[:70])

print("\n=== Wie viel vom Artikel ueberhaupt ankommt ===")
# Die Vorgabe war 1200 Zeichen und hat das Nachschlagewerk verschenkt. An 40
# Artikeln quer durch die Datei gemessen: Median 1938 Zeichen, laengster
# 7109. Bei 1200 waren nur 13 von 40 vollstaendig, bei 4000 sind es 36.
#
# Der Preis ist kleiner, als er aussieht: weil die meisten Artikel kurz
# sind, steigt die im Schnitt gelieferte Menge nur von 1043 auf 1984
# Zeichen - rund 270 Token. Der Deckel beisst nur bei den langen.
import inspect  # noqa: E402

vorgabe = inspect.signature(tools.wikipedia).parameters["zeichen"].default
pruefe(vorgabe >= 4000, f"Vorgabe ist {vorgabe}, nicht mehr 1200")

# Ein langer Artikel muss auch wirklich laenger ankommen. "Erster
# Weltkrieg" hat roh 7109 Zeichen - unter dem alten Deckel von 6000 waere
# er abgeschnitten geblieben.
tools.anfrage_beginnt()
kurz = tools.wikipedia("Erster Weltkrieg", 1200)
tools.anfrage_beginnt()
lang = tools.wikipedia("Erster Weltkrieg")
tools.anfrage_beginnt()
voll = tools.wikipedia("Erster Weltkrieg", 8000)
print(f"         1200 -> {len(kurz)}, Vorgabe -> {len(lang)}, "
      f"8000 -> {len(voll)}")
pruefe(len(lang) > len(kurz) * 2,
       f"die Vorgabe liefert deutlich mehr ({len(lang)} statt {len(kurz)})")
pruefe(len(voll) > 6000,
       f"der Deckel laesst mehr als 6000 durch ({len(voll)})",
       "der laengste gemessene Artikel hat 7109 Zeichen")

# Ein kurzer Artikel darf davon unberuehrt bleiben - sonst zahlt man die
# hoehere Grenze bei jedem Nachschlagen, statt nur bei den langen.
tools.anfrage_beginnt()
zimt_kurz = tools.wikipedia("Zimt", 1200)
tools.anfrage_beginnt()
zimt_lang = tools.wikipedia("Zimt")
pruefe(len(zimt_kurz) == len(zimt_lang),
       f"kurze Artikel bleiben gleich ({len(zimt_lang)} Zeichen)")

print("\n=== Und das Modell erfaehrt davon ===")
# Die entscheidende Stelle: solange im Schema "Standard 1200" stand, hat das
# Modell nie mehr angefordert - der Deckel darueber wurde nie erreicht.
wiki = [w for w in tools.schema()
        if w["function"]["name"] == "wikipedia"][0]
erklaerung = wiki["function"]["parameters"]["properties"]["zeichen"]["description"]
pruefe("1200" not in erklaerung or "4000" in erklaerung,
       "im Schema steht nicht mehr nur 'Standard 1200'", erklaerung[:80])
pruefe("4000" in erklaerung, "die neue Vorgabe steht dort", erklaerung[:80])
pruefe(any(w in erklaerung for w in ("6000", "8000")),
       "und dass mehr geholt werden darf", erklaerung[:80])

print("\n=== Was es nicht gibt ===")
pruefe("search_web" in tools.wikipedia("qwxzyfjkl_gibtsnicht_42"),
       "Unbekanntes verweist auf die Websuche")
pruefe("nachschlagen" in tools.wikipedia("  "), "Leere Frage wird abgefangen")

print("\n=== Schreibvarianten ===")
# Alle Ersetzungen gleichzeitig wäre falsch: aus "Duesseldorf" würde
# "Düßeldorf" (ue UND ss ersetzt), aus "Grosse Mauer" ein "Große Maür".
for wort, muss in (("Duesseldorf", "Düsseldorf"),
                   ("Grosse Mauer", "Große Mauer"),
                   ("Koeln", "Köln"),
                   ("Strasse", "Straße")):
    varianten = tools._schreibvarianten(wort)
    pruefe(muss in varianten, f"{wort} -> enthält {muss}", str(varianten))

print(f"\n  {fehler} Fehler")
raise SystemExit(1 if fehler else 0)
