"""Mehrere Gespraeche nebeneinander - wie man es von Chat-Programmen kennt.

Vorher gab es genau einen durchlaufenden Faden. Das hatte zwei Haken: ein
neues Thema stand mitten im alten, und "loeschen" hiess entweder gar nichts
(nur das Arbeitsgedaechtnis war leer, das Archiv nicht) oder alles.

Ein Chat ist hier nur eine Kennung. Jede Aeusserung im Archiv traegt sie mit,
und die Oberflaeche zeigt immer genau einen Chat. Was frueher schon im Archiv
lag, traegt keine - das bekommt den Sammelchat "Frueher", damit nichts
verschwindet, bloss weil es diese Einteilung noch nicht gab.

Absichtlich KEINE zweite Wahrheit: die Nachrichten stehen weiterhin nur in
verlauf.jsonl. Hier stehen nur Titel und welcher Chat gerade offen ist. So
kann nichts auseinanderlaufen.
"""
from __future__ import annotations

import datetime as dt
import json
import threading

from . import config

DATEI = config.ROOT / "data" / "chats.json"
_schloss = threading.RLock()

# Alles, was vor dieser Einteilung entstand. Kein echter Eintrag traegt diese
# Kennung - sie wird beim Lesen fuer Eintraege ohne Chat eingesetzt.
FRUEHER = "frueher"

_stand: dict | None = None


def _laden() -> dict:
    global _stand
    with _schloss:
        if _stand is not None:
            return _stand
        try:
            _stand = json.loads(DATEI.read_text(encoding="utf-8"))
            if not isinstance(_stand, dict):
                raise ValueError
        except (OSError, ValueError):
            _stand = {}
        _stand.setdefault("chats", [])
        _stand.setdefault("aktiv", "")
        return _stand


def _speichern() -> None:
    with _schloss:
        DATEI.parent.mkdir(parents=True, exist_ok=True)
        DATEI.write_text(json.dumps(_laden(), ensure_ascii=False, indent=2),
                         encoding="utf-8")


def _jetzt() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def neu(titel: str = "") -> str:
    """Legt einen Chat an und macht ihn zum aktiven. Gibt die Kennung zurueck."""
    with _schloss:
        stand = _laden()
        kennung = f"chat-{dt.datetime.now():%Y%m%d-%H%M%S}"
        # Zwei Chats in derselben Sekunde: anhaengen statt ueberschreiben
        vorhandene = {c["id"] for c in stand["chats"]}
        grund, zaehler = kennung, 2
        while kennung in vorhandene:
            kennung = f"{grund}-{zaehler}"
            zaehler += 1
        stand["chats"].append({"id": kennung, "titel": titel.strip(),
                               "erstellt": _jetzt(), "zuletzt": _jetzt()})
        stand["aktiv"] = kennung
        _speichern()
        return kennung


def aktiver(anlegen: bool = True) -> str:
    """Welcher Chat ist offen? Gibt es keinen, wird nur bei anlegen=True einer angelegt."""
    with _schloss:
        stand = _laden()
        kennung = stand.get("aktiv") or ""
        if kennung and any(c["id"] == kennung for c in stand["chats"]):
            return kennung
        if stand["chats"]:
            stand["aktiv"] = stand["chats"][0]["id"]
            _speichern()
            return stand["aktiv"]
        if not anlegen:
            return ""
        return neu()


def wechseln(kennung: str) -> bool:
    with _schloss:
        stand = _laden()
        if kennung != FRUEHER and not any(c["id"] == kennung
                                          for c in stand["chats"]):
            return False
        stand["aktiv"] = kennung
        _speichern()
        return True


def umbenennen(kennung: str, titel: str) -> bool:
    with _schloss:
        for chat in _laden()["chats"]:
            if chat["id"] == kennung:
                chat["titel"] = titel.strip()[:60]
                _speichern()
                return True
        return False


def beruehren(kennung: str, erster_satz: str = "") -> None:
    """Merkt, dass in diesem Chat gerade geredet wurde.

    Und gibt ihm beim ersten Mal einen Titel - aus dem, was gesagt wurde.
    Selbst benannte Chats bleiben unangetastet.
    """
    with _schloss:
        for chat in _laden()["chats"]:
            if chat["id"] != kennung:
                continue
            chat["zuletzt"] = _jetzt()
            if not chat.get("titel") and erster_satz.strip():
                chat["titel"] = _titel_aus(erster_satz)
            _speichern()
            return


def _titel_aus(satz: str) -> str:
    """Eine knappe Ueberschrift aus dem ersten Satz.

    Am Satzende abschneiden liest sich besser als mitten im Wort. Bleibt
    davon zu wenig uebrig, wird stattdessen nach Woertern gekuerzt.
    """
    sauber = " ".join(satz.split())
    for zeichen in ".?!":
        stelle = sauber.find(zeichen)
        if 12 <= stelle <= 60:
            return sauber[:stelle + 1]
    if len(sauber) <= 60:
        return sauber
    gekuerzt = sauber[:60].rsplit(" ", 1)[0]
    return (gekuerzt or sauber[:60]) + " ..."


def loeschen(kennung: str) -> int:
    """Chat und seine Nachrichten weg. Gibt zurueck, wie viele geloescht wurden.

    Der Sammelchat "Frueher" laesst sich ebenfalls loeschen - dann sind die
    Eintraege ohne Kennung gemeint.
    """
    from . import verlauf

    with _schloss:
        stand = _laden()
        weg = verlauf.chat_loeschen(kennung)
        stand["chats"] = [c for c in stand["chats"] if c["id"] != kennung]
        if stand.get("aktiv") == kennung:
            stand["aktiv"] = stand["chats"][0]["id"] if stand["chats"] else ""
        _speichern()
        return weg


def liste() -> list[dict]:
    """Alle Chats, das zuletzt benutzte zuerst - samt Anzahl der Nachrichten."""
    from . import verlauf

    with _schloss:
        stand = _laden()
        gezaehlt = verlauf.zaehlen_je_chat()
        eintraege = []
        for chat in stand["chats"]:
            anzahl = gezaehlt.get(chat["id"], 0)
            eintraege.append({**chat, "anzahl": anzahl,
                              "aktiv": chat["id"] == stand.get("aktiv")})
        # Was vor dieser Einteilung entstand, soll auffindbar bleiben - aber
        # unten stehen, nicht oben.
        alt = gezaehlt.get(FRUEHER, 0)
        eintraege.sort(key=lambda c: c.get("zuletzt", ""), reverse=True)
        if alt:
            eintraege.append({"id": FRUEHER, "titel": "Frueher",
                              "erstellt": "", "zuletzt": "", "anzahl": alt,
                              "aktiv": stand.get("aktiv") == FRUEHER})
        return eintraege
