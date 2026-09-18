"""Prüft, dass Selbstgespräch des Modells nicht in der Antwort landet.

Beobachtet im Betrieb: "Need answer.Laut Wikipedia waren die Hauptakteure..."
Das englische Stück davor ist der Denkkanal von gpt-oss, der in den sichtbaren
Text rutscht. Wichtiger als das Wegschneiden ist hier aber die Gegenprobe: ein
echter Satz darf NIE gekürzt werden. Lieber ein Denkrest zu viel stehen lassen
als einem Nutzer den Anfang seiner Antwort klauen.
"""
from jarvis.brain import Brain, denkrest_entfernen

fehler = 0


class Stueck:
    """Ein Haeppchen aus dem Stream - so wie es das SDK liefert."""

    def __init__(self, text=None, werkzeug=None):
        self.choices = [self]
        self.delta = self
        self.content = text
        self.tool_calls = []
        if werkzeug:
            class Funktion:
                name = werkzeug
                arguments = "{}"
            class Ruf:
                index = 0
                id = "c1"
                function = Funktion()
            self.tool_calls = [Ruf()]


def sammeln(stuecke):
    """Laesst _collect ueber einen erfundenen Stream laufen.

    Gibt (Antworttext, Gedachtes) zurueck - also genau die Trennung, um die
    es geht.
    """
    brain = Brain.__new__(Brain)          # ohne API-Schluessel
    brain._gen = 1
    brain._laeuft = True
    antwort, gedacht = [], []
    text, _calls = brain._collect(
        iter(stuecke), 1, lambda s: None,
        antwort.append, gedacht.append)
    return text, " ".join(gedacht)

WEG = [
    ("Need answer.Laut Wikipedia waren die Hauptakteure al-Qaida.",
     "Laut Wikipedia waren die Hauptakteure al-Qaida."),
    ("We need to answer the question briefly. Der Arbeitsspeicher liegt bei "
     "achtzig Prozent.",
     "Der Arbeitsspeicher liegt bei achtzig Prozent."),
    ("The user asks about the weather. In Düsseldorf sind es zwölf Grad.",
     "In Düsseldorf sind es zwölf Grad."),
    ("Answer in German. Es ist kurz nach acht, Sir.",
     "Es ist kurz nach acht, Sir."),
    ("<|channel|>analysis<|message|>Need answer.Alles läuft, Sir.",
     "Alles läuft, Sir."),
    ("Let's check. Need answer.Die Festplatte ist zu neunzig Prozent voll.",
     "Die Festplatte ist zu neunzig Prozent voll."),
]

# Diese Sätze sind echte Antworten - hier darf nichts verschwinden
BLEIBT = [
    "Der Arbeitsspeicher liegt bei siebenundachtzig Prozent, Sir.",
    "Ich brauche dafür noch einen Moment.",
    "Let's Dance läuft heute Abend um 20:15 Uhr.",
    "I need a break, sagte er - übersetzt: er braucht eine Pause.",
    "Need for Speed ist installiert.",
    "Die Antwort lautet: 391.",
    "Answer ist das englische Wort für Antwort.",
    "",
    # Diese sechs hat ein früherer Filter zerschnitten. Sie standen nicht im
    # Test, weil alle Probesätze aus genau EINEM Satz bestanden - und bei
    # einem einzigen Satz rettete die Notbremse ("wenn nichts übrig bleibt,
    # nimm das Original") das Ergebnis. Erst ein zweiter Satz dahinter zeigte
    # den Fehler: aus "Lets Encrypt hat das Zertifikat erneuert. Alles gut."
    # wurde "Alles gut."
    "Lets Encrypt hat das Zertifikat erneuert. Alles gut, Sir.",
    "I need a break: er braucht eine Pause. Dann geht es weiter.",
    "I should mention: die Platte ist voll. Aufräumen wäre gut.",
    "The user is King läuft im Radio. Soll ich lauter machen?",
    "Lets Dance war gestern. Heute läuft nichts.",
    "Need for Speed ist installiert. Soll ich es starten?",
]

def pruefe(bedingung: bool, text: str, zusatz: str = "") -> None:
    global fehler
    fehler += not bedingung
    print(f"  {'ok    ' if bedingung else 'FEHLER'} {text}")
    if not bedingung and zusatz:
        print(f"         {zusatz}")


print("=== Lautes Denken landet nicht in der Antwort ===")
# Der gemessene Fall, wortwoertlich. Auf "wieviele Testosteron-Derivate gibt
# es" kam: "We need answer: how many testosterone derivatives. Likely many;
# not countable. ... Let's search web." - und das stand IN der Antwort. Der
# alte Griff hielt nur 80 Zeichen zurueck; laengeres Selbstgespraech rutschte
# durch.
antwort, gedacht = sammeln([
    Stueck("We need answer: how many testosterone derivatives. "),
    Stueck("Likely many; not countable. But question likely expects number "),
    Stueck("of known derivatives. Wikipedia might list. Let's search web."),
    Stueck(werkzeug="search_web"),
])
pruefe(antwort == "", f"nichts davon in der Antwort ({antwort[:60]!r})")
pruefe("testosterone derivatives" in gedacht,
       "aber aufgehoben im Gedankengang", gedacht[:80])

print("\n=== Die deutsche Antwort kommt normal durch ===")
antwort, gedacht = sammeln([
    Stueck("Es gibt mehrere Dutzend anerkannte Testosteron-Derivate, "),
    Stueck("etwa dreissig, wenn man die Metaboliten mitzaehlt."),
])
pruefe("Testosteron-Derivate" in antwort, f"Antwort kam an: {antwort[:60]!r}")
pruefe(gedacht == "", f"nichts faelschlich als Gedanke ({gedacht[:50]!r})")

print("\n=== Beides hintereinander ===")
antwort, gedacht = sammeln([
    Stueck("The user asks about the weather in a German city. "),
    Stueck("I should call the weather tool and then answer briefly. "),
    Stueck(werkzeug="get_weather"),
    Stueck("In Duesseldorf sind es siebzehn Grad, Sir."),
])
pruefe(antwort.strip() == "In Duesseldorf sind es siebzehn Grad, Sir.",
       f"nur der deutsche Satz ist Antwort: {antwort.strip()[:60]!r}")
pruefe("weather tool" in gedacht, "das Englische ist im Gedankengang")

print("\n=== Wenn NUR Englisch kommt, wird es trotzdem gezeigt ===")
# Schweigen waere der schlechtere Fehler: lieber eine englische Antwort als
# ein leeres Fenster.
antwort, gedacht = sammeln([
    Stueck("The answer is forty-two."),
])
pruefe("forty-two" in antwort,
       f"kommt als Antwort durch: {antwort[:50]!r}")

print("\n=== Denkreste werden abgeschnitten ===")
for roh, soll in WEG:
    ist = denkrest_entfernen(roh)
    ok = ist == soll
    fehler += not ok
    print(f"  {'ok    ' if ok else 'FEHLER'} {ist[:70]}")
    if not ok:
        print(f"         erwartet: {soll[:70]}")

print("\n=== Echte Antworten bleiben unangetastet ===")
for satz in BLEIBT:
    ist = denkrest_entfernen(satz)
    ok = ist == satz
    fehler += not ok
    print(f"  {'ok    ' if ok else 'FEHLER'} {satz[:70]!r}")
    if not ok:
        print(f"         wurde zu: {ist[:70]!r}")

print(f"\n  {fehler} Fehler")
raise SystemExit(1 if fehler else 0)
