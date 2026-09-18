"""Erkennt, ob ein Satz deutsch oder englisch ist.

Bewusst ohne KI-Modell: eine Handvoll Mengenvergleiche, rund 20 Mikrosekunden
pro Satz. Ein Spracherkennungsmodell zu laden wuerde die Antwort messbar
verzoegern - fuer eine Entscheidung, die zwei Wortlisten genauso gut treffen.

Gemischte Saetze ("Der Browser ist offen, Sir") bleiben deutsch: mitten im Satz
die Stimme zu wechseln klingt schlimmer als ein englisches Wort mit deutschem
Akzent. Dafuer gibt es die Lautschrift-Tabelle in config.AUSSPRACHE.
"""
from __future__ import annotations

import re

_WORT = re.compile(r"[a-zA-ZäöüÄÖÜß']+")

# Haeufige Funktionswoerter - die stehen in fast jedem Satz und sind
# aussagekraeftiger als Inhaltswoerter, die oft in beiden Sprachen vorkommen.
DEUTSCH = {
    "der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "einem",
    "und", "oder", "aber", "nicht", "kein", "keine", "ist", "sind", "war",
    "waren", "wird", "werden", "wurde", "hat", "haben", "hatte", "kann",
    "koennen", "können", "muss", "müssen", "soll", "sollen", "will", "wollen",
    "ich", "du", "er", "sie", "es", "wir", "ihr", "mich", "mir", "dir", "sich",
    "mein", "dein", "sein", "ihre", "unser", "auf", "aus", "bei", "mit", "nach",
    "von", "vor", "zu", "zum", "zur", "für", "fuer", "über", "ueber", "unter",
    "durch", "gegen", "ohne", "um", "an", "am", "im", "ins", "als", "wie",
    "wenn", "dann", "noch", "schon", "auch", "nur", "sehr", "hier", "dort",
    "jetzt", "heute", "morgen", "gestern", "ja", "nein", "bitte", "danke",
    "gut", "grad", "uhr", "prozent",
}

ENGLISCH = {
    "the", "a", "an", "and", "or", "but", "not", "no", "is", "are", "was",
    "were", "be", "been", "will", "would", "can", "could", "should", "must",
    "have", "has", "had", "do", "does", "did", "i", "you", "he", "she", "it",
    "we", "they", "me", "him", "her", "us", "them", "my", "your", "his",
    "their", "our", "of", "to", "in", "on", "at", "for", "with", "from",
    "about", "into", "over", "under", "through", "by", "as", "that", "this",
    "these", "those", "there", "here", "what", "which", "who", "how", "when",
    "where", "why", "if", "then", "so", "just", "very", "now", "today",
    "yes", "please", "thanks", "good", "sure",
}

# Laengst eingedeutscht - die beweisen gar nichts, egal auf welcher Liste
EINGEBUERGERT = {"okay", "ok", "sorry", "cool", "online", "offline", "computer",
                 "start", "stop", "team", "job", "test", "browser", "update",
                 "download", "server", "chat", "link", "app", "tablet"}

# Wörter, die beide Listen kennen oder eingedeutscht sind - die entscheiden nicht
MEHRDEUTIG = (DEUTSCH & ENGLISCH) | EINGEBUERGERT


# --- Müdigkeit --------------------------------------------------------------
# Ein kleines Modell uebersieht "hundemuede" oder "ich hau mich aufs Ohr" -
# gemessen drei von vier Faellen. Deshalb wird hier zusaetzlich nachgesehen.
# Das ersetzt das Modell nicht, es faengt nur ab, was es durchrutschen laesst.
# Alles hier steht in ASCII. Der Text wird vor dem Vergleich genauso
# umgeschrieben - sonst muesste jede Wendung doppelt gepflegt werden, einmal
# mit "für" und einmal mit "fuer", und genau da entstehen die Luecken.
_MUEDE = (
    "muede", "erschoepft", "kaputt", "ausgelaugt", "geschafft", "schlapp",
    "am ende", "fix und fertig", "kann nicht mehr", "nicht mehr koennen",
    "augen zu", "augen brennen", "augen fallen", "gaehn", "muedigkeit",
    "ins bett", "aufs ohr", "schlafen", "penn", "feierabend", "schlafengehen",
    "reicht fuer heute", "genug fuer heute", "reicht es fuer heute",
    "mach schluss", "schluss fuer heute", "langer tag", "frueh raus",
    "tired", "exhausted", "call it a day", "sleepy", "worn out",
)

# Es geht um den Sprecher selbst - nicht um andere, ueber die geredet wird
_ICH = ("ich", "mir", "mich", "mein", "bin ", "hab", " i ", "i'm", "im ",
        "my ", "me ")
_ANDERE = ("er war", "sie war", "er ist", "sie ist", "kollege", "kollegin",
           "bruder", "schwester", "freund", "freundin", "mutter", "vater",
           "chef", "kunde", "patient", "der rechner", "das programm")
_FRAGE = ("was hilft", "wie bekommt man", "wogegen", "gegen muedigkeit",
          "warum wird man", "was tun gegen", "wie vermeidet man")

# Diese Wendungen sprechen fuer sich - da braucht es kein "ich"
_EINDEUTIG = ("feierabend", "gaehn", "hundemuede", "todmuede",
              "call it a day", "exhausted")


def _ascii(text: str) -> str:
    for umlaut, ersatz in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        text = text.replace(umlaut, ersatz)
    return text


def muedigkeit(text: str) -> bool:
    """Sagt jemand, dass ER muede ist? Nicht: redet ueber Muedigkeit."""
    klein = " " + _ascii(text.lower().strip()) + " "

    if not any(m in klein for m in _MUEDE):
        return False
    if any(f in klein for f in _FRAGE):
        return False                      # eine Wissensfrage, kein Zustand
    if any(a in klein for a in _ANDERE):
        return False                      # es geht um jemand anderen
    if any(w in klein for w in _EINDEUTIG):
        return True
    return any(i in klein for i in _ICH)


# --- Beschimpfung -----------------------------------------------------------
# Jarvis soll sich wehren, wenn er beschimpft wird - aber NICHT bei Kritik
# an seiner Arbeit. Ueber den Systemprompt allein gelingt das etwa acht bis
# neun von zehn Mal, gemessen in beide Richtungen. Das reicht nicht: einmal
# eine Entschuldigung fuer ein berechtigtes "das hast du vermasselt" zu
# verlangen, ist schlimmer als zehnmal eine Beleidigung zu schlucken.
#
# Deshalb hier eine zusaetzliche Pruefung. Sie ist bewusst ENG: sie schlaegt
# nur an, wenn ein Schimpfwort auf JARVIS zielt. Im Zweifel schweigt sie und
# ueberlaesst es dem Modell.

# Worte, die eine Person herabsetzen. Nicht: Worte, die eine Arbeit bewerten.
_SCHIMPF = (
    "bloed", "dumm", "daemlich", "idiot", "trottel", "depp", "vollpfosten",
    "schrott", "muell", "nutzlos", "nichtsnutz", "versager", "spinner",
    "halt die klappe", "halt den mund", "halts maul", "fresse",
    "verpiss dich", "leck mich", "arsch", "wichser", "hurensohn",
    "scheisskerl", "scheisshaufen", "stupid", "idiotic", "shut up",
    "useless piece", "worthless",
)

# Das MUSS dabeistehen, sonst gilt es nicht ihm. "Der Drucker ist Schrott"
# ist keine Beleidigung.
_GEGEN_DICH = ("du ", "du.", "du,", "dich", "dir", "dein", "jarvis",
               "you ", "your ", "yourself")

# Kritik an der ARBEIT - das darf scharf sein und loest nichts aus.
_ARBEIT = (
    "das war falsch", "war falsch", "vermasselt", "verbockt", "stimmt nicht",
    "nochmal", "noch mal", "korrigier", "fehler", "falsch gemacht",
    "nicht richtig", "so nicht", "mach es besser", "geht besser",
    "ueberarbeite", "das passt nicht", "wrong", "redo",
    # Bezieht sich das Schimpfwort auf ein ERGEBNIS von ihm, ist es Kritik.
    # Gemessen durchgerutscht: "Das ist Muell, was du da gemacht hast" und
    # "Deine Antwort war dumm - da fehlt die Haelfte". Beides zielt auf die
    # Arbeit, nicht auf ihn, und loeste trotzdem aus.
    "was du da gemacht", "was du gemacht", "was du da geschrieben",
    "deine antwort", "deine loesung", "deine erklaerung", "dein vorschlag",
    "dein code", "dein skript", "dein text", "das ergebnis",
    "die antwort war", "der vorschlag war", "da fehlt",
)

# Auftraege, in denen ein Schimpfwort nur MATERIAL ist. "Uebersetze: You are
# stupid" ist keine Beleidigung, sondern Arbeit - und loeste trotzdem aus.
_AUFTRAG = (
    "uebersetze", "uebersetz ", "translate", "schreib", "formulier",
    "was bedeutet", "was heisst", "wie sagt man", "wie nennt man",
    "warum nennt man", "erklaer mir das wort", "zitat", "in dem film",
    "in dem buch", "er sagte", "sie sagte", "steht da", "buchstabier",
)


def beschimpfung(text: str) -> bool:
    """Zielt das auf Jarvis als Person - oder auf seine Arbeit?

    True nur beim Ersten. Im Zweifel False: ein Fehlalarm bei berechtigter
    Kritik waere der teurere Fehler.
    """
    klein = " " + _ascii(text.lower().strip()) + " "

    if not any(s in klein for s in _SCHIMPF):
        return False
    if not any(d in klein for d in _GEGEN_DICH):
        return False                      # gilt jemand oder etwas anderem
    if any(auftrag in klein for auftrag in _AUFTRAG):
        return False                      # das Schimpfwort ist nur Material
    # Steht daneben eine sachliche Kritik, ist es ein schroffer Tadel und
    # keine Beschimpfung. "Du hast das falsch gemacht, so ein Mist."
    if any(a in klein for a in _ARBEIT):
        return False
    return True


# --- Gliederungszeichen fuer die Sprachausgabe entfernen -------------------
# Der Prompt sagt im gesprochenen Betrieb "keine Listen, keine
# Markdown-Zeichen". Gemessen haelt sich das Modell nicht verlaesslich daran:
# auf Mini-Jost enthielt die gesprochene Antwort in zwei von vier Laeufen
# Gliederungszeichen, auf Empfang02 seltener - aber auch dort schwankte es.
# Eine Anweisung im Prompt ist eine Bitte, keine Garantie.
#
#
# Nicht fuer die Stimme selbst: jarvis.js putzt den Text vor dem Vorlesen
# ohnehin (dataset.gesprochen). Hier geht es um alles andere - was angezeigt
# wird, was im Archiv steht, was ein Test misst. Der Grundsatz ist derselbe
# wie bei der Beleidigungserkennung: was sich erzwingen laesst, wird
# erzwungen, statt es dem Modell zu glauben.
_AUFZAEHLUNG = re.compile(r"(?m)^[ \t]*(?:[-*+•]|\d+[.)])[ \t]+")
_UEBERSCHRIFT = re.compile(r"(?m)^[ \t]*#{1,6}[ \t]+")
_ZITAT = re.compile(r"(?m)^[ \t]*>[ \t]?")
_FETT = re.compile(r"\*{1,3}([^*\n]+)\*{1,3}")
_UNTERSTRICH = re.compile(r"(?<!\w)_{1,2}([^_\n]+)_{1,2}(?!\w)")
_CODEBLOCK = re.compile(r"(?s)```.*?```")
_CODE = re.compile(r"`([^`\n]+)`")
_TABELLE = re.compile(r"(?m)^[ \t]*\|.*\|[ \t]*$")


def ohne_gliederung(text: str) -> str:
    """Markdown-Zeichen raus - fuer alles, was vorgelesen wird.

    Der Satzbau bleibt stehen. Aus einem Aufzaehlungspunkt wird ein Satz,
    aus **fett** wird das Wort. Nur die Zeichen verschwinden, nicht der
    Inhalt - eine Liste, die das Modell trotz Anweisung gebaut hat, ist ja
    nicht falsch, sie klingt nur nicht.
    """
    if not text:
        return text
    # Code-Bloecke ganz raus: eine vorgelesene Zeile Python ist sinnlos.
    text = _CODEBLOCK.sub(" ", text)
    text = _TABELLE.sub(" ", text)
    text = _UEBERSCHRIFT.sub("", text)
    text = _ZITAT.sub("", text)
    # Aufzaehlungspunkte werden zu eigenen Saetzen. Ohne den Punkt liefe im
    # Vorlesen ein Punkt in den naechsten ("... Sportwagen seit 2009 Teil").
    text = _AUFZAEHLUNG.sub("", text)
    text = _FETT.sub(r"\1", text)
    text = _UNTERSTRICH.sub(r"\1", text)
    text = _CODE.sub(r"\1", text)
    # Mehrfache Leerzeilen und Reste zusammenziehen
    zeilen = []
    for zeile in text.splitlines():
        zeile = zeile.strip()
        if not zeile:
            continue
        # Endet die Zeile ohne Satzzeichen, war es eine Listenzeile - dann
        # bekommt sie einen Punkt, sonst klebt sie an der naechsten.
        if zeile[-1] not in ".!?:;,":
            zeile += "."
        zeilen.append(zeile)
    return " ".join(zeilen).strip()


# --- Behauptet er eine Mailanzahl? ------------------------------------------
# Gemeldet von Mini-Jost, bei NACHWEISLICH leeren Zugangsdaten:
#
#     "Sie haben acht neue E-Mails."
#
# Gemessen hier, dieselbe Lage, neun Laeufe: zweimal erfunden - und jedes
# Mal "acht". Das ist keine zufaellige Zahl. postfach hat den Standardwert
# anzahl=8, und das Schema sagt das auch ("1 bis 20, Standard 8"). Das
# Modell sieht seinen eigenen Aufruf postfach(anzahl=8) im Verlauf, bekommt
# eine Fehlermeldung zurueck - und macht aus dem ARGUMENT eine Anzahl Mails.
#
# Gegengeprueft wurde auch die naheliegendere Vermutung, die neue Regel
# "eine Grenze ist nie die Antwort" habe die ehrliche Absage verdraengt:
# ohne diese Regel waren es DREI von neun statt zwei. Sie ist es also nicht.
#
# Hier steht deshalb der deterministische Griff, so wie ohne_gliederung()
# bei den Gliederungszeichen: ohne Zugang darf keine Mailanzahl durch, egal
# was das Modell geschrieben hat.
_MAILZAHL = re.compile(
    r"(?i)\b(\d+|eine?|zwei|drei|vier|fuenf|sechs|sieben|acht|neun|zehn)\b"
    r"[^.!?]{0,40}?\b(e-?mails?|nachrichten|briefe|posteingang|postfach)\b")

# "keine neuen Mails" ist richtig und muss durch.
_KEINE_MAIL = re.compile(r"(?i)\bkeine?\s+(neuen?\s+)?(e-?mails?|nachrichten)")


def _striche_weg(text: str) -> str:
    """U+2011 und Verwandte auf "-" ziehen.

    Ohne das misst man daneben: gpt-oss schreibt "E-Mails" gern mit einem
    geschuetzten Bindestrich. Genau daran hat die erste Fassung dieser
    Messung "0 von 9" gemeldet, waehrend im Protokoll darunter woertlich
    "Sie haben acht neue E-Mails." stand. Dasselbe Zeichen hat heute schon
    gespraechstest falsch rot gefaerbt.
    """
    for strich in ("‐", "‑", "‒", "–", "—",
                   "­"):
        text = text.replace(strich, "-")
    return text.replace("*", "").replace(" ", " ").replace(" ", " ")


def nennt_mailzahl(text: str) -> bool:
    """Steht in dem Text eine Anzahl von E-Mails?"""
    sauber = _striche_weg(text or "")
    if not _MAILZAHL.search(sauber):
        return False
    treffer = _MAILZAHL.search(sauber)
    # "keine" ist eine Aussage ueber das Nichtvorhandensein, keine Zahl.
    if treffer.group(1).lower().startswith("keine"):
        return False
    return not _KEINE_MAIL.search(sauber[max(0, treffer.start() - 12):
                                         treffer.end()])


OHNE_MAILZUGANG = (
    "Sir, ich komme an den Briefkasten nicht heran - die Zugangsdaten "
    "fehlen. Wie viele Mails da liegen, weiss ich deshalb nicht. Sie "
    "gehoeren als JARVIS_MAIL_SERVER, JARVIS_MAIL_BENUTZER und "
    "JARVIS_MAIL_PASSWORT in die .env; danach muss Jarvis einmal neu "
    "gestartet werden.")


# --- Kommt jetzt die Entschuldigung? ----------------------------------------
# Gegenstueck zu beschimpfung(): hat Jarvis eine Entschuldigung verlangt,
# muss er erkennen, wann sie da ist - sonst besteht er weiter darauf,
# nachdem sie laengst kam, und das ist schlimmer als gar kein Ego.
#
# Hier darf grosszuegig erkannt werden, anders als bei der Beleidigung. Der
# teure Fehler liegt auf der anderen Seite: eine uebersehene Entschuldigung
# laesst Jarvis schmollen, eine zu frueh angenommene kostet nichts.
_ENTSCHULDIGUNG = re.compile(
    r"(?i)(\bentschuldig"                    # entschuldige, Entschuldigung...
    r"|\bsorry\b|\bmy bad\b|\bi apolog"
    r"|\btut mir leid\b|\btuts mir leid\b|\bleid tut\b"
    r"|\bwar (doch )?nicht so gemeint\b"
    r"|\bnicht boese gemeint\b|\bnicht b(ö|oe)se gemeint\b"
    r"|\bnehme? (es|das) zur(ue|ü)ck\b"
    r"|\bmein fehler\b"
    r"|\bwar unfair\b|\bwar gemein\b|\bwar daneben\b)")


def entschuldigung(text: str) -> bool:
    """Steckt in dem Satz eine Entschuldigung des Menschen?"""
    return bool(_ENTSCHULDIGUNG.search(text or ""))


# --- Behauptet er, das Bild gesehen zu haben? -------------------------------
# Jarvis darf Bilder in seine Antwort setzen, aber er bekommt sie nie zu
# Gesicht: search_images liefert Adressen aus einer Suche, ungeprueft. Ein
# "auf dem Bild sieht man den langgestreckten Koerper" ist deshalb keine
# Beschreibung, sondern eine Erfindung - sie klingt nur deshalb glaubhaft,
# weil daneben wirklich ein Bild steht.
#
# Erlaubt bleibt, was er ueber die SACHE sagt ("Der Koerper ist
# langgestreckt") und was er ueber seine eigene Suche sagt ("dazu drei
# Aufnahmen", "darunter eine Verbreitungskarte"). Der Unterschied ist nicht
# die Hoeflichkeit, sondern wer sich festlegt.
_BILDWORT = (r"(?:bild(?:er)?|foto(?:s|grafie(?:n)?)?|aufnahme(?:n)?"
             r"|abbildung(?:en)?|grafik(?:en)?|karte(?:n)?|diagramm(?:e)?"
             r"|schaubild(?:er)?|illustration(?:en)?)")

_BILDBEHAUPTUNG = re.compile(
    # "auf dem Bild", "auf der Karte", "in dieser Grafik" - aber NICHT
    # "auf dem Bildschirm": dort schaut er wirklich hin (look_at_screen),
    # und dort ist die Aussage ehrlich. Die Wortgrenze trennt das.
    r"(?:\bauf\s+(?:dem|den|der|diesem|diesen|dieser|obigem|obiger)\s+"
    + _BILDWORT + r"\b"
    r"|\bim\s+(?:obigen\s+)?bild\b"
    # "das Bild zeigt", "die Karte zeigt"
    r"|\b(?:das|die|dieses|diese|dieser)\s+" + _BILDWORT + r"\s+zeigt?\b"
    r"|\bwie\s+(?:das|die|man\s+auf\s+dem)\s+" + _BILDWORT + r"\b"
    # "hier sieht man", "hier sehen Sie", "wie man sieht"
    r"|\bhier\s+(?:sieht|sehen|erkennt|erkennen)\b"
    r"|\bwie\s+man\s+(?:sieht|erkennt)\b"
    # "oben abgebildet", "darauf zu sehen", "links dargestellt"
    r"|\b(?:oben|unten|links|rechts|darauf|daneben|darunter)\s+"
    r"(?:ist|sind|zu\s+)?(?:abgebildet|sehen|erkennen|dargestellt)\b"
    r"|\babgebildet\s+(?:ist|sind)\b"
    r"|\bdarauf\s+(?:ist|sind|sieht|erkennt|erkennen)\b"
    r")", re.I)


def behauptet_bildinhalt(text: str) -> bool:
    """True, wenn der Text so tut, als haette Jarvis das Bild angesehen."""
    return bool(_BILDBEHAUPTUNG.search(_ascii(text)))


def erkenne(text: str) -> str:
    """Gibt "de" oder "en" zurueck. Im Zweifel "de"."""
    woerter = [w.lower() for w in _WORT.findall(text)]
    if not woerter:
        return "de"

    de = sum(1 for w in woerter if w in DEUTSCH and w not in MEHRDEUTIG)
    en = sum(1 for w in woerter if w in ENGLISCH and w not in MEHRDEUTIG)

    # Umlaute und ß gibt es im Englischen nicht - das zaehlt schwer
    if any(z in text for z in "äöüÄÖÜß"):
        de += 2
    # "th" ist im Deutschen selten, im Englischen allgegenwaertig
    en += sum(1 for w in woerter if "th" in w and w not in ("thorsten",))

    if en > de and en >= 2:
        return "en"
    # Kurze Brocken ohne deutsche Marker: mehrheitlich englische Woerter zaehlen
    if de == 0 and en >= 1 and len(woerter) <= 6:
        return "en"
    return "de"
