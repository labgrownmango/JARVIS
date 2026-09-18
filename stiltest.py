"""Antwortet Jarvis anders, je nachdem ob vorgelesen oder gelesen wird?

Der Anlass, gemeldet von Mini-Jost. Auf "Was kannst du mir ueber die
Automarke Porsche sagen?" kamen drei Saetze und dann:

    "Weitere Details finden Sie im Wikipedia-Artikel."

Zwei Beschwerden, eine Wurzel. Im Systemprompt stand fest:

    "Antworten sind fuer Sprachausgabe gedacht: keine Listen, keine
     Markdown-Zeichen, keine Emojis, keine Code-Bloecke. Ein bis drei
     Saetze, ausser es wird mehr verlangt."

Fuer eine Stimme ist das richtig - eine vorgelesene Aufzaehlung ist Unsinn.
Nur trifft die Annahme nicht: J. Kaiser tippt, und die Oberflaeche stellt
Markdown vollstaendig dar. Vorgelesen wird erst auf Knopfdruck. Der Prompt
verbot also genau das, wofuer die Oberflaeche gebaut wurde.

Jetzt haengt der Stil an der Betriebsart. Dieser Test haelt fest, dass die
Umschaltung existiert, in beide Richtungen wirkt und wirklich bis zum Modell
durchkommt. Der letzte Abschnitt braucht Netz; faellt der Endpunkt aus, wird
er uebersprungen statt rot gewertet.
"""
import inspect
import sys

from jarvis import brain as brain_modul
from jarvis import config

# Dieser Test druckt Modellantworten, und die bringen Zeichen mit, die es in
# cp1252 nicht gibt. Gemeldet von Mini-Jost: ein U+202F (schmales
# geschuetztes Leerzeichen) mitten in einer Antwort liess den Test mit
# UnicodeEncodeError abstuerzen - ausgerechnet in der Zeile, die den GRUND
# des Fehlschlags zeigen soll. Statt eines Ergebnisses stand dort ein
# Rueckverfolgungsprotokoll.
#
# "replace": ein Zeichen, das die Konsole nicht kann, wird zum Fragezeichen.
# Haesslich und voellig ausreichend - ein Testlauf darf nicht an der
# Schriftart der Konsole scheitern. Im Reihenlauf setzt pruefen.py dasselbe
# ueber PYTHONIOENCODING; das hier ist fuer den Einzelaufruf.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

fehler = 0
uebersprungen = 0


def pruefe(bedingung: bool, text: str, zusatz: str = "") -> None:
    global fehler
    fehler += not bedingung
    print(f"  {'ok    ' if bedingung else 'FEHLER'} {text}")
    if not bedingung and zusatz:
        # Zweiter Gurt: reconfigure kann fehlschlagen (umgeleitete Ausgabe,
        # aeltere Umgebung). Dann darf die Begruendung notfalls unleserlich
        # sein - aber der Lauf muss weitergehen.
        try:
            print(f"         {zusatz}")
        except UnicodeEncodeError:
            print("         " + str(zusatz).encode("ascii", "replace").decode())


print("=== Der feste Satzdeckel steht nicht mehr im Prompt ===")
# "Ein bis drei Saetze" galt frueher IMMER - auch im Chatfenster.
pruefe("Ein bis drei Sätze" not in config.SYSTEM_PROMPT,
       "kein fester Satzdeckel mehr im Systemprompt")
pruefe("keine Markdown-Zeichen" not in config.SYSTEM_PROMPT,
       "kein pauschales Markdown-Verbot mehr im Systemprompt")

print("\n=== Statt dessen zwei Fassungen ===")
gesprochen = config.stil(True)
getippt = config.stil(False)
pruefe(gesprochen != getippt, "gesprochen und getippt sind verschieden")

# Die Bloecke sind umbrochen - "Kein Satzdeckel" steht ueber zwei Zeilen.
# Ohne das Zusammenziehen prueft dieser Test die Zeilenbreite mit, nicht den
# Inhalt. (Genau daran ist er beim ersten Lauf gescheitert: meine Erwartung
# war falsch, nicht der Prompt.)
glatt_gesprochen = " ".join(gesprochen.split())
glatt_getippt = " ".join(getippt.split())

print("\n  Gesprochen:")
pruefe("VORGELESEN" in glatt_gesprochen, "sagt deutlich, dass vorgelesen wird")
pruefe("Ein bis drei Saetze" in glatt_gesprochen, "haelt den Satzdeckel")
for wort in ("Listen", "Markdown", "Code-Bloecke"):
    pruefe(wort in glatt_gesprochen, f"verbietet {wort}")

print("\n  Getippt:")
pruefe("GELESEN" in glatt_getippt, "sagt deutlich, dass gelesen wird")
pruefe("Markdown" in glatt_getippt and "darfst" in glatt_getippt,
       "erlaubt Markdown ausdruecklich")
pruefe("Kein Satzdeckel" in glatt_getippt, "hebt den Satzdeckel auf")
# Laenger heisst nicht geschwaetziger - das muss drinstehen, sonst wird aus
# der Erlaubnis eine Einladung zum Anlauf nehmen.
pruefe("knapp" in glatt_getippt.lower(), "bleibt trotzdem knapp")

print("\n=== Der Verweis auf eine Quelle statt einer Antwort ===")
pruefe("Weitere Details finden" in config.SYSTEM_PROMPT,
       "der gemeldete Satz steht als Gegenbeispiel im Prompt")

print("\n=== ask() nimmt die Betriebsart entgegen ===")
unterschrift = inspect.signature(brain_modul.Brain.ask)
pruefe("gesprochen" in unterschrift.parameters, "ask hat den Schalter")
if "gesprochen" in unterschrift.parameters:
    pruefe(unterschrift.parameters["gesprochen"].default is None,
           "Vorgabe None - laesst die letzte Einstellung stehen")

print("\n=== Und er landet wirklich im Systemprompt ===")
if not config.API_KEY:
    print("  ~~     kein API-Key - uebersprungen")
    uebersprungen += 1
else:
    kopf = brain_modul.Brain()
    for wert, erwartet, nicht in ((True, gesprochen, getippt),
                                  (False, getippt, gesprochen)):
        kopf._gesprochen = wert
        gebaut = kopf._prompt_mit_gedaechtnis()
        pruefe(erwartet in gebaut,
               f"_gesprochen={wert}: die richtige Fassung steht drin")
        pruefe(nicht not in gebaut,
               f"_gesprochen={wert}: die andere steht NICHT drin")

    # Der Hinweis darf sich nicht mit jeder Frage stapeln - deshalb steht er
    # im Systemprompt und nicht im Verlauf.
    kopf._gesprochen = False
    pruefe(kopf._prompt_mit_gedaechtnis().count("Diese Antwort wird") == 1,
           "steht genau einmal drin, nicht mehrfach")

print("\n=== Das Aufraeumen fuer die Sprachausgabe ===")
# Das ist der Teil, der NICHT von der Tagesform des Modells abhaengt.
from jarvis.sprache import ohne_gliederung  # noqa: E402

PROBEN = [
    ("**Porsche AG**\n- Gruendung 1931\n- Sitz Stuttgart",
     ["Porsche AG", "Gruendung 1931", "Sitz Stuttgart"]),
    ("## Ueberschrift\n\nEin Satz.", ["Ueberschrift", "Ein Satz."]),
    ("1. Erstens\n2. Zweitens", ["Erstens", "Zweitens"]),
    ("Ein `Befehl` und *kursiv*.", ["Befehl", "kursiv"]),
    ("> Ein Zitat.", ["Ein Zitat."]),
]
for roh, muss_drin in PROBEN:
    sauber = ohne_gliederung(roh)
    hat = any(z in sauber for z in ("**", "##", "- ", "`", "> ", "|"))
    pruefe(not hat, f"geputzt: {sauber[:60]!r}", f"aus {roh!r}")
    for stueck in muss_drin:
        pruefe(stueck in sauber, f"  Inhalt bleibt: {stueck!r}", sauber[:80])

# Aufzaehlungspunkte muessen zu Saetzen werden, sonst kleben sie aneinander
pruefe("Gruendung 1931. Sitz Stuttgart" in
       ohne_gliederung("- Gruendung 1931\n- Sitz Stuttgart"),
       "aus Punkten werden Saetze, nicht ein Wortbrei",
       ohne_gliederung("- Gruendung 1931\n- Sitz Stuttgart"))

# Und ein normaler Text darf NICHT angefasst werden
glatt = "Porsche ist ein Hersteller aus Stuttgart. Gegruendet 1931."
pruefe(ohne_gliederung(glatt) == glatt,
       "Fliesstext bleibt unveraendert", ohne_gliederung(glatt))

print("\n=== Kommt es beim Modell an? ===")
# Die eigentliche Probe: dieselbe Frage, zweimal, nur die Betriebsart
# unterschiedlich. Gesprochen muss kurz und zeichenlos sein, getippt darf
# laenger und gegliedert sein.
# Die Frage muss NEUTRAL sein. Die erste Fassung lautete "Erklaer mir in
# einer Uebersicht ... und wie seine vier Takte heissen" - die verlangt eine
# Aufzaehlung ausdruecklich, und genau das erlaubt der gesprochene Block
# ("ausser es wird ausdruecklich mehr verlangt"). Der Test bestrafte Jarvis
# also dafuer, meine eigene Regel zu befolgen. Gemessen: 1176 Zeichen
# gesprochen gegen 1233 getippt - kein Unterschied, weil die Frage beide
# Male dasselbe erzwang.
#
# Es ist die Frage, die den Anlass gab. Sie verlangt nichts Bestimmtes.
FRAGE = "Was kannst du mir über die Automarke Porsche sagen?"


def aussetzer(text: str) -> bool:
    return not text.strip() or "antwortete mit" in text


# Gliederung erkennt man an der POSITION, nicht am Vorkommen.
#
# Die erste Fassung suchte schlicht nach "- ", "* ", "#", "1." und "**"
# irgendwo im Text. Das faerbte den Test rot bei:
#
#     "... hat sich auf Sport- und Luxuswagen spezialisiert."
#
# Die deutsche Bindestrich-Ellipse. Genauso "Vor- und Nachteile", "Ein- und
# Ausgabe", "am 1. September". Die gesprochene Antwort war einwandfreier
# Fliesstext, sprache.ohne_gliederung() hatte richtig gearbeitet - der Test
# hat sich geirrt, nicht der Code.
#
# Ein Aufzaehlungspunkt steht am ZEILENANFANG. Nur "**" braucht keine
# Position: fette Auszeichnung kommt im Deutschen nicht zufaellig vor.
import re  # noqa: E402

_GLIEDERUNG = re.compile(
    # (?m) nur EINMAL und ganz vorn - Python lehnt eine Flagge mitten im
    # Ausdruck ab ("global flags not at the start of the expression").
    r"(?m)"
    r"^[ \t]*(?:[-*+•][ \t]|\d+[.)][ \t]|#{1,6}[ \t]|>[ \t]|\|)"
    r"|\*\*"
    r"|```")


def gegliedert(text: str) -> bool:
    return bool(_GLIEDERUNG.search(text or ""))


# Der Erkenner prueft sich zuerst selbst - ohne Netz, ohne Modell. Heute
# haben mich zwei ungeprueffte Erkenner in die Irre gefuehrt: der fuer
# "verlangt er eine Entschuldigung" (zu weit) und dieser hier (zu weit).
# Ein Erkenner, der selbst ungeprueft ist, misst die Tagesform des Modells
# und die eigenen Luecken zugleich - und hinterher weiss niemand, welche
# von beiden rot war.
print("\n=== Der Gliederungs-Erkenner an sich selbst ===")
for probe in ("- Ein Punkt\n- Noch einer",
              "1. Erstens\n2. Zweitens",
              "## Ueberschrift",
              "Das ist **fett**.",
              "> Ein Zitat",
              "* Sternchenpunkt"):
    pruefe(gegliedert(probe), f"erkannt: {probe.splitlines()[0][:34]!r}")

for probe in ("Sport- und Luxuswagen, seit 1947.",      # der gemeldete Fall
              "Vor- und Nachteile abgewogen.",
              "Ein- und Ausgabe geprueft.",
              "Am 1. September 2026 verkauft.",
              "Stuttgart-Zuffenhausen ist der Sitz.",
              "Porsche ist ein Hersteller aus Stuttgart."):
    pruefe(not gegliedert(probe), f"kein Fehlalarm: {probe[:34]!r}")


if not config.API_KEY:
    print("  ~~     kein API-Key - uebersprungen")
    uebersprungen += 1
else:
    # DREI Paare, nicht eines. Ein einzelnes Paar traegt nicht: gemessen
    # kippte es hier einmal (gesprochen 632 gegen getippt 583), waehrend
    # ueber fuenf Paare hinweg KEINES umgedreht war und der Abstand deutlich
    # blieb (Mittel 467 gegen 1304).
    #
    # Die erste Fassung dieses Tests mass ein Paar und leitete daraus
    # "die Umschaltung ist belegt" ab. Das war derselbe Fehler, den ich hier
    # schon zweimal gemacht habe - aus einem Lauf eine Aussage machen.
    PAARE = 3
    kurze, lange = [], []
    modelle = set()
    for _ in range(PAARE):
        paar = {}
        for wert in (True, False):
            kopf = brain_modul.Brain()
            try:
                paar[wert] = kopf.ask(FRAGE, gesprochen=wert)
            except Exception as exc:
                paar[wert] = ""
                print(f"  ~~     {type(exc).__name__}: {exc}")
            # Nach dem Aufruf, nicht davor: bei Belegung weicht Brain mitten
            # drin auf ein anderes Modell aus, und dann hat das andere
            # geantwortet.
            modelle.add(kopf.model)
        if not aussetzer(paar.get(True, "")) and not aussetzer(paar.get(False, "")):
            kurze.append(paar[True])
            lange.append(paar[False])

    if not kurze:
        print("  ~~     Modell antwortete nicht - uebersprungen")
        uebersprungen += 1
    else:
        for i, (k, l) in enumerate(zip(kurze, lange), 1):
            print(f"         Paar {i}: gesprochen {len(k):5}   "
                  f"getippt {len(l):5}"
                  + ("   UMGEDREHT" if len(l) <= len(k) else ""))
        # Ohne diese Zeile ist die Messung blind. Die Modellwahl steht auf
        # "reihenfolge", vier Modelle stehen zur Wahl, und bei Belegung wird
        # gewechselt - dann misst man zwei verschiedene Modelle gegeneinander
        # und haelt das Ergebnis fuer eine Aussage ueber den Prompt.
        print(f"         Modell(e): {', '.join(sorted(modelle))}")
        if len(modelle) > 1:
            print("  ~~     ACHTUNG: mehrere Modelle im Spiel - der "
                  "Vergleich sagt wenig ueber den Prompt aus")

        # Das laengste gesprochene gegen das laengste getippte waere
        # zufallsanfaellig; die Mittel sind es weniger.
        mittel_kurz = sum(len(k) for k in kurze) / len(kurze)
        mittel_lang = sum(len(l) for l in lange) / len(lange)
        # Der strengste Fall fuers Putzen: die laengste gesprochene Antwort.
        kurz = max(kurze, key=len)
        hat_kurz = any(gegliedert(a) for a in kurze)
        hat_lang = gegliedert(lange[0])
        # HART geprueft: im gesprochenen Betrieb raeumt sprache.ohne_
        # gliederung() auf, unabhaengig vom Modell. Bleibt hier etwas
        # stehen, ist das ein echter Fehler.
        pruefe(not hat_kurz,
               "gesprochen: keine Gliederungszeichen",
               kurz[:200])

        # NUR BERICHTET, nicht geprueft. Ob das Modell die eingeraeumte
        # Freiheit auch nutzt, schwankt: auf Mini-Jost kam in zwei von vier
        # Laeufen keine Gliederung, hier ebenfalls nicht immer - und zwar
        # mit demselben Modell. Eine Anweisung im Prompt ist eine Bitte,
        # keine Garantie; daraus eine Pruefung zu machen hiesse, die
        # Tagesform des Modells zu messen und Jarvis dafuer rot zu faerben.
        #
        # Erzwingen laesst es sich nicht sinnvoll: kuenstlich Aufzaehlungs-
        # punkte einzusetzen, wo das Modell Fliesstext geschrieben hat,
        # waere schlechter als der Fliesstext.
        print(f"  {'ok    ' if hat_lang else '~~    '} "
              f"getippt: {'gegliedert' if hat_lang else 'Fliesstext'} "
              f"(nur beobachtet, kein Pruefstein)")
        # BEWUSST relativ und ueber MEHRERE Paare - beides muss so bleiben.
        #
        # Keine feste Zahl: auf Empfang02 lagen die Baender bei 376-593
        # gegen 943-1673, auf Mini-Jost bei 323-663 gegen 554-1254. Eine
        # Schwelle wie "getippt muss ueber 700 liegen" haette dort rot
        # gefaerbt, ohne dass etwas kaputt war.
        #
        # Und nicht nur ein Paar: gemessen kippte ein einzelnes Paar hier
        # einmal (632 gegen 583), waehrend ueber fuenf Paare hinweg keines
        # umgedreht war. Geprueft wird die RICHTUNG im Mittel, nicht die
        # Groesse und nicht ein Einzelfall.
        pruefe(mittel_lang > mittel_kurz,
               f"getippt ist im Mittel ausfuehrlicher "
               f"({mittel_lang:.0f} > {mittel_kurz:.0f}, {len(kurze)} Paare)")

print(f"\n  {fehler} Fehler"
      + (f", {uebersprungen} uebersprungen" if uebersprungen else ""))
raise SystemExit(1 if fehler else 0)
