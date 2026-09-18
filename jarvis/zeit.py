"""Zeitbezug: Erinnerungen, Leerlauf und die Frage, wie lange etwas her ist.

Der Leerlauf kommt von Windows selbst - GetLastInputInfo sagt auf die
Millisekunde genau, wann zuletzt eine Taste gedrueckt oder die Maus bewegt
wurde. Das muss niemand alle zehn Minuten abfragen und mitschreiben; der
Wert liegt fertig da und kostet nichts.
"""
from __future__ import annotations

import ctypes
import datetime as dt
import json
import threading
import time

from . import config

DATEI = config.ROOT / "data" / "erinnerungen.json"
_schloss = threading.Lock()
_wecker: threading.Thread | None = None
_sprecher = None          # wird von main/web gesetzt: womit geweckt wird


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_ulong)]


def leerlauf_sekunden() -> float:
    """Wie lange niemand mehr Maus oder Tastatur angefasst hat."""
    try:
        info = _LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(info)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return 0.0
        jetzt = ctypes.windll.kernel32.GetTickCount()
        return max(0.0, (jetzt - info.dwTime) / 1000.0)
    except Exception:
        return 0.0


def leerlauf_text() -> str:
    sekunden = leerlauf_sekunden()
    if sekunden < 90:
        return "gerade aktiv"
    minuten = int(sekunden // 60)
    if minuten < 60:
        return f"seit {minuten} Minuten nichts mehr angefasst"
    stunden = minuten // 60
    return (f"seit {stunden} Stunden {minuten % 60} Minuten "
            f"nichts mehr angefasst")


def tageszeit() -> str:
    stunde = dt.datetime.now().hour
    if stunde < 5:
        return "nacht"
    if stunde < 11:
        return "morgen"
    if stunde < 14:
        return "mittag"
    if stunde < 18:
        return "nachmittag"
    if stunde < 22:
        return "abend"
    return "spaetabend"


GRUSS = {
    "nacht": "Noch wach, {name}?",
    "morgen": "Guten Morgen, {name}.",
    "mittag": "Mahlzeit, {name}.",
    "nachmittag": "Guten Tag, {name}.",
    "abend": "Guten Abend, {name}.",
    "spaetabend": "Guten Abend, {name}.",
}


def begruessung(name: str = "") -> str:
    """Ein Gruss, der zur Lage passt.

    Nachts nach langer Pause klingt anders als morgens um neun. Die Regel
    stammt aus dem Film: Jarvis sagt nicht "Hallo", er stellt fest, wie spaet
    es ist und wie lange jemand weg war.
    """
    name = name or config.USER_NAME
    zeitpunkt = tageszeit()
    leer = leerlauf_sekunden()
    stunde = dt.datetime.now().hour

    # Nach Mitternacht und lange nichts angefasst: da war jemand nicht am Platz
    if zeitpunkt == "nacht" and leer > 2 * 3600:
        stunden = int(leer // 3600)
        return (f"Es ist {dt.datetime.now().strftime('%H:%M')} Uhr, {name}. "
                f"Der Rechner stand {stunden} Stunden still - "
                f"Sie sollten schlafen.")
    if zeitpunkt == "nacht":
        return f"Es ist nach Mitternacht, {name}. Noch wach?"

    if leer > 4 * 3600:
        return (f"{GRUSS[zeitpunkt].format(name=name)} "
                f"Willkommen zurueck - hier war {int(leer // 3600)} Stunden "
                f"lang niemand.")
    if leer > 45 * 60:
        return (f"{GRUSS[zeitpunkt].format(name=name)} "
                f"Sie waren {int(leer // 60)} Minuten weg.")
    return GRUSS[zeitpunkt].format(name=name)


def begruessung_mit_lage(name: str = "") -> str:
    """Gruss plus das, was gerade erwaehnenswert ist - kurz gehalten."""
    teile = [begruessung(name)]

    offen = offene()
    if offen:
        naechste = min(offen,
                       key=lambda e: dt.datetime.fromisoformat(e["faellig"]))
        wann = dt.datetime.fromisoformat(naechste["faellig"])
        teile.append(f"Eine Erinnerung steht an: {naechste['text']} um "
                     f"{wann.strftime('%H:%M')}.")
    return " ".join(teile)


# --- Erinnerungen -----------------------------------------------------------
def _laden() -> list[dict]:
    if not DATEI.exists():
        return []
    try:
        return json.loads(DATEI.read_text(encoding="utf-8"))
    except Exception:
        return []


def _speichern(liste: list[dict]) -> None:
    DATEI.parent.mkdir(parents=True, exist_ok=True)
    DATEI.write_text(json.dumps(liste, ensure_ascii=False, indent=2),
                     encoding="utf-8")


def setzen(text: str, in_minuten: float = 0, um: str = "") -> dict:
    """Eine Erinnerung anlegen - entweder in X Minuten oder zu einer Uhrzeit."""
    jetzt = dt.datetime.now()
    if um.strip():
        teile = um.strip().replace(".", ":").split(":")
        stunde = int(teile[0])
        minute = int(teile[1]) if len(teile) > 1 else 0
        faellig = jetzt.replace(hour=stunde, minute=minute, second=0,
                                microsecond=0)
        if faellig <= jetzt:                  # heute schon vorbei: morgen
            faellig += dt.timedelta(days=1)
    else:
        faellig = jetzt + dt.timedelta(minutes=max(0.1, float(in_minuten or 5)))

    eintrag = {"text": text.strip(), "faellig": faellig.isoformat(timespec="seconds"),
               "gesetzt": jetzt.isoformat(timespec="seconds")}
    with _schloss:
        liste = _laden()
        liste.append(eintrag)
        _speichern(liste)
    wecker_starten()
    return eintrag


def offene() -> list[dict]:
    jetzt = dt.datetime.now()
    return [e for e in _laden()
            if dt.datetime.fromisoformat(e["faellig"]) > jetzt]


def streichen(suche: str = "") -> int:
    with _schloss:
        liste = _laden()
        if not suche.strip():
            _speichern([])
            return len(liste)
        bleiben = [e for e in liste if suche.lower() not in e["text"].lower()]
        _speichern(bleiben)
        return len(liste) - len(bleiben)


def _faellige_einsammeln() -> list[dict]:
    jetzt = dt.datetime.now()
    with _schloss:
        liste = _laden()
        faellig = [e for e in liste
                   if dt.datetime.fromisoformat(e["faellig"]) <= jetzt]
        if faellig:
            _speichern([e for e in liste if e not in faellig])
    return faellig


def _wecken() -> None:
    while True:
        for eintrag in _faellige_einsammeln():
            text = f"Erinnerung, {config.USER_NAME}: {eintrag['text']}"
            print(f"\n  [{text}]")
            if _sprecher is not None:
                try:
                    _sprecher(text)
                except Exception:
                    pass
        if not _laden():
            return                      # nichts mehr offen, Wecker schlaeft ein
        time.sleep(10)


def wecker_starten(sprecher=None) -> None:
    global _wecker, _sprecher
    if sprecher is not None:
        _sprecher = sprecher
    if _wecker and _wecker.is_alive():
        return
    if not _laden():
        return
    _wecker = threading.Thread(target=_wecken, daemon=True, name="Wecker")
    _wecker.start()
