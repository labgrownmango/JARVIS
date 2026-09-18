"""Steht unter der Antwort, worauf sie sich stuetzt?

Gewuenscht war eine Fusszeile wie bei den grossen Diensten: Vorlesen,
Kopieren, Quellen - die Quellen ausklappbar, mit Zeichen und Verweis.

Zwei Dinge sind daran heikel, und beide werden hier geprueft:

  1. Die Quellenangabe darf NICHT aus dem Antworttext gelesen werden. Was
     das Modell schreibt, ist keine Quellenangabe - es koennte eine Adresse
     erfinden. Gemeldet wird deshalb vom Werkzeug selbst, und nur das, was
     wirklich abgerufen wurde.
  2. Die Adressen stammen aus Suchtreffern, also aus dem Netz. Ein
     "javascript:" daraus in ein href zu schreiben waere genau die Luecke,
     die verbote.py sonst schliesst.

Braucht kein Netz fuer den Wikipedia-Teil.
"""
import json
import re
from pathlib import Path

from jarvis import tools

WURZEL = Path(__file__).parent
fehler = 0


def pruefe(bedingung: bool, text: str, zusatz: str = "") -> None:
    global fehler
    fehler += not bedingung
    print(f"  {'ok    ' if bedingung else 'FEHLER'} {text}")
    if not bedingung and zusatz:
        print(f"         {zusatz}")


print("=== Nachschlagen meldet seine Quelle ===")
tools.anfrage_beginnt()
pruefe(tools.quellen() == [], "zu Beginn ist nichts gemeldet")

antwort = tools.wikipedia("Photosynthese")
gemeldet = tools.quellen()
print(f"         {gemeldet}")
pruefe(len(gemeldet) == 1, f"genau eine Quelle ({len(gemeldet)})")
if gemeldet:
    q = gemeldet[0]
    pruefe(q["art"] == "wikipedia", f"als wikipedia erkannt: {q['art']}")
    pruefe("Photosynthese" in q["titel"], f"mit dem Titel: {q['titel']}")
    pruefe(q["url"].startswith("https://de.wikipedia.org/wiki/"),
           f"und einem Verweis: {q['url']}")

print("\n=== Der Titel kommt aus dem Archiv, nicht aus der Frage ===")
# Bei "Koeln" heisst der Artikel "Köln" - und nur damit stimmt die Adresse.
# Stuende die Frage im Verweis, zeigte er auf eine Seite, die es nicht gibt.
tools.anfrage_beginnt()
tools.wikipedia("Koeln")
gemeldet = tools.quellen()
if gemeldet:
    print(f"         {gemeldet[0]['url']}")
    pruefe("K%C3%B6ln" in gemeldet[0]["url"] or "Köln" in gemeldet[0]["url"],
           "der Umlaut steht im Verweis", gemeldet[0]["url"])
    pruefe("Koeln" not in gemeldet[0]["url"],
           "die Schreibweise aus der Frage NICHT", gemeldet[0]["url"])
else:
    print("  ~~     kein Treffer - uebersprungen")

print("\n=== Ein Fehlschlag meldet nichts ===")
# Sonst stuende unter einer Antwort eine Quelle, die nie etwas geliefert hat.
tools.anfrage_beginnt()
tools.wikipedia("qwxzyfjkl_gibtsnicht_42")
pruefe(tools.quellen() == [], f"nichts gemeldet: {tools.quellen()}")

print("\n=== Dieselbe Quelle nur einmal ===")
tools.anfrage_beginnt()
tools.wikipedia("Photosynthese")
tools.anfrage_beginnt()          # neue Anfrage - Liste faengt leer an
tools.wikipedia("Photosynthese")
pruefe(len(tools.quellen()) == 1,
       f"nach einer neuen Anfrage genau eine ({len(tools.quellen())})")

tools.quelle_melden("seite", "heise.de", "https://heise.de/a")
tools.quelle_melden("seite", "heise.de", "https://heise.de/a")
pruefe(len(tools.quellen()) == 2,
       f"eine doppelt gemeldete zaehlt einmal ({len(tools.quellen())})")

print("\n=== Der Weg nach vorne ===")
brain = (WURZEL / "jarvis" / "brain.py").read_text(encoding="utf-8")
pruefe("quelle:" in brain, "brain.py schickt 'quelle:' los")
pruefe("tools.quellen()" in brain, "und holt sie beim Werkzeug ab")
# Ueber denselben Kanal wie "werkzeug:" und "info:" - kein zweiter Weg.
pruefe("on_status(\"quelle:\"" in brain,
       "ueber den Statuskanal, nicht ueber den Antworttext")

js = (WURZEL / "oberflaeche" / "jarvis.js").read_text(encoding="utf-8")
pruefe('w.startsWith("quelle:")' in js, "die Oberflaeche nimmt sie entgegen")
pruefe("quellenZeigen" in js, "und stellt sie dar")

print("\n=== Kein Umweg ueber einen Favicon-Dienst ===")
# HIER STAND EINMAL DAS GEGENTEIL: "kein favicon in der Oberflaeche". Die
# Begruendung war, ein Favicon sei ein Web-Download je Quelle. Das war
# falsch, und J. Kaiser hat es gesehen: ein <img> LAEDT nichts herunter, es
# zeigt an - genau das Argument, mit dem Jarvis ueberhaupt Bilder in die
# Antwort setzen darf. Zweierlei Mass in derselben Datei.
#
# Vom alten Einwand bleibt einer uebrig, und der gilt weiter: ein
# FAVICON-DIENST bekaeme jede besuchte Adresse gemeldet. Der direkte Weg
# zur Seite selbst verraet ihr dagegen nichts, was sie nicht weiss - Jarvis
# hat sie gerade gelesen, vom selben Anschluss aus.
#
# Gesucht wird nur im ausfuehrbaren Teil. Die erste Fassung durchsuchte die
# ganze Datei und schlug an meinem eigenen Kommentar an, der erklaert, WARUM
# kein Dienst benutzt wird - der Test faerbte also rot, weil die Begruendung
# dasteht. Dasselbe Problem hatte verbotstest.py mit den .bat-Dateien.
ohne_kommentar = re.sub(r"/\*.*?\*/", " ", js, flags=re.S)
ohne_kommentar = "\n".join(
    z for z in ohne_kommentar.splitlines() if not z.strip().startswith("//"))

for muster, was in ((r"google\.com/s2", "Googles Favicon-Dienst"),
                    (r"duckduckgo\.com/ip3", "DuckDuckGos Favicon-Dienst"),
                    (r"icons\.duckduckgo", "DuckDuckGos Icon-Server"),
                    (r"favicone|besticon|faviconkit", "einen der kleinen Dienste"),
                    (r"unavatar|logo\.clearbit", "einen Logo-Dienst")):
    pruefe(not re.search(muster, ohne_kommentar, re.I),
           f"kein Umweg ueber {was}")
# Die bekannten Zeichen stehen als SVG im Code selbst - die brauchen gar
# keine Verbindung.
pruefe("QUELLZEICHEN" in js and "<svg" in js,
       "die bekannten Zeichen sind eingebaut")

print("\n=== Nur http und https werden verlinkt ===")
# Die Pruefung steht in jarvis.js; hier wird festgehalten, DASS sie da ist.
pruefe("https?:" in js and "quelleNotieren" in js,
       "die Oberflaeche prueft das Schema vor dem Verlinken")
pruefe('noopener' in js and 'noreferrer' in js,
       "Verweise tragen noopener und noreferrer")

print("\n=== Die Fusszeile hat alle drei Knoepfe ===")
for was, marke in (("Vorlesen", "lautsprecherSvg"),
                   ("Kopieren", "kopierSvg"),
                   ("Quellen", "quellenkopf")):
    pruefe(marke in js, f"{was} ist da")
pruefe("antwortfuss" in js, "und sie sitzen in einer Leiste unter der Antwort")

print("\n=== Kopieren gibt das Markdown, nicht den Fliesstext ===")
# Wer eine Antwort weiterschickt, will die Gliederung behalten.
pruefe("dataset.roh" in js, "der Rohtext wird aufgehoben")
# navigator.clipboard gibt es nur im sicheren Kontext - ueber http://jarvis
# im Heimnetz also nicht. Ohne Rueckfallweg taete der Knopf dort nichts.
pruefe("execCommand" in js, "und es gibt einen Rueckfallweg ohne HTTPS")

css = (WURZEL / "oberflaeche" / "stil.css").read_text(encoding="utf-8")
pruefe(".antwortfuss" in css and ".quellenliste" in css,
       "das Aussehen ist beschrieben")

print("\n=== Bekannte Seiten bekommen ihr Zeichen, nicht einen Buchstaben ===")
# Gemeldet: unter den Quellen stand ein "I" auf farbigem Grund - fuer
# Instagram, das nun wirklich ein eigenes Zeichen hat. Der Buchstabe ist die
# Rueckfallebene, nicht die Regel.
pruefe("SEITENZEICHEN" in js, "es gibt eine Tabelle bekannter Seiten")
for seite in ("instagram.com", "youtube.com", "github.com", "reddit.com",
              "stackoverflow.com", "tagesschau.de", "heise.de",
              "pubmed.ncbi.nlm.nih.gov"):
    pruefe(f'"{seite}"' in js, f"{seite} hat ein Zeichen")

# Jedes Zeichen muss auch wirklich gezeichnet sein - und eine Farbe haben,
# sonst steht ein weisses Bild auf weissem Grund.
block = js.split("const SEITENZEICHEN")[1].split("\n};")[0]
pruefe(block.count("svg viewBox") == block.count("farbe:"),
       f"jede Seite hat Zeichen UND Farbe "
       f"({block.count('svg viewBox')} zu {block.count('farbe:')})")
# Der entscheidende Punkt, derselbe wie oben: nichts davon wird geholt.
pruefe("http" not in block,
       "kein einziges Zeichen wird aus dem Netz geladen")
pruefe("de.wikipedia.org" not in block and r"wikipedia\.org$" in js,
       "de. und en.wikipedia.org teilen sich ein Zeichen",
       "im Quelltext steht der Punkt maskiert: wikipedia\\.org$")

print("\n=== Alle uebrigen Seiten: das echte Favicon, Buchstabe darunter ===")
# Einwand von J. Kaiser, und er trifft: ein <img> LAEDT nichts herunter, es
# zeigt an. Genau damit ist begruendet, dass Jarvis Bilder in die Antwort
# setzen darf - hier das Gegenteil zu behaupten war widerspruechlich.
#
# Der ernstzunehmende Rest des Einwands war die Seite, die erfaehrt, dass
# nach ihr gefragt wurde. Nur weiss sie das schon: Jarvis hat sie gerade
# gelesen, vom selben Anschluss aus.
pruefe("quellfavicon" in js and ".quellfavicon" in css,
       "das echte Favicon wird angezeigt")
pruefe('"https://" + schluessel + "/favicon.ico"' in js,
       "direkt bei der Seite selbst")
# Ein Favicon-Dienst waere bequemer und deutlich schlechter: er bekaeme
# JEDE besuchte Adresse gemeldet.
pruefe("s2/favicons" not in ohne_kommentar,
       "und weiterhin kein Umweg ueber einen Dienst",
       "geprueft ohne die Kommentare - der eine Satz, der den Dienst "
       "erklaert, ist sonst selbst der Treffer")
pruefe("referrerPolicy" in js.split("quellfavicon")[1][:600],
       "die Seite erfaehrt nicht, von wo aus")
pruefe("onerror" in js.split("quellfavicon")[1][:900],
       "und der Buchstabe bleibt als Rueckfall")
pruefe("naturalWidth" in js,
       "ein 1x1-Platzhalter zaehlt nicht als Zeichen",
       "manche Seiten antworten mit einem leeren Bild statt mit 404")
pruefe("hatzeichen" in css, "erst wenn es da ist, verdeckt es den Buchstaben")

print("\n=== Aber NUR fuer Seiten, auf denen jemand war ===")
# Einwand von Mini-Jost, und er trifft den Kern der Begruendung: "die Seite
# weiss es ohnehin" gilt fuer art "seite" und "wikipedia" - die hat Jarvis
# geholt. Fuer art "web" gilt es NICHT: search_web meldet jeden Treffer als
# Quelle, auch die ungeprueften, und von denen kennt Jarvis nur den Ausriss
# der Suchmaschine. Dort war niemand.
#
# Ein <img> an jeden Treffer haette bedeutet: eine Frage, fuenf Verbindungen
# zu Seiten, die nie jemand geoeffnet hat - IP und Zeitpunkt inklusive. Bei
# einer Medizinfrage genau die Sorte Angabe, die man nicht streut. Und es
# haette aufgehoben, wofuer DuckDuckGo hier ueberhaupt benutzt wird.
pruefe('quelle_melden("web"' in
       (WURZEL / "jarvis" / "tools.py").read_text(encoding="utf-8"),
       "search_web meldet Treffer als art 'web'")
pruefe('q.art === "seite" ? "seite" : "web"' in js,
       "die Oberflaeche behaelt die Art, statt alles auf 'seite' einzudampfen",
       "vorher war der Unterschied weg, bevor ihn jemand auswerten konnte")
pruefe("function quellschild(schluessel, geholt)" in js,
       "das Schild weiss, ob die Seite geholt wurde")
pruefe("if (geholt" in js,
       "und laedt nur dann ein Favicon nach")
pruefe('q.art !== "web"' in js, "art 'web' zaehlt als nicht geholt")
# Dieselbe Seite einmal geholt, einmal nur als Treffer: dann war jemand
# dort, und das Favicon verraet nichts Neues.
pruefe("da.geholt = da.geholt || geholt" in js,
       "einmal geholt reicht, wenn die Seite doppelt vorkommt")

print("\n=== Drei Formulierungen je Werkzeug ===")
# Damit die Anzeige nicht traege wirkt: wer zweimal hintereinander dasselbe
# liest, haelt es fuer eine haengende Anzeige.
#
# Und der eigentliche Fund: die Liste war veraltet. post, code, bild,
# set_reminder und browser gibt es als Werkzeug nicht mehr, zehn andere
# fehlten - darunter search_images und pubmed. Dort stand dann "Jarvis
# benutzt search_images …", der Funktionsname also, den die Liste gerade
# vermeiden soll. Deshalb wird sie hier an der ECHTEN Werkzeugliste
# gemessen und nicht an sich selbst.
worte = js.split("const WERKZEUGWORTE = {")[1].split("\n};")[0]
eintraege = dict(re.findall(r"^\s*(\w+):\s*\[(.*)\],\s*$", worte, re.M))
pruefe(bool(eintraege), f"{len(eintraege)} Werkzeuge in der Liste")

fehlend = sorted(set(tools.REGISTRY) - set(eintraege))
pruefe(not fehlend, "jedes echte Werkzeug hat Worte", str(fehlend))
ueberzaehlig = sorted(set(eintraege) - set(tools.REGISTRY))
pruefe(not ueberzaehlig, "und keine Leiche in der Liste", str(ueberzaehlig))

for name, inhalt in sorted(eintraege.items()):
    stuecke = [s for s in re.findall(r'"([^"]+)"', inhalt) if s.strip()]
    pruefe(len(stuecke) >= 3, f"{name}: {len(stuecke)} Formulierungen",
           inhalt[:70])
    pruefe(len(set(stuecke)) == len(stuecke),
           f"{name}: keine doppelt", str(stuecke))

pruefe("function werkzeugwort" in js, "es wird gewechselt")
pruefe("function werkzeugName" in js,
       "die Beschriftung im Nachhinein wechselt NICHT mit",
       "sonst heisst dasselbe Werkzeug in der Liste anders als eben im Reaktor")
pruefe("WARTEWORTE" in js, "auch das Warten hat mehrere Formulierungen")

print(f"\n  {fehler} Fehler")
raise SystemExit(1 if fehler else 0)
