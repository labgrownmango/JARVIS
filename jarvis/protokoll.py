"""Ein Protokoll der Sitzung: was Jarvis getan hat, in der Reihenfolge.

Absichtlich ein Ringpuffer im Arbeitsspeicher statt einer Datei - nach einer
langen Sitzung soll nichts vollaufen, und nach dem Beenden ist es weg.
Wer es dauerhaft will, schaltet SCHREIBEN ein.
"""
from __future__ import annotations

import threading
import time
from collections import deque

from . import config

GROESSE = 500                     # so viele Eintraege werden behalten
_eintraege: deque = deque(maxlen=GROESSE)
_schloss = threading.Lock()
_nummer = 0

# Art -> wie es in der Oberflaeche eingefaerbt wird
ARTEN = ("du", "jarvis", "werkzeug", "agent", "modell", "fehler", "system")


def schreibe(art: str, text: str, zusatz: dict | None = None) -> dict:
    """Einen Eintrag anlegen. Gibt ihn zurueck, damit er direkt verschickt
    werden kann."""
    global _nummer
    with _schloss:
        _nummer += 1
        eintrag = {
            "nr": _nummer,
            "zeit": time.strftime("%H:%M:%S"),
            "art": art if art in ARTEN else "system",
            "text": str(text),
            **(zusatz or {}),
        }
        _eintraege.append(eintrag)
    if config.PROTOKOLL_DATEI:
        try:
            with open(config.PROTOKOLL_DATEI, "a", encoding="utf-8") as fh:
                fh.write(f"{eintrag['zeit']} [{eintrag['art']}] "
                         f"{eintrag['text']}\n")
        except Exception:
            pass
    return eintrag


def alle(ab_nummer: int = 0) -> list[dict]:
    with _schloss:
        return [e for e in _eintraege if e["nr"] > ab_nummer]


def leeren() -> int:
    with _schloss:
        anzahl = len(_eintraege)
        _eintraege.clear()
    return anzahl


def letzte_nummer() -> int:
    return _nummer
