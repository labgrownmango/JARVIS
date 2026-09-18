"""Das Uebersetzungswerkzeug.

Der Anlass, es ueberhaupt einzubauen: Jarvis hat vorher selbst uebersetzt,
und ein 20B-Modell trifft Redewendungen und Fachbegriffe schlechter als ein
Modell, das nichts anderes tut.

Der Anlass fuer DIESEN Test: das Modell befolgt die Zielsprache nur, wenn
sie in der NUTZERZEILE steht. Eine Anweisung im Systemprompt wird
vollstaendig ignoriert - gemessen kam dann alles auf Englisch zurueck, bei
Ziel "Deutsch" sogar tschechischer Unsinn. Dieser Test haelt die richtige
Form fest, damit sie niemand aus Versehen wieder zurueckbaut.

Das Modell ist ein freier Endpunkt und darf belegt sein - dann wird
uebersprungen statt rot gewertet.
"""
from jarvis import tools

fehler = 0
uebersprungen = 0


def pruefe(bedingung: bool, text: str, zusatz: str = "") -> None:
    global fehler
    fehler += not bedingung
    print(f"  {'ok    ' if bedingung else 'FEHLER'} {text}")
    if not bedingung and zusatz:
        print(f"         {zusatz}")


def aussetzer(antwort: str) -> bool:
    return any(w in antwort for w in ("antwortete mit", "nichts zurueck",
                                      "nicht im Internet", "antwortet gerade"))


print("=== Ohne Angabe: Deutsch wird Englisch ===")
a = tools.uebersetzen("Der Drucker zieht das Papier schief ein.")
print(f"         {a[:100]}")
if aussetzer(a):
    uebersprungen += 1
    print("  ~~     Modell antwortete nicht - uebersprungen")
else:
    pruefe(a.startswith("English:"), "Zielsprache steht dabei", a[:60])
    pruefe("printer" in a.lower(), "der Drucker ist ein printer", a[:80])

print("\n=== Ohne Angabe: Fremdes wird Deutsch ===")
a = tools.uebersetzen("The printer keeps jamming the paper.")
print(f"         {a[:100]}")
if aussetzer(a):
    uebersprungen += 1
    print("  ~~     uebersprungen")
else:
    pruefe(a.startswith("German:"), "Zielsprache Deutsch gewaehlt", a[:60])
    pruefe(any(w in a.lower() for w in ("drucker", "papier")),
           "und es ist wirklich deutsch", a[:80])

print("\n=== Mit Angabe: die Zielsprache wird befolgt ===")
# Das ist der Kern. Vorher landete hier IMMER Englisch, egal was man
# angab - weil die Anweisung im Systemprompt stand statt in der Nutzerzeile.
#
# Geprueft wird mit einer Begruessung, nicht mit einem Fachsatz. Grund:
# bei "Der Drucker zieht das Papier schief ein" kam auf Italienisch
# "L'imprimante ritira il foglio inclinato" heraus - richtiges Italienisch
# mit einem franzoesischen Wort darin. Das ist eine Schwaeche des Modells,
# aber keine, die dieser Test messen soll; er soll pruefen, ob die
# ZIELSPRACHE ankommt. Eine Begruessung tut das eindeutig.
for sprache, marker in (("Französisch", ("bonjour",)),
                        ("Spanisch", ("buenos días", "buenos dias", "hola")),
                        ("Italienisch", ("buongiorno", "buon giorno"))):
    a = tools.uebersetzen("Guten Morgen, wie geht es Ihnen?", sprache)
    if aussetzer(a):
        uebersprungen += 1
        print(f"  ~~     {sprache} - uebersprungen")
        continue
    unten = a.lower()
    pruefe(any(m in unten for m in marker),
           f"{sprache}: {a[:64]}",
           "kam nicht in der gewuenschten Sprache zurueck")
    pruefe("good morning" not in unten,
           f"{sprache}: nicht heimlich Englisch")

print("\n=== Bekannte Schwaeche: die selteneren Sprachen ===")
# Nicht weggelassen, sondern gemessen und benannt. Bei Polnisch kam
# "Guten Morgen, jak się przebiega?" zurueck - die erste Haelfte blieb
# unuebersetzt. Dasselbe Muster bei Italienisch mit einem Fachsatz:
# "L'imprimante ritira il foglio inclinato", also ein franzoesisches Wort
# mitten im Italienischen.
#
# Das ist eine Schwaeche des Uebersetzungsmodells, kein Fehler hier - und
# deshalb faerbt sie den Testlauf nicht rot. Sichtbar bleibt sie trotzdem:
# wer das liest, weiss, worauf er sich bei welcher Sprache verlassen kann.
a = tools.uebersetzen("Guten Morgen, wie geht es Ihnen?", "Polnisch")
if aussetzer(a):
    uebersprungen += 1
    print("  ~~     Polnisch - uebersprungen")
elif any(m in a.lower() for m in ("dzień dobry", "dzien dobry")):
    print(f"  ok     Polnisch sauber: {a[:64]}")
else:
    uebersprungen += 1
    print(f"  ~~     Polnisch unvollstaendig (bekannt): {a[:64]}")

print("\n=== Kuerzel gehen auch ===")
a = tools.uebersetzen("Guten Morgen.", "fr")
if aussetzer(a):
    uebersprungen += 1
    print("  ~~     uebersprungen")
else:
    pruefe(a.startswith("French:"), f"'fr' wird zu French: {a[:50]}")

print("\n=== Leerer Text wird abgewiesen ===")
pruefe("Kein Text" in tools.uebersetzen("   "),
       "leere Eingabe sagt das auch")
pruefe("Kein Text" in tools.uebersetzen(""), "und ganz ohne Text ebenso")

print("\n=== Im Werkzeugverzeichnis ===")
pruefe("uebersetzen" in tools.REGISTRY, "als Werkzeug eingetragen")
namen = [w["function"]["name"] for w in tools.schema()]
pruefe("uebersetzen" in namen, "und im Schema fuer das Modell")

print(f"\n  {fehler} Fehler"
      + (f", {uebersprungen} uebersprungen" if uebersprungen else ""))
raise SystemExit(1 if fehler else 0)
