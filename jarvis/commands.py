"""Slash-Befehle.

Sie laufen direkt auf dem Rechner - ohne Umweg über das Modell. Dadurch
antworten sie sofort und kosten nichts. Alles ohne "/" geht wie gehabt an Jarvis.

Neuen Befehl anlegen: Funktion schreiben und mit @befehl(...) versehen.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable

from . import config, tools

BEENDEN = object()          # Rückgabewert, der die Hauptschleife stoppt


@dataclass
class Befehl:
    name: str
    hilfe: str
    argument: str = ""
    handler: Callable | None = None

    @property
    def signatur(self) -> str:
        return f"{self.name} {self.argument}".strip()


BEFEHLE: dict[str, Befehl] = {}

# Zweitnamen zeigen auf den Hauptnamen. Sie stehen NICHT in der Hilfe - sonst
# waere die Liste doppelt so lang und halb so uebersichtlich -, funktionieren
# aber genauso. Gedacht fuer das, was Leute aus anderen Programmen tippen.
ZWEITNAMEN: dict[str, str] = {}


def befehl(name: str, hilfe: str, argument: str = "",
           auch: tuple[str, ...] = ()) -> Callable:
    def deko(fn: Callable) -> Callable:
        BEFEHLE[name] = Befehl(name, hilfe, argument, fn)
        for zweit in auch:
            ZWEITNAMEN[zweit] = name
        return fn
    return deko


class Kontext:
    """Was die Befehle anfassen dürfen."""

    def __init__(self, brain, speaker, sprachmodus: bool) -> None:
        self.brain = brain
        self.speaker = speaker
        self.sprachmodus = sprachmodus


# --- Allgemein --------------------------------------------------------------
@befehl("/hilfe", "zeigt alle Befehle", "[befehl]", auch=("/help", "/?"))
def _hilfe(ctx: Kontext, arg: str) -> str:
    arg = arg.strip().lower()
    if arg:
        if not arg.startswith("/"):
            arg = "/" + arg
        treffer = [b for n, b in sorted(BEFEHLE.items()) if n.startswith(arg)]
        # Auch unter den Zweitnamen nachsehen: wer "/help cl" tippt, sucht
        # "/clear" - und das ist ein Zweitname von "/neu". Ohne das kam
        # "Kein Befehl faengt mit '/cl' an", obwohl es genau den gibt.
        for zweit, haupt in sorted(ZWEITNAMEN.items()):
            if zweit.startswith(arg) and BEFEHLE[haupt] not in treffer:
                treffer.append(BEFEHLE[haupt])
        if not treffer:
            nah = _aehnlich(arg)
            return (f"Kein Befehl faengt mit '{arg}' an."
                    + (f" Meintest du {'  '.join(nah)}?" if nah else ""))
        breite = max(len(b.signatur) for b in treffer)
        return "\n".join(f"  {b.signatur:<{breite}}   {b.hilfe}" for b in treffer)

    breite = max(len(b.signatur) for b in BEFEHLE.values())
    zeilen = [f"  {b.signatur:<{breite}}   {b.hilfe}"
              for _, b in sorted(BEFEHLE.items())]
    return ("Befehle - Tab vervollständigt, Escape leert die Zeile:\n"
            + "\n".join(zeilen)
            + "\n\nAlles ohne '/' geht als Frage an Jarvis.")


@befehl("/ende", "beendet Jarvis")
def _ende(ctx: Kontext, arg: str):
    return BEENDEN


@befehl("/reset", "löscht den Gespraechsverlauf", auch=("/neustart",))
def _reset(ctx: Kontext, arg: str) -> str:
    ctx.brain.reset()
    return "Verlauf gelöscht."


@befehl("/leeren", "leert den Bildschirm")
def _leeren(ctx: Kontext, arg: str) -> str:
    os.system("cls")
    return ""


# --- Chats ------------------------------------------------------------------
@befehl("/neu", "fängt einen neuen Chat an; das alte bleibt erhalten",
        "[titel]", auch=("/clear", "/new"))
def _neuer_chat(ctx: Kontext, arg: str) -> str:
    from . import chats

    chats.neu(arg.strip())
    ctx.brain.reset()
    # Ohne eigenen Titel die Kennung zu nennen ("chat-20260913-135215") sagt
    # niemandem etwas - den Namen holt sich der Chat gleich aus der ersten
    # Frage.
    name = arg.strip()
    return (f"Neuer Chat: {name}. " if name else "Neuer Chat. ") \
        + "Das vorige Gespräch bleibt unter /chats."


@befehl("/mikrofon", "zeigt die Mikrofone und was sie gerade liefern",
        "[nummer]", auch=("/mikro",))
def _mikrofon(ctx: Kontext, arg: str) -> str:
    """Welches Mikrofon nimmt Jarvis - und kommt dort etwas an?

    Der Anlass: "Weckwort bereit" stand im Protokoll, waehrend das Geraet
    durchgehend Nullen lieferte. Neun Eingabegeraete werden gemeldet,
    darunter dasselbe Headset viermal ueber verschiedene Treiberwege. Ohne
    diese Liste raet man.
    """
    from . import ohr

    liste = ohr.mikrofone()
    if liste and "fehler" in liste[0]:
        return f"Mikrofone nicht lesbar: {liste[0]['fehler']}"
    if not liste:
        return "Kein Mikrofon gefunden."

    wahl = arg.strip()
    if wahl:
        nummern = [str(m["nummer"]) for m in liste]
        if wahl not in nummern:
            return f"Nummer aus der Liste, bitte: {', '.join(nummern)}"
        name = [m["name"] for m in liste if str(m["nummer"]) == wahl][0]
        return (f"Trag JARVIS_MIKROFON={wahl} in die .env ein und starte "
                f"Jarvis neu, dann hoert er auf '{name}'.\n"
                f"(Hier umzustellen brächte nichts - das Zuhören läuft "
                f"schon und müsste ohnehin neu beginnen.)")

    zustand = ohr.zustand()
    pegel = zustand.get("pegel", {})
    zeilen = []
    for m in liste:
        marke = ">" if m["benutzt"] else " "
        zeilen.append(f"  {marke} {m['nummer']:>2}. {m['name'][:46]}")

    fuss = []
    if zustand.get("an"):
        jetzt = pegel.get("jetzt", 0.0)
        zustandswort = ("es kommt nichts an" if jetzt < 2e-4
                        else "Ton kommt an")
        fuss.append(f"    Weckwort laeuft, {zustandswort} "
                    f"(Pegel {jetzt:.5f}, {pegel.get('bloecke', 0)} Bloecke)")
        fuss.append(f"    Bisher {zustand.get('treffer', 0)}x erkannt, "
                    f"beste Naehe {pegel.get('beste_naehe', 0):.3f} "
                    f"von {zustand.get('schwelle', 0.4)} noetig")
    else:
        fuss.append(f"    Weckwort aus: {zustand.get('grund', '?')}")
    fuss.append("    /mikrofon <nummer> sagt, wie man wechselt")
    return "\n".join(zeilen + fuss)


@befehl("/chats", "zeigt alle Chats; mit Nummer wechselt er dorthin",
        "[nummer]")
def _chats(ctx: Kontext, arg: str) -> str:
    from . import chats

    liste = chats.liste()
    if not liste:
        return "Noch keine Chats."

    wahl = arg.strip()
    if wahl:
        if not wahl.isdigit() or not 1 <= int(wahl) <= len(liste):
            return f"Nummer zwischen 1 und {len(liste)}, bitte."
        ziel = liste[int(wahl) - 1]
        chats.wechseln(ziel["id"])
        anzahl = ctx.brain.chat_oeffnen(ziel["id"])
        titel = ziel["titel"] or ziel["id"]
        return f"Chat {wahl} offen: {titel} ({anzahl} Nachrichten geladen)."

    breite = max(len(c["titel"] or c["id"]) for c in liste)
    zeilen = []
    for nummer, chat in enumerate(liste, 1):
        marke = ">" if chat["aktiv"] else " "
        titel = chat["titel"] or chat["id"]
        zeilen.append(f"  {marke} {nummer:>2}. {titel:<{breite}}  "
                      f"{chat['anzahl']:>3} Nachrichten")
    return "\n".join(zeilen) + "\n    (/chats <nummer> wechselt)"


def ping_tabelle(brain) -> str:
    """Die Messung als Tabelle, mit '>' vor dem gewählten Modell."""
    if not brain.ping:
        return "  Noch nicht gepingt - mit '/modell pingen' nachholen."
    breite = max(len(e["modell"]) for e in brain.ping)
    zeilen = []
    for eintrag in brain.ping:
        marke = ">" if eintrag["modell"] == brain.model else " "
        zeit = (f"{eintrag['dauer']:5.1f}s" if eintrag["zustand"] == "frei"
                else "     -")
        zeilen.append(f"  {marke} {eintrag['modell']:<{breite}}  {zeit}  "
                      f"{eintrag['zustand']}")
    regel = ("schnellstes zuerst" if config.MODELL_WAHL == "schnellste"
             else "bestes verfügbares zuerst")
    if not brain.rangliste:
        zeilen.append("  ! kein Modell frei - später '/modell pingen'")
    return "\n".join(zeilen) + f"\n    ({regel})"


@befehl("/modell", "zeigt die Modelle; 'pingen' misst neu, <name> wechselt",
        "[pingen|<name>]")
def _modell(ctx: Kontext, arg: str) -> str:
    arg = arg.strip()

    if arg in ("pingen", "prüfen", "pruefen", "test", "check"):
        vorher = ctx.brain.model
        ctx.brain.pingen()
        tabelle = ping_tabelle(ctx.brain)
        if ctx.brain.model != vorher:
            return f"{tabelle}\n  Gewechselt von {vorher} auf {ctx.brain.model}."
        return tabelle

    if arg:
        treffer = [m for m in config.MODELS if arg.lower() in m.lower()]
        name = treffer[0] if len(treffer) == 1 else arg
        ctx.brain.model = name
        if name not in ctx.brain.rangliste:   # von Hand gewaehlt: nach vorn
            ctx.brain.rangliste = [name] + ctx.brain.rangliste
        return f"Jarvis spricht jetzt mit {name}."

    return (f"{ctx.brain.model} über {config.BASE_URL}, "
            f"Denktiefe {config.REASONING_EFFORT}, "
            f"Verlauf {len(ctx.brain.history)} Nachrichten\n"
            + ping_tabelle(ctx.brain))


# --- Stimme -----------------------------------------------------------------
@befehl("/stumm", "schaltet die Sprachausgabe um")
def _stumm(ctx: Kontext, arg: str) -> str:
    ctx.speaker.enabled = not ctx.speaker.enabled and config.TTS_ENABLED
    return f"Stimme {'an' if ctx.speaker.enabled else 'aus'}."


@befehl("/stimme", "listet Stimmen oder wechselt sie", "[name]")
def _stimme(ctx: Kontext, arg: str) -> str:
    from .voice import make_speaker

    ordner = config.ROOT / "voices"
    vorhanden = sorted(p.stem for p in ordner.glob("*.onnx"))
    windows = _windows_stimmen()
    arg = arg.strip()

    def marke(laeuft: bool) -> str:
        return ">" if laeuft else " "

    if not arg:
        auf_windows = config.TTS_BACKEND == "windows"
        zeilen = ["Piper - eigene Modelle, warm, aber rechenintensiv:"]
        if vorhanden:
            for n in vorhanden:
                zeilen.append(f"  {marke(not auf_windows and n == config.PIPER_VOICE)} {n}")
        else:
            zeilen.append("  (keine installiert)")
        if windows:
            zeilen.append("Windows - mitgeliefert, rund hundertmal schneller:")
            for n in windows:
                zeilen.append(f"  {marke(auf_windows and config.WIN_STIMME in n)} {n}")
        return "\n".join(zeilen) + "\n  Wechseln mit /stimme <name>"

    # Erst bei Windows nachsehen: kurze Namen wie "Katja" sind eindeutig
    treffer = [n for n in windows if arg.lower() in n.lower()]
    if treffer:
        from . import voice as v
        config.TTS_BACKEND = "windows"
        config.WIN_STIMME = treffer[0].replace("Microsoft ", "")
        v._win_web = None
        ctx.speaker = make_speaker()
        return f"Stimme gewechselt auf {treffer[0]} (Windows)."

    passend = [n for n in vorhanden if arg.lower() in n.lower()]
    if passend:
        config.TTS_BACKEND = "piper"
        config.PIPER_VOICE = passend[0]
        config.PIPER_MODEL = ordner / f"{passend[0]}.onnx"
        ctx.speaker = make_speaker()
        return f"Stimme gewechselt auf {passend[0]} (Piper)."

    if arg not in vorhanden:
        return (f"'{arg}' kenne ich nicht. Piper: "
                f"{', '.join(vorhanden) or 'keine'}. "
                f"Windows: {', '.join(windows) or 'keine'}")

    config.PIPER_VOICE = arg
    config.PIPER_MODEL = ordner / f"{arg}.onnx"
    ctx.speaker = make_speaker()
    return f"Stimme gewechselt auf {arg}."


def _windows_stimmen() -> list[str]:
    """Die deutschen Stimmen, die Windows selbst mitbringt."""
    try:
        import winsdk.windows.media.speechsynthesis as sprache
        return [v.display_name for v in sprache.SpeechSynthesizer.all_voices
                if v.language.lower().startswith("de-")]
    except Exception:
        return []


@befehl("/lauter", "dreht die Lautstärke hoch")
def _lauter(ctx: Kontext, arg: str) -> str:
    return tools.set_volume("up")


@befehl("/leiser", "dreht die Lautstärke runter")
def _leiser(ctx: Kontext, arg: str) -> str:
    return tools.set_volume("down")


# --- Direkte Werkzeuge (ohne Modell, also sofort) ---------------------------
@befehl("/zeit", "Datum und Uhrzeit")
def _zeit(ctx: Kontext, arg: str) -> str:
    return tools.get_time()


@befehl("/status", "Auslastung des Rechners")
def _status(ctx: Kontext, arg: str) -> str:
    return tools.system_status()


@befehl("/standort", "ungefährer Standort dieses Rechners")
def _standort(ctx: Kontext, arg: str) -> str:
    return tools.get_location()


@befehl("/wetter", "Wetter hier oder anderswo", "[ort] [tage]")
def _wetter(ctx: Kontext, arg: str) -> str:
    teile = arg.rsplit(" ", 1)
    if len(teile) == 2 and teile[1].isdigit():
        return tools.get_weather(teile[0], int(teile[1]))
    return tools.get_weather(arg.strip(), 1)


@befehl("/nachrichten", "Schlagzeilen, optional zu einem Thema", "[thema]")
def _nachrichten(ctx: Kontext, arg: str) -> str:
    return tools.get_news(arg.strip(), 5).replace(" || ", "\n  - ")


@befehl("/öffne", "startet ein freigegebenes Programm", "<name>")
def _oeffne(ctx: Kontext, arg: str) -> str:
    if not arg.strip():
        return f"Erlaubt: {', '.join(sorted(set(tools.APPS)))}"
    return tools.open_app(arg.strip())


@befehl("/autostart", "startet Jarvis mit Windows", "[an|aus|weckwort]")
def _autostart(ctx: Kontext, arg: str) -> str:
    from . import autostart

    arg = arg.strip().lower()
    if arg in ("aus", "weg", "off"):
        return autostart.ausschalten()
    if arg in ("an", "ein", "on", "oberflaeche"):
        return autostart.einschalten("oberflaeche")
    if arg == "weckwort":
        return autostart.einschalten("weckwort")

    if arg in ("desktop", "verknuepfung", "verknüpfung"):
        return autostart.desktop_verknuepfung()
    if arg in ("kurzname", "adresse"):
        return autostart.kurzname(True)

    lage = autostart.zustand()
    zeilen = [f"Autostart ist an ({lage['art']})." if lage["an"]
              else "Autostart ist aus."]
    zeilen += [
        "  /autostart an         Weboberfläche still im Hintergrund",
        "  /autostart weckwort   hört dauerhaft auf \"Hey Jarvis\"",
        "  /autostart aus        abschalten",
        "  /autostart desktop    Verknüpfung auf den Desktop legen",
        "  /autostart kurzname   http://jarvis:8765 statt der Zahlenadresse",
    ]
    return "\n".join(zeilen)


@befehl("/verlauf", "durchsucht frühere Gespräche", "[stichwort]")
def _verlauf(ctx: Kontext, arg: str) -> str:
    from . import verlauf

    letzte = verlauf.letzte_sitzung()
    kopf = (f"Letztes Gespräch: {verlauf.fuer_systemprompt()}\n"
            if letzte and not arg.strip() else "")
    treffer, weg = verlauf.suchen_nach_sinn(arg.strip(), grenze=10)
    if not treffer:
        return kopf + "Nichts gefunden."
    from .gedaechtnis import wie_lange_her
    zeilen = [f"  {'DU' if e['rolle'] == 'du' else 'JA'} "
              f"({wie_lange_her(e['wann'])}): {e['text'][:90]}"
              for e in treffer]
    # Welcher Weg es war, gehört dazu: über die Textsuche gefunden heißt,
    # dass sinngleiche Stellen mit anderen Worten übersehen wurden.
    fuss = ("" if weg == "Bedeutung" or not arg.strip()
            else "\n  (nach Wortlaut gesucht - das Bedeutungsmodell "
                 "antwortete nicht)")
    return kopf + "\n".join(zeilen) + fuss


@befehl("/hangar", "zeigt die Agenten (Mk 1, Mk 2 ...)")
def _hangar(ctx: Kontext, arg: str) -> str:
    from .agenten import HANGAR

    weg = HANGAR.aufraeumen()
    uebersicht = HANGAR.uebersicht()
    return uebersicht + (f"\n  ({weg} eingemottet und freigegeben)" if weg else "")


@befehl("/agent", "schickt einen Agenten für eine längere Aufgabe los",
        "<aufgabe>")
def _agent(ctx: Kontext, arg: str) -> str:
    if not arg.strip():
        return ("Welche Aufgabe?  Beispiel:\n"
                "  /agent sammle das Wetter der naechsten drei Tage fuer "
                "Berlin, Hamburg und Muenchen")
    return tools.start_agent(arg.strip())


@befehl("/bericht", "holt den Bericht eines fertigen Agenten", "[Mk 2]")
def _bericht(ctx: Kontext, arg: str) -> str:
    return tools.agent_bericht(arg.strip())


@befehl("/stoppen", "hält einen Agenten an - ohne Namen alle", "[Mk 2]")
def _stoppen(ctx: Kontext, arg: str) -> str:
    from .agenten import HANGAR

    name = arg.strip()
    if not name:
        return f"{HANGAR.alle_stoppen()} Agenten angehalten."
    if not name.lower().startswith("mk"):
        name = f"Mk {name}"
    agent = HANGAR.agenten.get(name)
    if agent is None:
        return f"Einen {name} gibt es nicht."
    agent.stoppen()
    HANGAR.entfernen(name)
    return f"{name} angehalten und eingemottet."


@befehl("/code", "schreibt ein Programm - ohne Umweg über das Gespräch",
        "[sprache|datei:] <aufgabe>")
def _code(ctx: Kontext, arg: str) -> str:
    if not arg.strip():
        return ("Was soll das Programm tun?  Beispiel:\n"
                "  /code ein Skript, das alte Logdateien loescht\n"
                "  /code powershell: zeigt die groessten Ordner\n"
                "  /code skript.py: baue eine Fehlerbehandlung ein")
    teil1, _, rest = arg.partition(":")
    teil1_sauber = teil1.strip()
    rest_sauber = rest.strip()
    if rest_sauber:
        # Fall 1: Dateiname angegeben (z.B. "tool.py: erweitere um...")
        datei_pfad = config.WERKSTATT / teil1_sauber
        hat_sichere_endung = Path(teil1_sauber).suffix.lower() in tools._SICHERE_ENDUNGEN
        if datei_pfad.exists() or hat_sichere_endung:
            return tools.edit_code(teil1_sauber, rest_sauber)
        # Fall 2: Sprache angegeben (z.B. "powershell: zeigt...")
        if teil1_sauber.lower() in tools._ENDUNGEN:
            return tools.write_code(rest_sauber, sprache=teil1_sauber.lower())
    return tools.write_code(arg.strip())


@befehl("/edit", "bearbeitet ein vorhandenes Skript in werkstatt/",
        "<datei>[:] <anweisung>")
def _edit(ctx: Kontext, arg: str) -> str:
    if not arg.strip():
        config.WERKSTATT.mkdir(parents=True, exist_ok=True)
        dateien = sorted(p.name for p in config.WERKSTATT.iterdir() if p.is_file() and not p.name.endswith(".bak"))
        liste = ", ".join(dateien) if dateien else "Werkstatt ist leer."
        return ("Welche Datei soll bearbeitet werden?  Beispiel:\n"
                "  /edit mein_skript.py: baue eine Fortschrittsanzeige ein\n"
                f"Vorhanden in werkstatt/: {liste}")
    if ":" in arg:
        datei, _, anweisung = arg.partition(":")
    else:
        teile = arg.strip().split(None, 1)
        datei = teile[0]
        anweisung = teile[1] if len(teile) > 1 else ""
    return tools.edit_code(datei.strip(), anweisung.strip())


@befehl("/werkstatt", "öffnet den Ordner mit dem geschriebenen Code")
def _werkstatt(ctx: Kontext, arg: str) -> str:
    config.WERKSTATT.mkdir(parents=True, exist_ok=True)
    dateien = sorted(p.name for p in config.WERKSTATT.iterdir() if p.is_file())
    os.system(f'start "" "{config.WERKSTATT}"')
    if not dateien:
        return "Noch nichts geschrieben."
    return f"{len(dateien)} Dateien: " + ", ".join(dateien[-10:])


@befehl("/btw", "Zwischenruf - bleibt nicht im Gespräch", "<text>")
def _btw(ctx: Kontext, arg: str) -> str:
    """Etwas sagen, ohne dass es im Verlauf stehen bleibt.

    Jarvis kennt beim Antworten den bisherigen Verlauf, aber diese Frage und
    seine Antwort darauf verschwinden danach: nicht im Gespräch, nicht im
    Archiv, nicht im Gedächtnis. Für Nebensächliches, das den Faden nicht
    zerreißen soll.
    """
    if not arg.strip():
        return ("Was denn? /btw sagt etwas, das nicht im Gespräch "
                "stehen bleibt.")
    antwort = ctx.brain.nebenbei(arg.strip())
    return (antwort or "(nichts)") + "\n  [nebenbei - steht nicht im Verlauf]"


@befehl("/sicherung", "sichert Gedächtnis, Archiv und Werkstatt",
        "[liste|zurueck <name>]")
def _sicherung(ctx: Kontext, arg: str) -> str:
    from . import sicherung

    wunsch = arg.strip().lower()
    if wunsch.startswith("liste"):
        return sicherung.uebersicht()
    if wunsch.startswith("zurueck") or wunsch.startswith("zurück"):
        name = arg.split(maxsplit=1)[1].strip() if len(arg.split()) > 1 else ""
        if not name:
            return f"Welche? {sicherung.uebersicht()}"
        return sicherung.zurueckholen(name)
    return sicherung.anlegen("von Hand")


@befehl("/merken", "legt etwas ins Langzeitgedächtnis", "<text>")
def _merken(ctx: Kontext, arg: str) -> str:
    if not arg.strip():
        return "Was soll ich mir merken?"
    return tools.remember(arg.strip())


@befehl("/gedaechtnis", "durchsucht das Langzeitgedächtnis", "[suche]")
def _gedaechtnis(ctx: Kontext, arg: str) -> str:
    return tools.recall(arg.strip()).replace(" | ", "\n  - ")


# --- Auswertung -------------------------------------------------------------
def ist_befehl(eingabe: str) -> bool:
    return eingabe.lstrip().startswith("/")


def ausfuehren(eingabe: str, ctx: Kontext):
    """Gibt den Antworttext zurück, BEENDEN, oder None bei Unbekanntem."""
    name, _, arg = eingabe.strip().partition(" ")
    name = name.lower()
    name = ZWEITNAMEN.get(name, name)

    if name in BEFEHLE:
        return BEFEHLE[name].handler(ctx, arg)

    treffer = [n for n in sorted(BEFEHLE) if n.startswith(name)]
    if len(treffer) == 1:                       # eindeutige Abkuerzung
        return BEFEHLE[treffer[0]].handler(ctx, arg)
    if treffer:
        return f"'{name}' ist mehrdeutig: {'  '.join(treffer)}"
    # Ein aehnlicher Name hilft mehr als "gibt es nicht". Gemessen im echten
    # Gebrauch: getippt wurde "/help cl" und "/clear" - englische Namen aus
    # anderen Programmen. Die landeten beim Modell, und das erfand daraufhin
    # eine ganze Befehlsliste, die es nie gab.
    nah = _aehnlich(name)
    if nah:
        return (f"'{name}' kenne ich nicht. Meintest du {'  '.join(nah)}?"
                "\n/hilfe zeigt alle.")
    return f"Unbekannter Befehl '{name}'. /hilfe zeigt alle."


def _aehnlich(name: str) -> list[str]:
    """Die naechstliegenden Befehle zu einem Vertipper."""
    import difflib

    alle = list(BEFEHLE) + list(ZWEITNAMEN)
    return difflib.get_close_matches(name, alle, n=3, cutoff=0.6)


def namen_mit_hilfe() -> dict[str, str]:
    return {n: b.hilfe for n, b in BEFEHLE.items()}
