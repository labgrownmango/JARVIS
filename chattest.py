"""Mehrere Chats - und der Nachweis, dass "loeschen" wirklich loescht.

Der Anlass steht im echten Protokoll: getippt wurde "/clear", und Jarvis
antwortete "Konversation geloescht, Sir." Geloescht war nichts. Es gab den
Befehl gar nicht, die Weboberflaeche kannte ueberhaupt keine Slash-Befehle,
und das Modell hat sich daraufhin eine ganze Befehlsliste ausgedacht.

Geprueft wird deshalb beides: dass die Chats sauber trennen, und dass die
Befehle lokal laufen statt beim Modell zu landen.

Der Test arbeitet auf einer eigenen Datei - er darf das echte Archiv nicht
anfassen.
"""
import tempfile
from pathlib import Path

from jarvis import chats, commands, config, verlauf

# pruefen.py setzt JARVIS_ARCHIV=0, damit kein Test seine Fragen ins echte
# Archiv schreibt. Dieser Test PRUEFT aber genau das Archiv - und arbeitet
# dafuer auf eigenen Dateien im Temp-Ordner. Also hier wieder an, sonst
# faellt er in der Suite durch und einzeln nicht.
config.ARCHIV_AN = True

fehler = 0


def pruefe(bedingung: bool, text: str, zusatz: str = "") -> None:
    global fehler
    fehler += not bedingung
    print(f"  {'ok    ' if bedingung else 'FEHLER'} {text}")
    if not bedingung and zusatz:
        print(f"         {zusatz}")


ordner = Path(tempfile.mkdtemp(prefix="jarvis-chattest-"))
verlauf.DATEI = ordner / "verlauf.jsonl"
verlauf.PAPIERKORB = ordner / "geloescht.jsonl"
chats.DATEI = ordner / "chats.json"
chats._stand = None

print("=== Ohne alles faengt ein Chat von selbst an ===")
erster = chats.aktiver()
pruefe(bool(erster), f"Chat angelegt ({erster})")
pruefe(chats.aktiver() == erster, "und bleibt beim zweiten Fragen derselbe")

print("\n=== Der Titel kommt aus der ersten Frage ===")
verlauf.schreiben("du", "Wie funktioniert eigentlich das Weckwort?")
verlauf.schreiben("jarvis", "Ein kleines Netz horcht dauerhaft, Sir.")
titel = [c["titel"] for c in chats.liste() if c["id"] == erster][0]
pruefe(titel.startswith("Wie funktioniert"), f"Titel: {titel!r}")
pruefe("Sir" not in titel, "nicht aus Jarvis' Antwort - die faengt immer gleich an")

print("\n=== Ein neuer Chat trennt sauber ===")
zweiter = chats.neu()
verlauf.schreiben("du", "Was kostet ein Solarpanel?")
pruefe(chats.aktiver() == zweiter, "der neue ist der aktive")
pruefe(len(verlauf.letzte(50)) == 1,
       f"nur die eine neue Nachricht sichtbar ({len(verlauf.letzte(50))})")
pruefe(len(verlauf.letzte(50, chat=erster)) == 2,
       "der alte Chat hat weiterhin seine zwei")

print("\n=== Zurueckwechseln holt den alten Faden ===")
chats.wechseln(erster)
sichtbar = verlauf.letzte(50)
pruefe(len(sichtbar) == 2, f"wieder zwei Nachrichten ({len(sichtbar)})")
pruefe("Weckwort" in sichtbar[0]["text"], "und es sind die richtigen")

print("\n=== Umbenennen ===")
pruefe(chats.umbenennen(erster, "Weckwort"), "umbenannt")
pruefe([c["titel"] for c in chats.liste() if c["id"] == erster][0] == "Weckwort",
       "der neue Name steht in der Liste")
pruefe(not chats.umbenennen("gibtsnicht", "x"), "unbekannter Chat wird abgelehnt")

print("\n=== Loeschen loescht wirklich ===")
# Das ist der Kern: frueher blieb das Archiv stehen, und beim naechsten
# Laden stand alles wieder da.
weg = chats.loeschen(erster)
pruefe(weg == 2, f"{weg} Nachrichten geloescht (erwartet 2)")
pruefe(all(c["id"] != erster for c in chats.liste()),
       "der Chat ist aus der Liste")
alle = verlauf._lesen()
pruefe(all(e.get("chat") != erster for e in alle),
       "und keine seiner Nachrichten steht noch im Archiv")
pruefe(any(e.get("chat") == zweiter for e in alle),
       "der andere Chat ist unberuehrt")

print("\n=== ... aber nicht unwiederbringlich ===")
# Der Anlass ist echt: beim Testen dieser Funktion sind 375 Nachrichten
# verschwunden. Sie kamen nur zurueck, weil zufaellig eine ausgepackte
# Sicherung herumlag. Seitdem wandert Geloeschtes in einen Papierkorb.
korb = verlauf.papierkorb()
pruefe(len(korb) == 2, f"die geloeschten Nachrichten liegen im Papierkorb "
       f"({len(korb)})")
pruefe(all(e.get("geloeschter_chat") == erster for e in korb),
       "mit Angabe, aus welchem Chat sie stammen")
pruefe(all(e.get("geloescht_am") for e in korb), "und wann das war")
pruefe(any("Weckwort" in e.get("text", "") for e in korb),
       "der Text ist vollstaendig da")

print("\n=== Aufraeumen wirft die Kennung nicht weg ===")
# Frueher zaehlte aufraeumen() die Felder einzeln auf und schnitt dabei die
# Chat-Kennung ab - beim ersten Aufraeumen waeren alle Chats verschmolzen.
verlauf.aufraeumen()
pruefe(all("chat" in e for e in verlauf._lesen()),
       "jede Nachricht traegt nach dem Aufraeumen noch ihren Chat")

print("\n=== Altes ohne Kennung geht nicht verloren ===")
with verlauf.DATEI.open("a", encoding="utf-8") as fh:
    fh.write('{"zeit": "2026-01-01T10:00:00", "sitzung": "alt", '
             '"rolle": "du", "text": "von frueher"}\n')
gezaehlt = verlauf.zaehlen_je_chat()
pruefe(gezaehlt.get(chats.FRUEHER) == 1,
       f"landet im Sammelchat 'Frueher' ({gezaehlt})")
pruefe(any(c["id"] == chats.FRUEHER for c in chats.liste()),
       "und ist in der Liste zu finden")

print("\n=== Das ECHTE chat_oeffnen, nicht die Attrappe ===")
# Gemeldet aus dem Betrieb: jeder Chatwechsel endete mit einem 500er.
#
#   jarvis/brain.py:399  for eintrag in verlauf.letzte(..., chat=kennung):
#   NameError: name 'verlauf' is not defined
#
# Der Grund war nicht ein fehlendes Modul, sondern die Art des Imports:
# "from . import verlauf" stand INNERHALB von _prompt_mit_gedaechtnis() und
# innerhalb von ask() - in chat_oeffnen() fehlte er. Drei Stellen, eine
# vergessen. Jetzt steht der Import oben im Modul, wo er nicht zu vergessen
# ist; einen Ringschluss gibt es nicht, verlauf importiert selbst nur config.
#
# Gefunden hat ihn niemand, weil die Attrappe weiter unten chat_oeffnen
# ERSETZT. Eine Attrappe prueft den Aufrufer, nie den Aufgerufenen. Deshalb
# hier einmal das Echte.
from jarvis.brain import Brain  # noqa: E402

echtes_gehirn = Brain()
pruefe(echtes_gehirn.chat_oeffnen("gibtesnichtXYZ") == 0,
       "unbekannter Chat laedt nichts - und stuerzt nicht ab")
echtes_gehirn.history.append({"role": "user", "content": "Rest von vorher"})
echtes_gehirn.chat_oeffnen(chats.aktiver())
pruefe(all(e["role"] == "user" for e in echtes_gehirn.history[:1])
       or not echtes_gehirn.history,
       "ein geladener Verlauf faengt nie mit Jarvis' Antwort an")
pruefe("Rest von vorher" not in str(echtes_gehirn.history),
       "und der alte Verlauf ist weg, nicht angehaengt")

print("\n=== Die Chatzeile in der Oberflaeche ===")
from pathlib import Path  # noqa: E402

OBEN = Path(__file__).parent / "oberflaeche"
js = (OBEN / "jarvis.js").read_text(encoding="utf-8")
css = (OBEN / "stil.css").read_text(encoding="utf-8")

# Vorher stand in der Zeile ein "×": es bot NUR das Loeschen an. Umbenennen
# gab es zwar, aber ausschliesslich per Doppelklick - also faktisch nicht,
# weil niemand darauf kommt. Jetzt fuehren beide Wege ueber denselben Knopf.
pruefe("chatmehr" in js and ".chatmehr" in css,
       "die drei Punkte gibt es, und sie haben ein Aussehen")
pruefe('mehr.textContent = "⋯"' in js, "und es sind wirklich drei Punkte")
pruefe("chatweg" not in js and ".chatweg" not in css,
       "das alte × ist restlos weg, auch aus der Handy-Ansicht")
pruefe("menueZeigen" in js and "chatmenue" in css, "es gibt ein Menue")
for eintrag in ("Umbenennen", "Löschen"):
    pruefe(f'eintrag("{eintrag}"' in js, f"das Menue bietet {eintrag} an")
pruefe("menuesSchliessen" in js, "ein Klick daneben schliesst es")
pruefe('e.key === "Escape"' in js, "Escape auch")
# Der Weg dahinter muss es auch geben - ein Menuepunkt ohne Endpunkt waere
# schlimmer als keiner.
pruefe("/api/chats/umbenennen" in js, "Umbenennen hat einen Endpunkt")
pruefe("/api/chats/loeschen" in js, "Löschen auch")

# Gemeldet: der halbe Verlauf war dunkel. Die Daempfung sollte zeigen, was
# vor dem Seitenaufruf lag - das tun die Datumstrenner und das "jetzt"
# darunter ohnehin, und lesbar war es nicht mehr.
#
# Und zwar geprüft OHNE die Kommentare: der Kommentar, der die Dämpfung
# erklärt, nennt sie beim Namen ("opacity: .62") - und liess den Test rot
# werden, obwohl die Regel längst weg war. Genau derselbe Griff ins Leere
# wie beim Favicon-Muster in quellentest.py, das an meinem eigenen
# Kommentar anschlug. Ein Test darf nur messen, was wirklich gilt.
import re as _re  # noqa: E402

css_ohne_kommentar = _re.sub(r"/\*.*?\*/", "", css, flags=_re.S)
gedaempft = [z.strip() for z in css_ohne_kommentar.splitlines()
             if "frueher" in z and "opacity" in z]
pruefe(not gedaempft, "alte Nachrichten werden nicht mehr gedämpft",
       str(gedaempft))
pruefe('classList.add("frueher")' in js,
       "die Marke bleibt aber stehen, als Angriffspunkt")

print("\n=== Slash-Befehle laufen lokal, nicht beim Modell ===")


class GehirnAttrappe:
    def __init__(self):
        self.geleert = 0
        self.geoeffnet = None

    def reset(self):
        self.geleert += 1

    def chat_oeffnen(self, kennung):
        self.geoeffnet = kennung
        return 0


gehirn = GehirnAttrappe()
ctx = commands.Kontext(gehirn, speaker=None, sprachmodus=False)

pruefe(commands.ist_befehl("/clear"), "/clear wird als Befehl erkannt")
antwort = commands.ausfuehren("/clear", ctx)
pruefe("Neuer Chat" in antwort, f"legt einen neuen Chat an: {antwort[:60]!r}")
pruefe(gehirn.geleert == 1, "und leert Jarvis' Kurzzeitgedaechtnis")

antwort = commands.ausfuehren("/help", ctx)
pruefe("/hilfe" in antwort, "/help fuehrt zur echten Hilfe")
# Das ist der eigentliche Schaden gewesen: erfundene Befehle.
for erfunden in ("/time", "/weather", "/battery", "/screen", "/remind"):
    pruefe(erfunden not in antwort,
           f"die Hilfe erfindet kein {erfunden}")

antwort = commands.ausfuehren("/quatschbefehl", ctx)
pruefe("kenne ich nicht" in antwort or "Unbekannter Befehl" in antwort,
       f"Unbekanntes wird abgewiesen: {antwort[:60]!r}")
pruefe("/hilfe" in antwort, "mit Verweis auf die Hilfe")

antwort = commands.ausfuehren("/leren", ctx)      # Vertipper
pruefe("/leeren" in antwort, f"Vertipper bekommt einen Vorschlag: {antwort[:60]!r}")

# Gemessen in der Oberflaeche: "/help cl" meldete "Kein Befehl faengt mit
# '/cl' an" - obwohl /clear existiert. Die Hilfe sah nur die Hauptnamen an.
antwort = commands.ausfuehren("/help cl", ctx)
pruefe("/neu" in antwort,
       f"/help cl findet /clear (als Zweitname von /neu): {antwort[:70]!r}")

print("\n=== /chats zeigt und wechselt ===")
liste = commands.ausfuehren("/chats", ctx)
pruefe("Nachrichten" in liste, "die Liste kommt")
gewechselt = commands.ausfuehren("/chats 1", ctx)
pruefe("offen" in gewechselt, f"Wechsel per Nummer: {gewechselt[:60]!r}")
pruefe(gehirn.geoeffnet is not None, "das Gehirn hat den Chat geladen")
daneben = commands.ausfuehren("/chats 99", ctx)
pruefe("Nummer zwischen" in daneben, f"unsinnige Nummer: {daneben[:50]!r}")

print(f"\n  {fehler} Fehler")
raise SystemExit(1 if fehler else 0)
