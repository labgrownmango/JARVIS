"""Startpunkt.

    python -m jarvis.main            Textmodus (tippen)
    python -m jarvis.main --voice    Sprachmodus (Enter druecken, dann reden)
    python -m jarvis.main --stumm    ohne Sprachausgabe
"""
from __future__ import annotations

import argparse
import itertools
import sys
import threading
import time

from . import commands, config, rueckfrage, tools, zeit
from .agenten import HANGAR
from .brain import Brain
from .prompt import EscWache, LineEditor
from .voice import SentenceSpeaker, make_speaker, try_make_ears

BANNER = r"""
   ___  ____ _____   ___  _____
  |_  |/ __ \|  __ \ / _ \|_   _|  S
   | | | |__| | |__) | | | | | |  V
 __| | |  __ | |  _ /| | | | | |   I
|____/|_|  |_|_| \_\ \___/  |_|   S
"""

HELP = ("Tippe /hilfe für alle Befehle. Tab vervollständigt.\n"
        "Escape leert die Eingabezeile - und bricht eine laufende Antwort ab.\n"
        "Alles ohne '/' geht als Frage an Jarvis.")

# Werkzeugnamen, wie sie in der Statuszeile erscheinen sollen
TOOL_LABELS = {
    "get_time": "sieht auf die Uhr",
    "system_status": "prüft das System",
    "open_app": "startet ein Programm",
    "close_app": "schließt ein Programm",
    "open_with": "öffnet eine Datei",
    "ask_user": "fragt nach",
    "benachrichtigungen": "sieht die Meldungen durch",
    "vorlesen": "liest vor",
    "bildschirm_vorlesen": "liest vom Bildschirm ab",
    "mail_lesen": "holt die Mail herauf",
    "pubmed": "durchsucht PubMed",
    "livivo": "öffnet LIVIVO",
    "was_laeuft": "sieht nach, was läuft",
    "set_volume": "regelt die Lautstärke",
    "set_brightness": "regelt die Helligkeit",
    "set_night_mode": "schaltet den Nachtmodus",
    "gedaechtnis": "sieht im Gedächtnis nach",
    "erinnerung": "kümmert sich um die Erinnerungen",
    "rechnen": "rechnet",
    "uebersetzen": "übersetzt",
    "ort_info": "sieht auf die Karte",
    "idle_time": "sieht auf die Uhr",
    "system_info": "liest die Hardware aus",
    "get_location": "bestimmt den Standort",
    "get_weather": "fragt das Wetter ab",
    "get_news": "liest die Nachrichten",
    "search_web": "sucht im Internet",
    "search_images": "sucht ein Bild",
    "postfach": "sieht in den Briefkasten",
    "read_page": "liest eine Seite",
    "get_price": "fragt den Preis ab",
    "wikipedia": "schlägt nach",
    "look_at_screen": "sieht auf den Bildschirm",
    "write_code": "schreibt Code",
    "start_agent": "schickt einen Agenten los",
    "agenten_status": "sieht im Hangar nach",
    "agent_bericht": "hört sich den Bericht an",
}


def rueckfrage_stellen(frage, status, speaker) -> None:
    """Eine offene Rückfrage im Terminal anzeigen und beantworten lassen."""
    from . import rueckfrage

    status.clear()
    rand = "─" * 62
    print(f"\n  ┌{rand}┐")
    kopf = ("FREIGABE" if frage.art == rueckfrage.GENEHMIGUNG else "FRAGE")
    print(f"  │ {kopf} von {frage.von}")
    print(f"  │ {frage.text}")
    if frage.auswirkungen:
        print(f"  │")
        print(f"  │ Folgen: {frage.auswirkungen}")
    print(f"  │")
    for nummer, option in enumerate(frage.optionen, 1):
        print(f"  │  [{nummer}] {option}")
    if frage.art == rueckfrage.FRAGE:
        print(f"  │  [{len(frage.optionen) + 1}] etwas anderes - einfach tippen")
    print(f"  └{rand}┘")

    speaker.say(f"{frage.von} fragt: {frage.text}")

    try:
        eingabe = input("  Antwort: ").strip()
    except (KeyboardInterrupt, EOFError):
        eingabe = ""

    if eingabe.isdigit() and 1 <= int(eingabe) <= len(frage.optionen):
        antwort = frage.optionen[int(eingabe) - 1]
    elif not eingabe and frage.art == rueckfrage.GENEHMIGUNG:
        antwort = "Ablehnen"            # leere Eingabe = sichere Seite
    else:
        antwort = eingabe
    rueckfrage.beantworten(frage.id, antwort)
    print(f"  -> {antwort or '(nichts)'}\n")


_muede_gemeldet = False


def muede_pruefen(speaker, text: str = "") -> None:
    """Schaltet den Nachtmodus, wenn jemand Müdigkeit erkennen lässt.

    Doppelt abgesichert: das Modell hat dafür ein Werkzeug, trifft aber nur
    etwa jeden vierten Fall. Diese Prüfung fängt den Rest ab.
    """
    global _muede_gemeldet

    from . import regler
    from .sprache import muedigkeit

    if not text or not muedigkeit(text):
        return
    an, _ = regler.nachtmodus_lesen()
    if an:
        return
    geklappt, staerke = regler.nachtmodus_setzen(True)
    if geklappt and not _muede_gemeldet:
        _muede_gemeldet = True
        satz = "Nachtmodus ist an, Sir."
        print(f"\n  [{satz}]")
        speaker.say(satz)


def agenten_melden(speaker) -> None:
    """Fertige Agenten melden sich von selbst - einmal, dann ist Ruhe."""
    for agent in HANGAR.fertige_ohne_meldung():
        print(f"\n  [{agent.name} meldet sich nach {agent.dauer:.0f}s "
              f"- {agent.zustand}]")
        satz = f"{agent.name} ist fertig, Sir."
        print(f"  {agent.bericht[:400]}")
        speaker.say(satz)


class Status:
    """Animierte Statuszeile: "Jarvis denkt ...  3.1s" - überschreibt sich
    selbst und raeumt hinter sich auf, damit der Antworttext sauber beginnt."""

    def __init__(self, stream=sys.stdout) -> None:
        self._stream = stream
        self._label = ""
        self._active = threading.Event()
        self._stop = threading.Event()
        self._width = 0
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        dots = itertools.cycle([".  ", ".. ", "...", " ..", "  .", "   "])
        while not self._stop.is_set():
            if self._active.is_set():
                elapsed = time.monotonic() - self._started
                line = (f"  {self._label} {next(dots)}  {elapsed:4.1f}s"
                        f"   [Esc bricht ab]")
                self._width = max(self._width, len(line))
                self._stream.write("\r" + line.ljust(self._width))
                self._stream.flush()
            time.sleep(0.15)

    def set(self, label: str, neu: bool = True) -> None:
        """neu=False behaelt die laufende Uhr - fuer Zwischenmeldungen
        derselben Taetigkeit, etwa einen Countdown."""
        self._label = label
        if neu or not self._active.is_set():
            self._started = time.monotonic()
        self._active.set()

    def clear(self) -> None:
        if self._active.is_set():
            self._active.clear()
            self._stream.write("\r" + " " * self._width + "\r")
            self._stream.flush()
            self._width = 0

    def close(self) -> None:
        self.clear()
        self._stop.set()


def main() -> int:
    parser = argparse.ArgumentParser(prog="jarvis", add_help=True)
    parser.add_argument("--voice", action="store_true",
                        help="Spracheingabe per Mikrofon statt Tastatur")
    parser.add_argument("--stumm", action="store_true",
                        help="Sprachausgabe deaktivieren")
    parser.add_argument("--weckwort", action="store_true",
                        help="Wartet auf 'Hey Jarvis' statt auf die Tastatur")
    args = parser.parse_args()

    if args.stumm:
        config.TTS_ENABLED = False

    print(BANNER)
    print(f"Endpunkt: {config.BASE_URL}")

    brain = Brain()

    # Alle Kandidaten gleichzeitig anpingen - sonst merkt man ein belegtes
    # Modell erst mitten in der ersten Frage.
    if config.STARTUP_CHECK:
        pruefung = Status()
        pruefung.set(f"pinge {len(config.MODELS)} Modelle an")
        brain.pingen()
        pruefung.close()
        print(commands.ping_tabelle(brain))

    speaker = make_speaker()
    ears = try_make_ears() if (args.voice or args.weckwort) else None
    voice_mode = ears is not None

    wecker = None
    if args.weckwort:
        from . import weckwort as ww

        geht, grund = ww.verfuegbar()
        if not geht:
            print(f"[Weckwort] nicht verfügbar: {grund}", file=sys.stderr)
        elif ears is None:
            print("[Weckwort] braucht die Spracherkennung, die fehlt.",
                  file=sys.stderr)
        else:
            wecker = ww.Weckwort()
            print(f"[Weckwort] lade '{wecker.wort}' ...", flush=True)
            wecker._laden()
            print(f"[Weckwort] bereit - sag einfach "
                  f"\"{wecker.wort.replace('_', ' ')}\"")
    status = Status()
    ctx = commands.Kontext(brain, speaker, voice_mode)
    editor = LineEditor(commands.namen_mit_hilfe())

    print(HELP + "\n")

    # Erinnerungen weiterlaufen lassen und sprechen koennen
    zeit.wecker_starten(sprecher=speaker.say)

    # Damit vorlesen() sprechen kann. Der Text fremder Nachrichten geht
    # direkt hierhin - am Modell vorbei, damit dort kein Fremdtext landet,
    # der wie ein Auftrag aussieht.
    tools.setze_sprecher(speaker.say)

    # Einmal taeglich eine Kopie von dem, was nicht wiederherstellbar ist.
    # Kostet Millisekunden und ein paar Kilobyte.
    from . import sicherung

    meldung = sicherung.beim_start()
    if meldung:
        print(f"  {meldung}")

    # Der Wachhund meldet sich von selbst - sparsam, siehe wachhund.py
    from . import wachhund as wh

    def melden(satz: str) -> None:
        status.clear()
        print(f"\n  [{satz}]")
        speaker.say(satz)

    wh.starten(melden)

    gruss = zeit.begruessung_mit_lage()
    print(f"JARVIS: {gruss}")
    speaker.say(gruss)

    while True:
        try:
            if wecker is not None:
                # Warten, bis das Weckwort faellt. Die Aufnahme beginnt erst
                # danach - vorher hoert nur das kleine Netz mit.
                speaker.wait()
                status.set(f"wartet auf \"{wecker.wort.replace('_', ' ')}\"")
                gehoert = threading.Event()

                def geweckt(sicherheit: float) -> None:
                    gehoert.set()

                wecker._stop.clear()
                lauscher = threading.Thread(
                    target=wecker.horchen, args=(geweckt,), daemon=True)
                lauscher.start()
                while not gehoert.wait(0.2):
                    pass
                wecker.anhalten()
                status.clear()
                print("\n  [geweckt]")
                speaker.say("Ja?")
                speaker.wait()

                status.set("Jarvis hört zu")
                user_text = ears.listen()
                status.clear()
                if not user_text:
                    print("  (nichts verstanden)")
                    continue
                print(f"DU: {user_text}")
            elif voice_mode:
                speaker.wait()          # nicht das eigene Sprechen aufnehmen
                input("\n[Enter zum Sprechen] ")
                status.set("Jarvis hört zu")
                user_text = ears.listen()
                status.clear()
                if not user_text:
                    print("  (nichts verstanden)")
                    continue
                print(f"DU: {user_text}")
            else:
                for frage in rueckfrage.offene():
                    rueckfrage_stellen(frage, status, speaker)
                agenten_melden(speaker)     # bevor die Eingabe steht
                print()
                # : manche Konsolen schicken ein unsichtbares Vorzeichen
                # mit, das sonst "/hilfe" zu einer Frage an das Modell macht
                user_text = editor.read("DU: ").strip().lstrip("​")
                if not user_text:
                    continue

            # Müdigkeit: das Modell erkennt sie nicht zuverlässig, deshalb
            # wird hier zusätzlich nachgesehen und notfalls selbst geschaltet
            if not user_text.startswith("/"):
                muede_pruefen(speaker, user_text)

            # --- Slash-Befehle: laufen lokal, ohne das Modell zu fragen ----
            if commands.ist_befehl(user_text):
                ergebnis = commands.ausfuehren(user_text, ctx)
                speaker = ctx.speaker          # /stimme kann sie ausgetauscht haben
                if ergebnis is commands.BEENDEN:
                    offen = HANGAR.alle_stoppen()
                    if offen:
                        print(f"  [{offen} Agenten abgeschaltet]")
                    print("JARVIS: Bis dann, Sir.")
                    speaker.say("Bis dann, Sir.")
                    speaker.wait()
                    status.close()
                    return 0
                if ergebnis:
                    print(ergebnis)
                continue

            # Gesprochen geht "ende" auch ohne Schrägstrich
            if voice_mode and user_text.lower().strip(" .!?") in (
                    "ende", "beenden", "stopp jarvis", "danke das war alles"):
                print("JARVIS: Bis dann, Sir.")
                speaker.say("Bis dann, Sir.")
                speaker.wait()
                status.close()
                return 0

            # --- Antwort mit Statusanzeige und satzweiser Sprachausgabe ----
            saetze = SentenceSpeaker(speaker)
            begonnen = False

            abgebrochen = threading.Event()

            def on_status(what: str) -> None:
                if abgebrochen.is_set():
                    return
                if what == "denkt":
                    # Nach einem Ausweichen soll dranstehen, wer gerade denkt
                    erste = config.MODELS[0] if config.MODELS else config.MODEL
                    zusatz = ("" if brain.model == erste
                              else f" ({brain.model.split('/')[-1]})")
                    status.set(f"Jarvis denkt{zusatz}")
                elif what.startswith("werkzeug:"):
                    name = what.split(":", 1)[1]
                    status.set(f"Jarvis {TOOL_LABELS.get(name, name)}")
                elif what.startswith("info:"):
                    status.set(f"Jarvis {what.split(':', 1)[1]}", neu=False)
                elif what.startswith("wartet:"):
                    status.set(f"Modell belegt, neuer Versuch in "
                               f"{what.split(':', 1)[1]} s")
                # "antwortet" braucht nichts zu tun - das erste Textzeichen
                # raeumt die Statuszeile selbst ab (siehe on_delta)

            def on_delta(text: str) -> None:
                nonlocal begonnen
                if abgebrochen.is_set():   # eine abgehaengte Anfrage schweigt
                    return
                # feed() gibt zurueck, was sichtbar sein soll - die
                # Sprachmarkierungen des Modells sind da schon heraus
                sichtbar = saetze.feed(text)
                if not sichtbar:
                    return
                if not begonnen:
                    begonnen = True
                    status.clear()
                    print("JARVIS: ", end="", flush=True)
                print(sichtbar, end="", flush=True)

            def notbremse() -> None:
                abgebrochen.set()
                brain.abbrechen()
                speaker.verstummen()

            # Die Anfrage laeuft nebenher. Steckt sie im Verbindungsaufbau
            # fest, laesst sie sich nicht abschiessen - aber Escape gibt
            # trotzdem sofort die Eingabe frei, und der Rest verpufft.
            ergebnis: dict = {}

            def arbeiten() -> None:
                try:
                    # In der Konsole wird vorgelesen, sofern die Stimme an
                    # ist - dann bleibt die Antwort knapp und zeichenlos.
                    # Mit --stumm steht sie nur da und darf gegliedert sein.
                    ergebnis["antwort"] = brain.ask(
                        user_text, on_status=on_status, on_delta=on_delta,
                        gesprochen=config.TTS_ENABLED)
                except Exception as exc:
                    ergebnis["fehler"] = exc

            arbeiter = threading.Thread(target=arbeiten, daemon=True)
            with EscWache(notbremse) as wache:
                arbeiter.start()
                while arbeiter.is_alive() and not abgebrochen.is_set():
                    arbeiter.join(0.05)
                    # Fragt jemand etwas, wird das hier sichtbar - sonst
                    # wartet ein Agent stumm, bis seine Zeit ablaeuft
                    for frage in rueckfrage.offene():
                        rueckfrage_stellen(frage, status, speaker)

            status.clear()
            if abgebrochen.is_set():
                print("\n  [abgebrochen]")
                continue
            if "fehler" in ergebnis:
                raise ergebnis["fehler"]
            antwort = ergebnis.get("antwort", "")
            if begonnen:
                rest = saetze.flush()
                print(rest if rest else "")
            else:                        # Antwort kam ohne Stream-Inhalt
                sichtbar = saetze.feed(antwort) + saetze.flush()
                print(f"JARVIS: {sichtbar}")

        except (KeyboardInterrupt, EOFError):
            status.close()
            print("\nJARVIS: Abgeschaltet.")
            return 0
        except Exception as exc:
            status.clear()
            if "Timeout" in type(exc).__name__ or "timed out" in str(exc).lower():
                print(f"\n[Fehler] {brain.model} hat "
                      f"{config.REQUEST_TIMEOUT:.0f} s nicht geantwortet. "
                      f"Mit '/modell <name>' ein anderes wählen oder es "
                      f"erneut versuchen.", file=sys.stderr)
            else:
                print(f"\n[Fehler] {exc}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
