"""Der Wachhund: die Stellen, an denen Jarvis von selbst den Mund aufmacht.

Der schwierige Teil ist nicht das Erkennen, sondern das Maß. Ein Assistent,
der ständig dazwischenredet, wird nach zwei Tagen abgeschaltet. Deshalb drei
Grundregeln:

1. Nur wenn jemand da ist. Über fünf Minuten Leerlauf: er schweigt.
2. Jede Regel hat ihre eigene Sperrzeit. Ereignisse (ein Download ist fertig)
   melden sich einmal. Zustände (der Speicher ist voll) bleiben ja bestehen -
   die dürfen erst nach einer halben Stunde wieder.
3. Nachts nur, was nicht warten kann.
"""
from __future__ import annotations

import datetime as dt
import threading
import time

import psutil

from . import config, protokoll, zeit


class Regel:
    """Eine Sache, auf die geachtet wird."""

    def __init__(self, name: str, beschreibung: str, sperrzeit: float,
                 pruefen, dringend: bool = False) -> None:
        self.name = name
        self.beschreibung = beschreibung
        self.sperrzeit = sperrzeit        # Sekunden bis zur naechsten Meldung
        self.pruefen = pruefen            # gibt einen Satz zurueck oder ""
        self.dringend = dringend          # darf auch nachts
        self.aktiv = True
        self.zuletzt = 0.0

    def faellig(self) -> bool:
        return self.aktiv and time.monotonic() - self.zuletzt >= self.sperrzeit


# --- Die einzelnen Beobachtungen --------------------------------------------
_downloads_bekannt: set = set()
_downloads_wartend: dict = {}
_lange_laeufer: dict = {}


def _downloads_pruefen() -> str:
    """Eine neue, fertige Datei im Downloads-Ordner.

    Erkannt wird sie daran, dass sie zwischen zwei Runden nicht mehr
    gewachsen ist - solange sie noch laedt, aendert sich ihre Groesse.
    """
    from pathlib import Path

    global _downloads_bekannt
    ordner = Path.home() / "Downloads"
    if not ordner.is_dir():
        return ""

    unfertig = (".crdownload", ".part", ".partial", ".tmp", ".!ut", ".opdownload")
    jetzt = {}
    try:
        for datei in ordner.iterdir():
            if not datei.is_file() or datei.suffix.lower() in unfertig:
                continue
            if datei.name.startswith("~"):
                continue
            jetzt[datei.name] = datei.stat().st_size
    except OSError:
        return ""

    if not _downloads_bekannt:                  # erster Durchlauf: nur merken
        _downloads_bekannt = set(jetzt)
        return ""

    fertig = []
    for name, groesse in jetzt.items():
        if name in _downloads_bekannt:
            continue
        vorher = _downloads_wartend.get(name)
        if vorher is None or vorher != groesse:
            _downloads_wartend[name] = groesse   # waechst noch, naechste Runde
            continue
        fertig.append((name, groesse))
        _downloads_bekannt.add(name)
        _downloads_wartend.pop(name, None)

    for verschwunden in set(_downloads_wartend) - set(jetzt):
        _downloads_wartend.pop(verschwunden, None)
    _downloads_bekannt &= set(jetzt) | _downloads_bekannt

    if not fertig:
        return ""
    if len(fertig) == 1:
        name, groesse = fertig[0]
        return (f"Der Download ist fertig, {config.USER_NAME}: {name}"
                + (f", {groesse/1e6:.0f} Megabyte." if groesse > 1e6 else "."))
    return (f"{len(fertig)} Downloads sind fertig, {config.USER_NAME}: "
            + ", ".join(n for n, _ in fertig[:3]) + ".")


def _agenten_pruefen() -> str:
    from .agenten import HANGAR

    fertige = HANGAR.fertige_ohne_meldung()
    if not fertige:
        return ""
    if len(fertige) == 1:
        a = fertige[0]
        return f"{a.name} ist fertig, {config.USER_NAME}. {a.bericht[:200]}"
    return (f"{len(fertige)} Agenten sind fertig: "
            + ", ".join(a.name for a in fertige) + ".")


def _lange_vorgaenge_pruefen() -> str:
    """Ein Programm, das lange unter Volllast lief, hat sich beendet."""
    global _lange_laeufer
    jetzt = time.monotonic()
    laufend = {}

    for p in psutil.process_iter(["pid", "name"]):
        try:
            last = p.cpu_percent(None)
            if last > config.WACH_LAST_GRENZE:
                pid = p.info["pid"]
                beginn = _lange_laeufer.get(pid, {}).get("seit", jetzt)
                laufend[pid] = {"name": p.info["name"], "seit": beginn}
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    beendet = []
    for pid, daten in _lange_laeufer.items():
        if pid in laufend:
            continue
        dauer = jetzt - daten["seit"]
        if dauer >= config.WACH_LAST_DAUER:
            beendet.append((daten["name"], dauer))
    _lange_laeufer = laufend

    if not beendet:
        return ""
    name, dauer = beendet[0]
    return (f"{name} ist durch, {config.USER_NAME} - "
            f"es lief {dauer/60:.0f} Minuten unter Last.")


def _platte_pruefen() -> str:
    try:
        nutzung = psutil.disk_usage("C:\\")
    except OSError:
        return ""
    frei = nutzung.free / 1e9
    if frei > config.WACH_PLATTE_GB:
        return ""
    return (f"Auf Laufwerk C sind nur noch {frei:.0f} Gigabyte frei, "
            f"{config.USER_NAME}.")


def _speicher_pruefen() -> str:
    m = psutil.virtual_memory()
    if m.percent < config.WACH_RAM_PROZENT:
        return ""
    return (f"Der Arbeitsspeicher ist bei {m.percent:.0f} Prozent, "
            f"{config.USER_NAME} - nur noch {m.available/1e6:.0f} Megabyte frei.")


_hauptmodell_war_belegt = False


def _hauptmodell_pruefen() -> str:
    """Ist das Wunschmodell wieder frei? Kostet einen Aufruf ueber ein Token."""
    global _hauptmodell_war_belegt
    from . import web

    brain = web._brain
    if brain is None or not config.MODELS:
        return ""
    erstes = config.MODELS[0]
    if brain.model == erstes:
        _hauptmodell_war_belegt = False
        return ""

    _hauptmodell_war_belegt = True
    ergebnis = brain._anklopfen(erstes)
    if ergebnis["zustand"] != "frei":
        return ""
    brain.model = erstes
    if erstes not in brain.rangliste:
        brain.rangliste = [erstes] + brain.rangliste
    return (f"{erstes} ist wieder frei, {config.USER_NAME} - "
            f"ich habe zurueckgewechselt.")


def _nachtmodus_pruefen() -> str:
    """Schaltet den Blaulichtfilter zur eingestellten Zeit.

    Sagt es nur beim Umschalten, nicht bei jeder Runde - und nur, wenn
    tatsaechlich jemand da ist, sonst haette er es gar nicht gesehen.
    """
    from . import regler

    if not config.NACHT_AUTOMATISCH:
        return ""
    soll = regler.nachtzeit()
    ist, _staerke = regler.nachtmodus_lesen()
    if soll == ist:
        return ""

    geklappt, _ = regler.nachtmodus_setzen(soll)
    if not geklappt:
        return ""
    if soll:
        return (f"Es ist nach {config.NACHT_VON_STUNDE} Uhr, "
                f"{config.USER_NAME} - ich habe den Nachtmodus eingeschaltet.")
    return "Guten Morgen - Nachtmodus aus."


_war_weg = False


def _benachrichtigungen_pruefen() -> str:
    """Was kam, waehrend niemand da war.

    Gemeldet wird erst, wenn jemand zurueck ist - waehrend der Abwesenheit
    spraeche es ins Leere. Gesammelt wird aber die ganze Zeit, sonst fehlte
    hinterher die Haelfte.
    """
    global _war_weg
    from . import melder, zeit as zeitmodul

    try:
        melder.BRIEFKASTEN.abholen()
    except Exception:
        return ""

    weg = zeitmodul.leerlauf_sekunden() > config.WACH_ANWESEND
    if weg:
        _war_weg = True
        return ""                     # sammeln, aber schweigen
    if not _war_weg:
        return ""                     # niemand war weg, nichts nachzutragen
    _war_weg = False

    zusammen = melder.BRIEFKASTEN.zusammenfassung(
        dt.datetime.now() - dt.timedelta(hours=6))
    if zusammen.startswith("Nichts Neues"):
        return ""
    # Anbieten, nicht vorlesen: der Inhalt geht spaeter ueber vorlesen()
    # direkt an die Stimme, nicht durch das Modell.
    return f"Waehrend Sie weg waren: {zusammen}. Soll ich vorlesen?"


def _laufzeit_pruefen() -> str:
    seit = dt.datetime.fromtimestamp(psutil.boot_time())
    tage = (dt.datetime.now() - seit).days
    if tage < config.WACH_LAUFZEIT_TAGE:
        return ""
    return (f"Der Rechner laeuft seit {tage} Tagen ohne Neustart, "
            f"{config.USER_NAME}.")


# --- Die Wache ---------------------------------------------------------------
class Wachhund:
    def __init__(self, sprechen=None) -> None:
        self.sprechen = sprechen or (lambda text: print(f"\n  [{text}]"))
        self.zuletzt_gesprochen = 0.0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.regeln = [
            Regel("download", "Ein Download ist fertig", 0,
                  _downloads_pruefen),
            Regel("agent", "Ein Agent hat seinen Bericht", 0,
                  _agenten_pruefen),
            Regel("vorgang", "Ein langer Vorgang ist beendet", 60,
                  _lange_vorgaenge_pruefen),
            Regel("platte", "Das Laufwerk laeuft voll", 6 * 3600,
                  _platte_pruefen, dringend=True),
            Regel("speicher", "Der Arbeitsspeicher ist voll",
                  config.WACH_RAM_SPERRE, _speicher_pruefen),
            Regel("modell", "Das Hauptmodell ist wieder frei", 600,
                  _hauptmodell_pruefen),
            Regel("laufzeit", "Der Rechner laeuft sehr lange", 24 * 3600,
                  _laufzeit_pruefen),
            Regel("nachrichten", "Nachrichten, waehrend niemand da war", 300,
                  _benachrichtigungen_pruefen),
            # Darf auch nachts - sonst koennte er sich nie einschalten
            Regel("nachtmodus", "Nachtmodus zur eingestellten Zeit", 60,
                  _nachtmodus_pruefen, dringend=True),
        ]
        for regel in self.regeln:
            regel.aktiv = regel.name not in config.WACH_AUS

    def _nachtruhe(self) -> bool:
        """Ist gerade Ruhezeit?

        Die alte Fassung rechnete immer so, als liefe das Fenster ueber
        Mitternacht ("stunde >= von or stunde < bis"). Bei 23 bis 7 stimmt
        das - bei einer Mittagsruhe von 13 bis 15 waere fast jede Stunde
        "Ruhezeit" gewesen, und Jarvis haette den ganzen Tag geschwiegen.
        Da sich die Zeiten in der Oberflaeche einstellen lassen, ist das kein
        theoretischer Fall.
        """
        stunde = dt.datetime.now().hour
        von, bis = config.WACH_RUHE_VON, config.WACH_RUHE_BIS
        if von == bis:
            return False                   # kein Fenster - nie Ruhezeit
        if von < bis:
            return von <= stunde < bis     # innerhalb eines Tages
        return stunde >= von or stunde < bis   # ueber Mitternacht

    def _runde(self) -> None:
        anwesend = zeit.leerlauf_sekunden() <= config.WACH_ANWESEND

        # Der Nachtmodus schaltet unabhaengig davon, ob jemand da ist - sonst
        # spraenge er nachts nie an. Nur gesagt wird es, wenn jemand zusieht.
        nacht_regel = next((r for r in self.regeln if r.name == "nachtmodus"),
                           None)
        if nacht_regel and nacht_regel.aktiv:
            try:
                meldung = nacht_regel.pruefen()
            except Exception as exc:
                protokoll.schreibe("fehler", f"Wachhund/nachtmodus: {exc}")
                meldung = ""
            if meldung:
                protokoll.schreibe("system", meldung)
                if anwesend:
                    self.sprechen(meldung)
                    self.zuletzt_gesprochen = time.monotonic()

        # Niemand da? Alles Weitere spraeche ins Leere.
        if not anwesend:
            return
        if time.monotonic() - self.zuletzt_gesprochen < config.WACH_PAUSE:
            return

        nacht = self._nachtruhe()
        for regel in self.regeln:
            if regel.name == "nachtmodus":
                continue                  # schon oben erledigt
            if not regel.faellig() or (nacht and not regel.dringend):
                continue
            try:
                satz = regel.pruefen()
            except Exception as exc:
                protokoll.schreibe("fehler", f"Wachhund/{regel.name}: {exc}")
                regel.zuletzt = time.monotonic()
                continue
            if not satz:
                continue
            regel.zuletzt = time.monotonic()
            self.zuletzt_gesprochen = time.monotonic()
            protokoll.schreibe("system", satz)
            self.sprechen(satz)
            return                    # immer nur eine Sache auf einmal

    def _laufen(self) -> None:
        time.sleep(8)                 # dem Start Ruhe lassen
        while not self._stop.wait(config.WACH_TAKT):
            self._runde()

    def starten(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._laufen, daemon=True,
                                        name="Wachhund")
        self._thread.start()

    def anhalten(self) -> None:
        self._stop.set()

    def uebersicht(self) -> list[dict]:
        jetzt = time.monotonic()
        return [{
            "name": r.name, "beschreibung": r.beschreibung, "aktiv": r.aktiv,
            "sperrzeit": r.sperrzeit, "dringend": r.dringend,
            "wartet_noch": max(0, round(r.sperrzeit - (jetzt - r.zuletzt)))
            if r.zuletzt else 0,
        } for r in self.regeln]

    def umschalten(self, name: str, an: bool) -> bool:
        for r in self.regeln:
            if r.name == name:
                r.aktiv = an
                return True
        return False


WACHHUND: Wachhund | None = None


def starten(sprechen=None) -> Wachhund:
    global WACHHUND
    if WACHHUND is None:
        WACHHUND = Wachhund(sprechen)
        if config.WACH_AN:
            WACHHUND.starten()
    return WACHHUND
