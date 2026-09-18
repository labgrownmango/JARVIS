""""Hey Jarvis" - am Rechner, nicht im Browser.

Das Weckwort lief bisher nur, wenn Jarvis im Terminalfenster mit --weckwort
gestartet wurde. Wer die Weboberflaeche benutzt - also im Alltag jeder -,
bekam auf "Hey Jarvis" nichts, und es stand nirgends warum. Das Mikrofon des
BROWSERS hilft dabei nicht: es gibt es ueber http:// gar nicht, und selbst
mit HTTPS waere es das Mikrofon des Handys, nicht das des Rechners.

Also hoert der Server selbst zu, mit dem Mikrofon, das am Rechner haengt:

    Weckwort erkannt  ->  aufnehmen bis es still wird  ->  verstehen
                      ->  Jarvis fragen               ->  laut antworten

Das laeuft vollstaendig hier, ohne Browser. Die Oberflaeche sieht davon nur
das Ergebnis im Verlauf - man kann also am Schreibtisch reden und spaeter am
Handy nachlesen, was gesagt wurde.

Aus ist es, bis es jemand einschaltet (JARVIS_WECKWORT=1). Ein Programm, das
ungefragt dauerhaft mithoert, schaltet man bewusst ein.
"""
from __future__ import annotations

import threading
import time

from . import config, protokoll

_wecker = None
_laeuft = False
_schloss = threading.Lock()
_zustand = {"an": False, "grund": "nicht gestartet", "treffer": 0,
            "zuletzt": 0.0, "geraet": ""}

# Was gerade ankommt. Ohne das ist "Weckwort bereit" eine Behauptung:
# es stand im Protokoll, waehrend niemand wusste, ob ueberhaupt Ton
# hereinkommt - und ein stummes Mikrofon sah genauso aus wie ein gutes.
_pegel = {"jetzt": 0.0, "spitze": 0.0, "spitze_seit": 0.0,
          "naehe": 0.0, "beste_naehe": 0.0, "bloecke": 0}


def _pegel_merken(lautstaerke: float, naehe: float) -> None:
    _pegel["jetzt"] = lautstaerke
    _pegel["naehe"] = naehe
    _pegel["bloecke"] += 1
    # Die Spitze verfaellt nach ein paar Sekunden - sonst steht dort fuer
    # immer der eine Huster von vorhin und sagt nichts mehr ueber jetzt.
    jetzt = time.time()
    if lautstaerke > _pegel["spitze"] or jetzt - _pegel["spitze_seit"] > 4:
        _pegel["spitze"] = lautstaerke
        _pegel["spitze_seit"] = jetzt
    _pegel["beste_naehe"] = max(_pegel["beste_naehe"], naehe)


def zustand() -> dict:
    lage = dict(_zustand)
    lage["pegel"] = dict(_pegel)
    lage["schwelle"] = config.WECKWORT_SCHWELLE
    lage["wort"] = config.WECKWORT.replace("_", " ")
    return lage


def mikrofone() -> list[dict]:
    """Alle Eingabegeraete - mit der Angabe, welches gerade benutzt wird."""
    try:
        import sounddevice as sd
    except Exception as exc:
        return [{"fehler": f"{type(exc).__name__}: {exc}"}]
    try:
        geraete = sd.query_devices()
        standard = sd.default.device[0]
    except Exception as exc:
        return [{"fehler": f"{type(exc).__name__}: {exc}"}]

    gewaehlt = config.MIKROFON
    liste = []
    for nummer, g in enumerate(geraete):
        if g["max_input_channels"] <= 0:
            continue
        benutzt = (nummer == gewaehlt if isinstance(gewaehlt, int)
                   else (bool(gewaehlt) and gewaehlt.lower() in g["name"].lower())
                   if gewaehlt else nummer == standard)
        liste.append({"nummer": nummer, "name": g["name"],
                      "kanaele": g["max_input_channels"], "benutzt": benutzt})
    return liste


def _antworten(gehirn_holen, sprecher, ohren) -> None:
    """Einmal zuhoeren, fragen, antworten."""
    from . import tools

    _zustand["treffer"] += 1
    _zustand["zuletzt"] = time.time()
    protokoll.schreibe("system", "Weckwort erkannt - hoert zu")

    try:
        gesagt = ohren.listen()
    except Exception as exc:
        protokoll.schreibe("fehler", f"Mikrofon: {type(exc).__name__}: {exc}")
        return
    gesagt = (gesagt or "").strip()
    if not gesagt:
        protokoll.schreibe("system", "nichts verstanden")
        return

    protokoll.schreibe("du", gesagt)
    brain = gehirn_holen()
    tools.anfrage_beginnt()
    try:
        # Wird gleich vorgelesen - also knapp und ohne Markdown-Zeichen.
        antwort = brain.ask(gesagt, gesprochen=True)
    except Exception as exc:
        protokoll.schreibe("fehler", f"{type(exc).__name__}: {exc}")
        return
    if antwort:
        protokoll.schreibe("jarvis", antwort)
        try:
            sprecher.say(antwort)
        except Exception:
            pass


def starten(gehirn_holen) -> tuple[bool, str]:
    """Das Weckwort im Hintergrund scharf machen.

    Gibt (lief_an, Grund) zurueck. Der Grund wird gebraucht: "es tut nichts"
    ohne Erklaerung war genau das Problem.
    """
    global _wecker, _laeuft

    with _schloss:
        if _laeuft:
            return True, "laeuft bereits"
        if not config.WECKWORT_AN:
            _zustand["grund"] = ("abgeschaltet - einschalten mit "
                                 "JARVIS_WECKWORT=1 in der .env")
            return False, _zustand["grund"]

        from . import weckwort as ww

        geht, grund = ww.verfuegbar()
        if not geht:
            _zustand["grund"] = grund
            protokoll.schreibe("fehler", f"Weckwort: {grund}")
            return False, grund

        from .voice import make_speaker, try_make_ears

        ohren = try_make_ears()
        if ohren is None:
            grund = ("die Spracherkennung fehlt - ohne sie nuetzt das "
                     "Weckwort nichts")
            _zustand["grund"] = grund
            protokoll.schreibe("fehler", f"Weckwort: {grund}")
            return False, grund

        # Eine eigene Stimme, nicht die stumme des Webservers: hier soll es
        # wirklich aus dem Lautsprecher kommen. Im Browser wird derselbe Satz
        # nicht noch einmal gesprochen - er steht dort nur im Verlauf.
        sprecher = make_speaker()

        _wecker = ww.Weckwort()
        try:
            _wecker._laden()
        except Exception as exc:
            grund = f"Modell '{_wecker.wort}' laedt nicht: {exc}"
            _zustand["grund"] = grund
            protokoll.schreibe("fehler", f"Weckwort: {grund}")
            return False, grund

        def bei_treffer(_wert: float) -> None:
            # In einem eigenen Faden, damit das Horchen weiterlaeuft,
            # waehrend geantwortet wird.
            threading.Thread(
                target=_antworten, args=(gehirn_holen, sprecher, ohren),
                daemon=True, name="Weckwort-Antwort").start()

        _wecker.im_hintergrund(bei_treffer, _pegel_merken)
        _laeuft = True
        benutzt = [m for m in mikrofone() if m.get("benutzt")]
        _zustand.update({"an": True, "grund": "",
                         "geraet": benutzt[0]["name"] if benutzt else "?"})
        protokoll.schreibe(
            "system",
            f"Weckwort bereit - sag \"{_wecker.wort.replace('_', ' ')}\"")
        return True, ""


def anhalten() -> None:
    global _laeuft
    with _schloss:
        if _wecker is not None:
            _wecker.anhalten()
        _laeuft = False
        _zustand.update({"an": False, "grund": "angehalten"})
