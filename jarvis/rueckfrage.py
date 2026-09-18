"""Rückfragen an den Menschen - aus dem Gespräch heraus oder aus einem Agenten.

Zwei Arten, wie vorgegeben:

  FRAGE        mehrere Vorschläge zur Auswahl, dazu immer die Möglichkeit,
               etwas Eigenes zu schreiben.
  GENEHMIGUNG  etwas Folgenreiches steht an. Es wird genau gezeigt, was
               passieren würde und was das bedeutet - erlauben oder ablehnen.

Der fragende Faden hält an, bis jemand antwortet. Das ist Absicht: ein Agent,
der eine Genehmigung braucht, soll warten, nicht raten. Antwortet niemand,
gilt nach einer Weile die sichere Seite - bei Genehmigungen also "nein".

Kostet nichts: ein Wörterbuch und ein Warteereignis pro offener Frage, kein
eigener Faden, keine Schleife im Hintergrund.
"""
from __future__ import annotations

import itertools
import threading
import time

from . import config

FRAGE = "frage"
GENEHMIGUNG = "genehmigung"

_zaehler = itertools.count(1)
_schloss = threading.Lock()
_offen: dict[str, dict] = {}

# Wird von der Oberfläche gesetzt, damit eine neue Frage auffällt
melder = None


class Rueckfrage:
    def __init__(self, art: str, text: str, optionen: list[str],
                 auswirkungen: str = "", von: str = "Jarvis",
                 zeitlimit: float = 0) -> None:
        self.id = f"rf{next(_zaehler)}"
        self.art = art
        self.text = text.strip()
        self.optionen = optionen
        self.auswirkungen = auswirkungen.strip()
        self.von = von
        self.zeitlimit = zeitlimit or config.RUECKFRAGE_ZEITLIMIT
        self.gestellt = time.monotonic()
        self.antwort: str | None = None
        self._da = threading.Event()

    @property
    def rest(self) -> float:
        return max(0.0, self.zeitlimit - (time.monotonic() - self.gestellt))

    def als_dict(self) -> dict:
        return {"id": self.id, "art": self.art, "text": self.text,
                "optionen": self.optionen, "auswirkungen": self.auswirkungen,
                "von": self.von, "rest": round(self.rest),
                "zeitlimit": self.zeitlimit}

    def beantworten(self, antwort: str) -> None:
        self.antwort = antwort
        self._da.set()

    def warten(self) -> str:
        """Blockiert, bis geantwortet wird oder die Zeit ablaeuft."""
        if self._da.wait(self.zeitlimit):
            return self.antwort or ""
        return ""          # nichts gehoert - der Aufrufer entscheidet sicher


def _eintragen(frage: Rueckfrage) -> None:
    with _schloss:
        _offen[frage.id] = {"frage": frage}
    if melder:
        try:
            melder(frage)
        except Exception:
            pass


def _austragen(frage: Rueckfrage) -> None:
    with _schloss:
        _offen.pop(frage.id, None)


def stellen(text: str, optionen: list[str] | None = None,
            von: str = "Jarvis") -> str:
    """Eine Auswahlfrage. Gibt die Antwort zurueck - Vorschlag oder Eigenes."""
    frage = Rueckfrage(FRAGE, text, list(optionen or [])[:3], von=von)
    _eintragen(frage)
    try:
        return frage.warten()
    finally:
        _austragen(frage)


def genehmigen(was: str, auswirkungen: str = "", von: str = "Jarvis") -> bool:
    """Eine Freigabe. Ohne Antwort gilt Ablehnung - das ist die sichere Seite."""
    frage = Rueckfrage(GENEHMIGUNG, was, ["Einmal erlauben", "Ablehnen"],
                       auswirkungen=auswirkungen, von=von)
    _eintragen(frage)
    try:
        return frage.warten().strip().lower().startswith("einmal")
    finally:
        _austragen(frage)


def offene() -> list[Rueckfrage]:
    with _schloss:
        return [e["frage"] for e in _offen.values()]


def beantworten(frage_id: str, antwort: str) -> bool:
    with _schloss:
        eintrag = _offen.get(frage_id)
    if eintrag is None:
        return False
    eintrag["frage"].beantworten(antwort)
    return True
