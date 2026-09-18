"""Das Langzeitgedächtnis - es überlebt das Beenden.

Jeder Eintrag trägt sein Datum, und beim Abruf steht dabei, wie lange das her
ist. Ohne das wäre "du wolltest die Festplatte aufräumen" wertlos: vorgestern
gesagt heißt etwas anderes als vor vier Monaten.

Ein Auszug wird bei jedem Start in Jarvis' Systemprompt gelegt. Nur so weiss
er von sich aus, wen er vor sich hat - statt darauf zu warten, dass jemand
"erinnerst du dich" fragt.
"""
from __future__ import annotations

import datetime as dt
import json
import threading

from . import config

DATEI = config.ROOT / "data" / "gedaechtnis.jsonl"
_schloss = threading.Lock()

# Wofuer ein Eintrag gut ist. Steuert, was in den Systemprompt wandert.
ARTEN = {
    "herkunft": "wer Jarvis ist - unveränderlich",
    "person": "über {name} selbst",
    "vorliebe": "wie es {name} haben will",
    "vorhaben": "was ansteht",
    "fakt": "Sonstiges",
}

# Diese Art wird von vergessen() nicht angefasst. Sie steht fuer das, was
# Jarvis ueber sich selbst weiss - festgelegt von seinem Entwickler, nicht
# im Gespraech entstanden und deshalb auch nicht im Gespraech loeschbar.
# Ein "vergiss alles ueber dich" soll ihn nicht zu einem Textgenerator ohne
# Herkunft machen.
UNVERGESSLICH = "herkunft"


def _jetzt() -> dt.datetime:
    return dt.datetime.now()


def wie_lange_her(wann: dt.datetime) -> str:
    """"vor drei Tagen" statt "2026-09-09T14:22:01"."""
    tage = (_jetzt().date() - wann.date()).days
    if tage == 0:
        stunden = int((_jetzt() - wann).total_seconds() // 3600)
        if stunden < 1:
            return "gerade eben"
        return f"heute vor {stunden} Stunden" if stunden > 1 else "vor einer Stunde"
    if tage == 1:
        return "gestern"
    if tage == 2:
        return "vorgestern"
    if tage < 7:
        return f"vor {tage} Tagen"
    if tage < 14:
        return "vor einer Woche"
    if tage < 60:
        return f"vor {tage // 7} Wochen"
    if tage < 365:
        return f"vor {tage // 30} Monaten"
    jahre = tage // 365
    return "vor einem Jahr" if jahre == 1 else f"vor {jahre} Jahren"


def merken(text: str, art: str = "fakt") -> dict:
    eintrag = {
        "zeit": _jetzt().isoformat(timespec="seconds"),
        "art": art if art in ARTEN else "fakt",
        "text": text.strip(),
    }
    with _schloss:
        DATEI.parent.mkdir(parents=True, exist_ok=True)
        with DATEI.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(eintrag, ensure_ascii=False) + "\n")
    return eintrag


def alle() -> list[dict]:
    if not DATEI.exists():
        return []
    eintraege = []
    with _schloss:
        for zeile in DATEI.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(zeile)
                e["wann"] = dt.datetime.fromisoformat(e["zeit"])
                eintraege.append(e)
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
    return eintraege


def suchen(frage: str = "", grenze: int = 12) -> list[dict]:
    frage = frage.strip().lower()
    treffer = [e for e in alle() if not frage or frage in e["text"].lower()]
    return treffer[-grenze:]


def vergessen(frage: str) -> int:
    """Entfernt Eintraege, die dazu passen. Gibt die Anzahl zurueck.

    Was Jarvis ueber sich selbst weiss, bleibt dabei stehen. Das ist keine
    Erinnerung aus einem Gespraech, sondern seine Herkunft - festgelegt von
    seinem Entwickler. Ein "vergiss alles" soll ihn nicht in einen
    Textgenerator ohne Vergangenheit zurueckverwandeln.
    """
    frage = frage.strip().lower()
    if not frage:
        return 0
    bleiben = [e for e in alle()
               if frage not in e["text"].lower()
               or e["art"] == UNVERGESSLICH]
    weg = len(alle()) - len(bleiben)
    with _schloss:
        with DATEI.open("w", encoding="utf-8") as fh:
            for e in bleiben:
                fh.write(json.dumps({"zeit": e["zeit"], "art": e["art"],
                                     "text": e["text"]}, ensure_ascii=False) + "\n")
    return weg


def fuer_systemprompt(grenze: int = 18) -> str:
    """Was Jarvis von Anfang an über {USER_NAME} wissen soll.

    Dauerhaftes zuerst (wer jemand ist, wie er Dinge mag), dann das Neueste.
    Bewusst knapp: das steht bei JEDER Anfrage im Prompt und kostet jedes Mal
    Tokens und Zeit.
    """
    eintraege = [e for e in alle() if e["art"] != UNVERGESSLICH]
    # Die Herkunft steht schon fest im Systemprompt - sie hier noch einmal
    # anzuhaengen waere doppelt und wuerde bei jeder Anfrage Platz kosten.
    if not eintraege:
        return ""

    wichtig = [e for e in eintraege if e["art"] in ("person", "vorliebe")]
    rest = [e for e in eintraege if e["art"] not in ("person", "vorliebe")]
    auswahl = wichtig[-(grenze // 2):] + rest[-(grenze - len(wichtig[-(grenze // 2):])):]

    zeilen = [f"- {e['text']} ({wie_lange_her(e['wann'])})" for e in auswahl]
    return ("Was du über {name} weisst - aus frueheren Gespraechen:\n"
            + "\n".join(zeilen))
