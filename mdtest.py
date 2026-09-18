"""Die Markdown-Darstellung darf keine Lücke aufreissen.

Der Text, der dort ankommt, stammt mittelbar aus dem Netz: Suchtreffer,
Seiteninhalte, Nachrichtenbetreffe. Wird er als HTML eingesetzt, ist das die
klassische Luecke - dann reicht ein <img src=x onerror=...> in irgendeinem
Suchergebnis.

Ein echter Testlauf im Browser ist hier nicht moeglich: auf diesem Rechner
ist kein Node installiert, und die Oberflaeche laeuft nur im Browser. Geprueft
wird deshalb die Bauweise - dass die betreffenden Funktionen ausschliesslich
Knoten bauen und nirgends innerHTML beschreiben. Das ist schwaecher als ein
Ablauftest, aber es faengt genau den Fehler ab, der hier teuer waere: dass
jemand spaeter aus Bequemlichkeit ein innerHTML einbaut.

Im Browser nachgemessen (13.09.2026), mit diesem Eingabetext:
    Text mit [gut](https://example.com) und [boese](javascript:alert(1))
    sowie <img src=x onerror=alert(1)> und **fett**.
Ergebnis: ein einziger Link (https://example.com), null Bilder, das
javascript: blieb Text, und das img-Tag kam als &lt;img ...&gt; an.
"""
import re
import re as _re
from pathlib import Path

DATEI = Path(__file__).parent / "oberflaeche" / "jarvis.js"
quelle = DATEI.read_text(encoding="utf-8")
fehler = 0


def pruefe(bedingung: bool, text: str, zusatz: str = "") -> None:
    global fehler
    fehler += not bedingung
    print(f"  {'ok    ' if bedingung else 'FEHLER'} {text}")
    if not bedingung and zusatz:
        print(f"         {zusatz}")


def funktion(name: str) -> str:
    """Den Rumpf einer Funktion herausschneiden - ueber die Klammerbilanz."""
    start = quelle.find(f"function {name}(")
    if start < 0:
        return ""
    auf = quelle.find("{", start)
    tiefe, i = 0, auf
    while i < len(quelle):
        if quelle[i] == "{":
            tiefe += 1
        elif quelle[i] == "}":
            tiefe -= 1
            if tiefe == 0:
                return quelle[auf:i + 1]
        i += 1
    return quelle[auf:]


print("=== Die Funktionen gibt es ueberhaupt ===")
NAMEN = ["markdownSetzen", "mdZeile", "mdTabelle", "inhaltSetzen",
         "linkErlaubt", "bildErlaubt"]
for name in NAMEN:
    pruefe(bool(funktion(name)), f"{name} gefunden")

print("\n=== Kein innerHTML im Markdown-Weg ===")
# Hier wird fremder Text verarbeitet. Ein innerHTML an dieser Stelle waere
# genau die Luecke, um die es geht.
for name in ("markdownSetzen", "mdZeile", "mdTabelle", "inhaltSetzen"):
    rumpf = funktion(name)
    pruefe("innerHTML" not in rumpf, f"{name} schreibt kein innerHTML",
           [z.strip() for z in rumpf.splitlines() if "innerHTML" in z][:2])
    pruefe("outerHTML" not in rumpf and "insertAdjacentHTML" not in rumpf,
           f"{name} auch sonst kein HTML aus Text")

print("\n=== Text wird als Text eingesetzt ===")
# mdTabelle baut keine Textknoten selbst, sondern reicht jede Zelle an
# mdZeile weiter - das ist richtig so und war beim ersten Anlauf eine
# falsche Testerwartung, kein Fehler im Code.
pruefe("createTextNode" in funktion("mdZeile"), "mdZeile baut Textknoten")
pruefe("mdZeile(" in funktion("mdTabelle"),
       "mdTabelle reicht die Zellen an mdZeile weiter")
pruefe("createElement" in funktion("mdTabelle"),
       "und baut die Tabelle aus einzelnen Elementen")

print("\n=== Adressen werden geprueft ===")
rumpf = funktion("linkErlaubt")
pruefe("new URL" in rumpf, "die Adresse wird wirklich zerlegt, nicht geraten")
pruefe("https:" in rumpf and "http:" in rumpf,
       "nur http und https gelten als erlaubt")
# javascript: und data: duerfen nicht durchkommen - das ergibt sich aus der
# Positivliste, aber der Test sagt es ausdruecklich.
pruefe("protocol" in rumpf,
       "geprueft wird das Protokoll, nicht der Anfang der Zeichenkette")

rumpf = funktion("bildErlaubt")
pruefe("svg" in rumpf.lower(),
       "SVG bleibt draussen - es kann Skripte enthalten")

print("\n=== Der Link im Dokument haengt nicht am Fenster ===")
zeile = [z for z in quelle.splitlines() if "noopener" in z]
pruefe(bool(zeile), "Links bekommen rel=noopener", "fehlt")
pruefe(any("noreferrer" in z for z in zeile),
       "und noreferrer - die fremde Seite erfaehrt nicht, woher der Klick kam")

print("\n=== Die Sprachausgabe liest keine Sternchen vor ===")
rumpf = funktion("inhaltSetzen")
pruefe("gesprochen" in rumpf, "es gibt einen eigenen Text zum Vorlesen")
pruefe("```" in rumpf or "Codeblock" in rumpf,
       "Codebloecke werden beim Vorlesen ersetzt, nicht buchstabiert")

print("\n=== LaTeX wird lesbar gemacht, nicht angezeigt ===")
# Gemeldet aus dem Betrieb, so stand es im Fenster:
#
#     Dann nutzt du die Formel
#     \[
#     A = \pi \times r^{2}
#     \]
#
# Eine Formelbibliothek (KaTeX, MathJax) waere der uebliche Weg und kommt
# nicht in Frage: fremdes Skript, und die Sicherheitsrichtlinie laesst nur
# eigene zu. Also umrechnen statt darstellen - "A = π × r²" ist im
# Chatfenster ohnehin besser lesbar, und die Stimme kann es vorlesen.
pruefe("function formelnLesbar" in quelle, "es gibt eine Umrechnung")
pruefe("formelnLesbar(text)" in funktion("inhaltSetzen"),
       "und sie greift VOR Anzeige, Kopieren und Vorlesen",
       "sonst bekommt der Kopierknopf '\\pi' und die Stimme liest "
       "'Backslash pi'")

# Kein Skript von aussen - das waere der bequeme Weg gewesen.
#
# Geprueft OHNE die Kommentare. Die erste Fassung durchsuchte die ganze
# Datei und schlug an meinem eigenen Kommentar an, der erklaert, WARUM
# keine Formelbibliothek benutzt wird - der Test faerbte also rot, weil die
# Begruendung dasteht. Das ist heute der sechste Test, der an der
# Schreibweise des Quelltextes scheitert statt an der Sache.
_ohne_kommentar = _re.sub(r"/\*.*?\*/", " ", quelle, flags=_re.S)
_ohne_kommentar = "\n".join(z for z in _ohne_kommentar.splitlines()
                            if not z.strip().startswith("//"))
for dienst in ("katex", "mathjax", "cdn.jsdelivr", "unpkg"):
    pruefe(dienst not in _ohne_kommentar.lower(),
           f"keine Formelbibliothek von {dienst}")

# Die beiden Faelle, die mein eigener Test gefunden hat, BEVOR sie jemand
# gesehen hat - beide standen in der ersten Fassung drin:
rumpf_formel = funktion("formelnLesbar")
pruefe("includes(\"\\\\\")" in rumpf_formel or 'includes("\\\\")' in rumpf_formel,
       "einzelnes $...$ nur mit echtem LaTeX darin",
       "sonst wird aus 'Kosten $19 bis $25' ein 'Kosten 19 bis25'")
pruefe("runde" in rumpf_formel,
       "mehrere Durchgaenge fuer verschachtelte Formeln",
       "ein \\frac mit \\sqrt im Zaehler passt beim ersten Mal auf kein Muster")
pruefe("function klammern" in quelle,
       "Klammern nur, wo sie gebraucht werden (3/4, nicht (3)/(4))")

print(f"\n  {fehler} Fehler")
raise SystemExit(1 if fehler else 0)
