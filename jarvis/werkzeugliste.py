"""Änderungen an den Werkzeugen, die über die Oberfläche gemacht werden.

Der Code der Werkzeuge bleibt unangetastet. Hier liegt nur, was jemand daran
verstellt hat: abgeschaltet, andere Beschreibung, andere Standardwerte. Das
steht in werkzeuge.json und überlebt einen Neustart.

Warum die Beschreibung wichtig ist: Das Modell entscheidet allein anhand
dieses Textes, wann es ein Werkzeug wählt. Wer ihn ändert, ändert das
Verhalten - ohne eine Zeile Code.
"""
from __future__ import annotations

import copy
import json
import threading

from . import config

DATEI = config.ROOT / "werkzeuge.json"
_schloss = threading.Lock()
_aenderungen: dict = {}


def laden() -> dict:
    global _aenderungen
    with _schloss:
        if DATEI.exists():
            try:
                _aenderungen = json.loads(DATEI.read_text(encoding="utf-8"))
            except Exception:
                _aenderungen = {}
        return copy.deepcopy(_aenderungen)


def speichern(neu: dict) -> None:
    global _aenderungen
    with _schloss:
        _aenderungen = neu
        DATEI.write_text(json.dumps(neu, ensure_ascii=False, indent=2),
                         encoding="utf-8")


def aendern(name: str, feld: str, wert) -> None:
    daten = laden()
    daten.setdefault(name, {})[feld] = wert
    speichern(daten)


def ist_aktiv(name: str) -> bool:
    return laden().get(name, {}).get("aktiv", True)


def anwenden(schema: list[dict]) -> list[dict]:
    """Nimmt das Grundschema und baut daraus das, was das Modell sieht."""
    daten = laden()
    ergebnis = []
    for eintrag in schema:
        fn = eintrag["function"]
        name = fn["name"]
        aenderung = daten.get(name, {})
        if not aenderung.get("aktiv", True):
            continue                       # abgeschaltet: taucht gar nicht auf

        kopie = copy.deepcopy(eintrag)
        kfn = kopie["function"]
        if aenderung.get("beschreibung"):
            kfn["description"] = aenderung["beschreibung"]

        for pname, pwerte in (aenderung.get("parameter") or {}).items():
            ziel = kfn["parameters"]["properties"].get(pname)
            if ziel is None:
                continue
            if pwerte.get("beschreibung"):
                ziel["description"] = pwerte["beschreibung"]
        ergebnis.append(kopie)
    return ergebnis


def standardwerte(name: str) -> dict:
    """Vorgaben, die vor dem Aufruf in die Argumente gefuellt werden."""
    aenderung = laden().get(name, {})
    werte = {}
    for pname, pwerte in (aenderung.get("parameter") or {}).items():
        if pwerte.get("standard") not in (None, ""):
            werte[pname] = pwerte["standard"]
    return werte


def uebersicht(grundschema: list[dict]) -> list[dict]:
    """Alles, was die Oberflaeche ueber die Werkzeuge wissen muss."""
    daten = laden()
    liste = []
    for eintrag in grundschema:
        fn = eintrag["function"]
        name = fn["name"]
        aenderung = daten.get(name, {})
        parameter = []
        for pname, pwerte in fn["parameters"]["properties"].items():
            geaendert = (aenderung.get("parameter") or {}).get(pname, {})
            parameter.append({
                "name": pname,
                "typ": pwerte.get("type", "string"),
                "beschreibung": geaendert.get("beschreibung")
                                or pwerte.get("description", ""),
                "original": pwerte.get("description", ""),
                "standard": geaendert.get("standard", ""),
                "pflicht": pname in fn["parameters"].get("required", []),
            })
        liste.append({
            "name": name,
            "aktiv": aenderung.get("aktiv", True),
            "beschreibung": aenderung.get("beschreibung") or fn["description"],
            "original": fn["description"],
            "geaendert": bool(aenderung),
            "parameter": parameter,
        })
    return liste


def zuruecksetzen(name: str = "") -> None:
    if not name:
        speichern({})
        return
    daten = laden()
    daten.pop(name, None)
    speichern(daten)
