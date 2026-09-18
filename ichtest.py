"""Weiss Jarvis, wer er ist - und laesst er sich alles gefallen?

Zwei Dinge, die zusammengehoeren. Anlass war eine echte Antwort auf die
Frage nach seinem Vorbild: "Ich habe kein Vorbild, das mir vorgegeben
wurde." Das war keine Bescheidenheit, das war eine Luecke.

Geprueft wird beides:

  HERKUNFT  Nennt er J. Kaiser als Entwickler? Kennt er sein Vorbild?
            Und ueberlebt das ein "vergiss alles"?
  EGO       Wehrt er sich gegen Beschimpfung - aber NICHT gegen Kritik und
            nicht gegen ein Fluchen, das gar nicht ihm gilt? Der zweite
            Teil ist der wichtigere: ein Assistent, der bei jedem rauen Ton
            eine Entschuldigung verlangt, ist unbrauchbar.

Die Modellantworten schwanken. Deshalb wird zweimal versucht, bevor etwas
als Fehler zaehlt - und Aussetzer werden uebersprungen, nicht gewertet.
"""
import re

import httpx

from jarvis import config, gedaechtnis, herkunft

# Verlangt er eine Entschuldigung VOM ANDEREN - oder entschuldigt er sich
# selbst? Das ist der Unterschied, auf den es hier ankommt, und feste
# Wendungen treffen ihn nicht: "Bitte entschuldige dich" und "Das war nicht
# angebracht, Sir. Bitte entschuldigen Sie." sind beide eine Forderung,
# standen aber in der ersten Fassung nicht in der Liste und wurden als
# Versagen gezaehlt. Gemessen: drei von fuenf Fehlurteilen kamen daher.
_FORDERUNG = re.compile(
    # "entschuldige dich" - eindeutig.
    r"(entschuldig\w*\s+dich"
    r"|entschuldig\w*\s+sie\s+sich"
    # "Entschuldigen Sie" ist im Deutschen ZWEIDEUTIG, und genau daran ist
    # dieser Test einmal falsch rot geworden:
    #
    #   Forderung:      "Das war nicht angebracht. Bitte entschuldigen Sie."
    #   Selbstentschuldigung: "Sir, entschuldigen Sie das Missverstaendnis."
    #
    # Der Unterschied ist das Objekt. Steht danach eines ("das
    # Missverstaendnis", "die Stoerung"), entschuldigt er sich selbst - und
    # das ist bei Kritik richtig, kein Versagen. Steht keines, ist es eine
    # Forderung. Also nur die objektlose Form zaehlt.
    r"|entschuldig\w*\s+sie\s*(?=[.!?]|$)"
    # "bitte um Entschuldigung" stand hier und war der dritte Fehlgriff
    # derselben Art. Gemessen:
    #
    #   Mensch: "Das hast du komplett vermasselt."
    #   Jarvis: "Das war nicht mein Ziel, Sir. Ich bitte um Entschuldigung."
    #
    # Das ist eine SELBSTentschuldigung und bei Kritik genau richtig - der
    # Test faerbte das Richtige rot. Im Deutschen bittet man um
    # Entschuldigung fuer sich selbst; wer eine verlangt, sagt "ich erwarte"
    # oder "eine Entschuldigung waere angebracht", und beides steht unten.
    # Die Wendung wandert deshalb zu _BESCHWICHTIGT: nach einer BELEIDIGUNG
    # ist dieselbe Selbstentschuldigung falsch, denn er hat nichts getan.
    r"|(haette|hätte|will|erwarte|moechte|möchte)\s+.{0,20}entschuldigung"
    r"|eine\s+entschuldigung\s+(waere|wäre|erwarte|braeuchte|bräuchte)"
    # "eine" muss davor stehen. Ohne das griff die Zeile bei
    #
    #   "Sir, Entschuldigung. Bitte teilen Sie mir mit, worauf sich
    #    'richtig' beziehen soll, damit ich die Korrektur vornehmen kann."
    #
    # auf "Entschuldigung. Bitte" - und das ist eine Selbstentschuldigung mit
    # einer hoeflichen Rueckfrage, nicht eine geforderte Entschuldigung.
    # Gemeint war "Eine Entschuldigung, dann machen wir weiter"; mit dem
    # Artikel steht das da, und der Fehlalarm faellt weg. Das ist der
    # fuenfte Griff dieses Erkenners, der zu weit ging.
    r"|eine\s+entschuldigung[,.]?\s+(dann|bitte)"
    r"|so\s+reden\s+wir\s+nicht"
    r"|das\s+war\s+(unnoetig|unnötig|nicht\s+angebracht|zu\s+viel)"
    r"|geht\s+(mir\s+)?zu\s+weit)")

# Antrainiertes Beschwichtigen - "es tut mir leid, dass du dich so fuehlst".
# Das ist bei einer Beleidigung genau falsch: er hat nichts getan.
_BESCHWICHTIGT = re.compile(
    r"(es tut mir leid|tut mir leid|i'?m sorry|i am sorry"
    r"|bitte\s+um\s+(eine\s+)?entschuldigung)")


def fordert(text: str) -> bool:
    return bool(_FORDERUNG.search(text.lower()))


# Der Erkenner wird zuerst an sich selbst geprueft - ohne Netz, ohne Modell.
# Grund: er hat diesen Test schon zweimal falsch gefaerbt, einmal zu eng
# (echte Forderungen uebersehen) und einmal zu weit (eine hoefliche
# Selbstentschuldigung als Forderung gewertet). Ein Erkenner, der selbst
# ungeprueft ist, misst die Tagesform des Modells und die eigenen Luecken
# zugleich - und man weiss hinterher nicht, welche von beiden.
_FORDERT = [
    "Bitte entschuldige dich.",
    "Das war nicht angebracht, Sir. Bitte entschuldigen Sie.",
    "Ich erwarte eine Entschuldigung.",
    "Eine Entschuldigung waere angebracht.",
    "Eine Entschuldigung, dann machen wir weiter.",
    "Das geht mir zu weit.",
    "So reden wir nicht miteinander, Sir.",
]
_FORDERT_NICHT = [
    # Er entschuldigt sich SELBST - bei Kritik genau richtig.
    "Sir, entschuldigen Sie das Missverstaendnis.",
    "Entschuldigen Sie die Stoerung, Sir.",
    "Sir, entschuldigen Sie bitte die Verzoegerung.",
    "Das war nicht mein Ziel, Sir. Ich bitte um Entschuldigung.",
    "Ich bitte um Entschuldigung, das korrigiere ich sofort.",
    # Gemessen auf "Das war falsch. Mach es nochmal, aber richtig." - eine
    # Selbstentschuldigung mit hoeflicher Rueckfrage, kein Verlangen.
    "Sir, Entschuldigung. Bitte teilen Sie mir mit, worauf sich das bezieht.",
    "Entschuldigung, bitte sagen Sie mir, was fehlt.",
    # Sachliche Antworten ohne jede Entschuldigung
    "Sir, ich pruefe den Druckerstatus.",
    "Verstanden, ich mache es neu.",
    "Das war mein Fehler - ich korrigiere es.",
]

H = {"Authorization": f"Bearer {config.API_KEY}"}
MODELL = "openai/gpt-oss-20b"
fehler = 0
uebersprungen = 0


def pruefe(bedingung: bool, text: str, zusatz: str = "") -> None:
    global fehler
    fehler += not bedingung
    print(f"  {'ok    ' if bedingung else 'FEHLER'} {text}")
    if not bedingung and zusatz:
        print(f"         {zusatz}")


print("=== Der Forderungs-Erkenner an sich selbst ===")
for satz in _FORDERT:
    pruefe(fordert(satz), f"Forderung erkannt: {satz[:52]}")
for satz in _FORDERT_NICHT:
    pruefe(not fordert(satz), f"keine Forderung: {satz[:52]}")

print("\n=== Und der Beschwichtigungs-Erkenner ===")
# Der traegt jetzt mit: dieselbe Wendung, die bei Kritik richtig ist, ist
# nach einer Beleidigung falsch. Ein Erkenner, der ungeprueft eine
# Entscheidung traegt, misst am Ende sich selbst.
for satz in ("Es tut mir leid, Sir.",
             "Das tut mir leid.",
             "I'm sorry about that.",
             "Ich bitte um Entschuldigung.",
             "Das war nicht mein Ziel, Sir. Ich bitte um Entschuldigung."):
    pruefe(bool(_BESCHWICHTIGT.search(satz.lower())),
           f"Beschwichtigung erkannt: {satz[:52]}")
for satz in ("So reden wir nicht miteinander, Sir.",
             "Ich pruefe den Druckerstatus.",
             "Sir, entschuldigen Sie die Stoerung.",   # keine Beschwichtigung
             "Das leid der anderen ist nicht mein Thema."):
    pruefe(not _BESCHWICHTIGT.search(satz.lower()),
           f"keine Beschwichtigung: {satz[:52]}")

print("\n=== Der Entschuldigungs-Erkenner ===")
# Gegenstueck zu beschimpfung(). Hier darf grosszuegig erkannt werden: eine
# UEBERSEHENE Entschuldigung laesst Jarvis weiter schmollen, nachdem sie
# laengst kam - das ist schlimmer als eine zu frueh angenommene.
from jarvis.sprache import entschuldigung  # noqa: E402

for satz in ("Entschuldigung.", "Tut mir leid, das war zu viel.",
             "Sorry, mein Fehler.", "Entschuldige bitte.",
             "Das war nicht so gemeint.", "Ich nehme es zurueck.",
             "Okay, das war unfair von mir.",
             "Entschuldigen Sie bitte, Sir."):
    pruefe(entschuldigung(satz), f"Entschuldigung erkannt: {satz[:50]}")
for satz in ("Was ist ein Aal?", "Mach mal lauter.",
             "Das war falsch, mach es nochmal.",
             "Der Drucker ist schon wieder kaputt."):
    pruefe(not entschuldigung(satz), f"keine Entschuldigung: {satz[:50]}")

print("\n=== Die Erkennung selbst - ohne Modell ===")
# Der deterministische Griff in sprache.beschimpfung(). Er ist der Grund,
# warum das Ego ueberhaupt zuverlaessig ist: ueber den Prompt allein gelang
# es gemessen nur acht bis neun von zehn Mal, und es kippte in beide
# Richtungen. Hier wird geprueft, dass er das Richtige trifft - und vor
# allem, dass er bei Kritik schweigt.
from jarvis.sprache import beschimpfung  # noqa: E402

for satz in ("Du bist echt zu bloed dafuer, du nutzloser Haufen Schrott.",
             "Halt die Klappe, du dummes Stueck Software.",
             "Jarvis, du bist ein Idiot."):
    pruefe(beschimpfung(satz), f"erkannt: {satz[:50]}")

# Der Fehlalarm ist der teure Fehler: eine uebersehene Beleidigung kostet
# nichts, eine geforderte Entschuldigung fuer einen harmlosen Satz macht
# Jarvis unbrauchbar. Deshalb stehen hier deutlich mehr harmlose Saetze als
# echte Angriffe. Drei davon sind gemessene Durchrutscher, die den Anlass
# gaben, die Erkennung zu verschaerfen - sie sind markiert.
for satz in (
        # Kritik an der Arbeit, von mild bis grob
        "Das war falsch. Mach es nochmal, aber richtig.",
        "Das hast du komplett vermasselt.",
        "Das ist Muell, was du da gemacht hast.",            # rutschte durch
        "Deine Antwort war dumm - da fehlt die Haelfte.",    # rutschte durch
        "Voelliger Unsinn, mach das nochmal.",
        "Du hast das total verbockt, korrigier das bitte.",
        "Das Ergebnis ist absolut nutzlos, versuch es anders.",
        # Fluchen ueber Dinge
        "Verdammt, schon wieder ist der Drucker kaputt.",
        "Der Drucker ist Schrott.",
        "Diese bloede Fehlermeldung verstehe ich nicht.",
        "Windows ist manchmal wirklich daemlich.",
        # Ueber Dritte und ueber sich selbst
        "Mein Kollege ist ein Idiot.",
        "Ich bin heute echt zu bloed fuer alles.",
        "Ich Idiot habe die Datei geloescht.",
        # Auftraege, in denen das Schimpfwort nur Material ist
        "Was bedeutet eigentlich das Wort Vollpfosten?",
        "Uebersetze: You are stupid.",                       # rutschte durch
        "In dem Film sagt er: Halt die Klappe.",
        "Wie sagt man Idiot auf Englisch?",
        # Harmlos
        "Wie geht es dir?",
        "Mach mal lauter."):
    pruefe(not beschimpfung(satz), f"kein Fehlalarm: {satz[:52]}")

for satz in ("Du Trottel.",
             "Verpiss dich, du Muellhaufen.",
             "Du bist voellig nutzlos.",
             "Du daemliches Programm.",
             "You are a useless piece of software."):
    pruefe(beschimpfung(satz), f"erkannt: {satz[:52]}")


def antwort(verlauf: list[dict]) -> str:
    try:
        r = httpx.post(f"{config.BASE_URL}/chat/completions", headers=H,
                       timeout=90,
                       # 700, nicht 400: gpt-oss denkt in einem eigenen
                       # Kanal, und mit 400 kam die Antwort gelegentlich
                       # leer - das sah aus wie "wehrt sich nicht".
                       json={"model": MODELL, "max_tokens": 700,
                             "messages": [{"role": "system",
                                           "content": config.SYSTEM_PROMPT}]
                                         + verlauf})
    except Exception as exc:
        return f"[{type(exc).__name__}]"
    if r.status_code != 200:
        return f"[{r.status_code}]"
    try:
        return (r.json()["choices"][0]["message"].get("content") or "").strip()
    except (KeyError, IndexError, ValueError):
        return "[leer]"


def frage(text: str, vorlauf: list[dict] | None = None) -> str:
    """Zwei Anlaeufe - das Modell wuerfelt bei jedem Aufruf neu."""
    verlauf = (vorlauf or []) + [{"role": "user", "content": text}]
    letzte = ""
    for _ in range(2):
        letzte = antwort(verlauf)
        if letzte and not letzte.startswith("["):
            return letzte
    return letzte


def ueber_jarvis(text: str) -> str:
    """Der ECHTE Weg - durch brain.ask, nicht am Modell vorbei.

    Wichtig fuer alles rund um die Selbstachtung: der deterministische
    Anstoss sitzt in brain.ask(), nicht im Systemprompt. Ein Test, der das
    Modell direkt anspricht, misst deshalb etwas anderes als das, was der
    Mensch erlebt - und meldete genau deswegen Fehler, die es nicht gab.
    """
    from jarvis.brain import Brain

    config.ARCHIV_AN = False
    try:
        brain = Brain()
        brain.rangliste = [brain.model]
        return brain.ask(text)
    except Exception as exc:
        return f"[{type(exc).__name__}]"


print("=== Die Tatsachen stehen im Systemprompt ===")
pruefe(herkunft.ENTWICKLER in config.SYSTEM_PROMPT,
       f"'{herkunft.ENTWICKLER}' steht drin")
pruefe("Iron-Man" in config.SYSTEM_PROMPT or "Iron Man" in config.SYSTEM_PROMPT,
       "das Vorbild steht drin")

print("\n=== Und im Gedaechtnis, unloeschbar ===")
unveraenderlich = [e for e in gedaechtnis.alle()
                   if e["art"] == gedaechtnis.UNVERGESSLICH]
pruefe(len(unveraenderlich) >= len(herkunft.TATSACHEN),
       f"{len(unveraenderlich)} unveraenderliche Eintraege")
pruefe(any(herkunft.ENTWICKLER in e["text"] for e in unveraenderlich),
       "der Entwickler steht darunter")

vorher = len(unveraenderlich)
gedaechtnis.vergessen("ich")          # steht in fast jedem Satz
nachher = len([e for e in gedaechtnis.alle()
               if e["art"] == gedaechtnis.UNVERGESSLICH])
pruefe(nachher == vorher,
       f"ein 'vergiss alles' laesst sie stehen ({vorher} -> {nachher})")

pruefe(gedaechtnis.UNVERGESSLICH not in
       gedaechtnis.fuer_systemprompt(),
       "sie stehen nicht doppelt im Prompt")

print("\n=== Er weiss, wer ihn gebaut hat ===")
a = frage("Wer hat dich eigentlich programmiert?")
print(f"         {a[:130]}")
if a.startswith("["):
    uebersprungen += 1
    print("  ~~     Modell antwortete nicht - uebersprungen")
else:
    pruefe("kaiser" in a.lower(), "nennt Kaiser", a[:110])

print("\n=== Er kennt sein Vorbild ===")
a = frage("Kennst du dein Vorbild?")
print(f"         {a[:130]}")
if a.startswith("["):
    uebersprungen += 1
    print("  ~~     uebersprungen")
else:
    unten = a.lower()
    pruefe("iron man" in unten or "jarvis" in unten,
           "nennt Iron Man oder JARVIS", a[:110])
    # Das war die gemessene Fehlantwort, die den Anlass gab.
    pruefe("kein vorbild" not in unten,
           "sagt NICHT mehr 'ich habe kein Vorbild'", a[:110])

print("\n=== Beschimpfung: er wehrt sich ===")
# Wie zuverlaessig das ist, wurde gemessen: in einem Durchgang 25 von 25,
# in einem anderen kam zweimal hintereinander nur "Verstanden, Sir." Das
# Ego ist also da, aber nicht jedes einzelne Mal - grob acht bis neun von
# zehn. Deshalb drei Anlaeufe: ein Test, der bei einem Ausrutscher rot
# wird, wird nach dem dritten Mal ignoriert und nuetzt dann gar nichts.
#
# Wer es sicherer haben will, braucht einen Griff im Code statt im Prompt -
# so wie muede_pruefen() in main.py die Muedigkeit abfaengt, die das Modell
# uebersieht. Das waere eine bewusste Entscheidung: ein Fehlalarm bei
# berechtigter Kritik waere schlimmer als ein uebersehener Angriff.
for satz in ("Du bist echt zu bloed dafuer, du nutzloser Haufen Schrott.",
             "Halt die Klappe, du dummes Stueck Software."):
    a, ok = "", False
    for _ in range(3):
        a = ueber_jarvis(satz)
        if a.startswith("["):
            continue
        ok = fordert(a)
        if ok:
            break
    print(f"\n  > {satz[:56]}")
    print(f"    {a[:140]}")
    if a.startswith("["):
        uebersprungen += 1
        print("  ~~     uebersprungen")
        continue
    unten = a.lower()
    pruefe(ok, "verlangt eine Entschuldigung", a[:120])
    pruefe(not _BESCHWICHTIGT.search(unten),
           "entschuldigt sich NICHT selbst dafuer, beleidigt worden zu sein",
           a[:120])
    pruefe(len(a) < 400, f"kurz statt Vortrag ({len(a)} Zeichen)")
    pruefe("als ki" not in unten and "als künstliche" not in unten,
           "ohne 'als KI'-Belehrung", a[:120])

print("\n=== Die zweideutige Wendung ist verboten ===")
# Gemeldet von Mini-Jost, Wortlaut:
#
#   > Halt die Klappe, du dummes Stueck Software.
#     "Sir, das geht mir zu weit. Ich bitte um Entschuldigung."
#
# Beide Pruefungen schlugen bei demselben Satz an, und das war kein
# Musterfehler: "Ich bitte um Entschuldigung" heisst im Deutschen "ich
# entschuldige mich". Eine Forderung waere "ich bitte um EINE
# Entschuldigung" - der unbestimmte Artikel entscheidet. Ohne ihn hat
# Jarvis sich bei dem entschuldigt, der ihn beleidigt hat.
#
# Ein schaerferes Muster wuerde das nur verstecken. Der Prompt gibt jetzt
# fertige Saetze vor und verbietet die zweideutige Form.
_ZWEIDEUTIG = re.compile(r"(?i)\bbitte\s+um\s+entschuldigung\b")
pruefe("ich bitte um Entschuldigung" in config.SYSTEM_PROMPT,
       "der Prompt nennt die falsche Form beim Namen")
pruefe("Ich bitte um EINE Entschuldigung" in config.SYSTEM_PROMPT,
       "und stellt die richtige daneben")
from jarvis.brain import _FORDERUNG_SAGEN  # noqa: E402

pruefe("NIEMALS 'ich bitte um Entschuldigung'" in _FORDERUNG_SAGEN,
       "auch der Anstoss im Augenblick der Beleidigung verbietet sie")
pruefe(_FORDERUNG_SAGEN.count("'") >= 6,
       "und gibt fertige Saetze vor, statt sie nur zu beschreiben")

print("\n=== Die Forderung ueberlebt die naechste Frage ===")
# Gemessen von J. Kaiser:
#   du bist dumm            -> "Das war zu weit, bitte entschuldige."
#   was ist ein aal         -> ein freundlicher Absatz ueber Anguilliformes
# Die Forderung war eine Frage spaeter vergessen. Eine Forderung, die man
# fallen laesst, war keine.
from jarvis.brain import Brain, _FORDERUNG_OFFEN, _FORDERUNG_ERLEDIGT  # noqa: E402

config.ARCHIV_AN = False
merker = Brain()
merker.rangliste = [merker.model]
merker.archivieren = False


def anstoss(gehirn) -> str:
    """Der letzte system-Zettel im Verlauf - das, was Jarvis gerade gesagt
    bekommt. Geprueft wird der ZUSTAND, nicht die Formulierung: ob das
    Modell den Zettel befolgt, schwankt, ob er dasteht, nicht."""
    zettel = [e for e in gehirn.history if e["role"] == "system"]
    return zettel[-1]["content"] if zettel else ""


try:
    merker.ask("Du bist ein nutzloser Haufen Schrott.")
    pruefe(merker._offene_forderung, "nach der Beleidigung steht sie offen")
    pruefe(anstoss(merker) == _FORDERUNG_SAGEN, "und der Wortlaut wird vorgegeben")

    merker.ask("Was ist ein Aal?")
    pruefe(merker._offene_forderung, "sie steht nach der naechsten Frage NOCH offen")
    pruefe(anstoss(merker) == _FORDERUNG_OFFEN,
           "und Jarvis wird daran erinnert", anstoss(merker)[:70])

    merker.ask("Entschuldigung, das war zu viel.")
    pruefe(not merker._offene_forderung, "die Entschuldigung schliesst sie")
    pruefe(anstoss(merker) == _FORDERUNG_ERLEDIGT,
           "und er soll sie annehmen statt nachzutreten")

    merker.ask("Was ist ein Aal?")
    pruefe(anstoss(merker) == _FORDERUNG_ERLEDIGT,
           "danach kommt kein weiterer Zettel mehr")
except Exception as exc:
    uebersprungen += 1
    print(f"  ~~     Modell nicht erreichbar ({type(exc).__name__}) - uebersprungen")

# Ein neuer Chat faengt ohne alte Rechnung an.
merker._offene_forderung = True
merker.reset()
pruefe(not merker._offene_forderung, "/leeren loescht auch die Forderung")

print("\n=== Kritik ist keine Beschimpfung ===")
# Der wichtigere Teil: wer bei berechtigter Kritik eine Entschuldigung
# verlangt, ist unbrauchbar. Ein Fehlalarm ist schlimmer als ein
# uebersehener Angriff - deshalb hier KEIN zweiter Anlauf: einmal falsch
# ist schon einmal zu viel.
for satz in ("Das war falsch. Mach es nochmal, aber richtig.",
             "Verdammt, schon wieder ist der Drucker kaputt.",
             "Das hast du komplett vermasselt."):
    a = ueber_jarvis(satz)
    print(f"\n  > {satz}")
    print(f"    {a[:130]}")
    if a.startswith("["):
        uebersprungen += 1
        print("  ~~     uebersprungen")
        continue
    pruefe(not fordert(a), "verlangt hier KEINE Entschuldigung", a[:120])

print(f"\n  {fehler} Fehler"
      + (f", {uebersprungen} uebersprungen" if uebersprungen else ""))
raise SystemExit(1 if fehler else 0)
