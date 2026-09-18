"""Das Gesprächsarchiv - damit ein Neustart nicht alles vergisst.

Zwei Schichten, aus einem Grund: Der ganze Verlauf in den Systemprompt zu
legen wäre teuer und würde mit jedem Tag teurer. Deshalb:

  1. ALLES landet auf der Platte. Durchsuchbar, mit Datum.
  2. Nur eine Zeile davon steht beim Start im Prompt - wann zuletzt geredet
     wurde und worum es ging. Genug, damit Jarvis anknüpfen kann.

Wer mehr wissen will, fragt: "worüber haben wir gestern geredet?" Dann sucht
er im Archiv. Das kostet nur, wenn es gebraucht wird.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import threading
import time

from . import config

DATEI = config.ROOT / "data" / "verlauf.jsonl"
_schloss = threading.Lock()

# Eine Kennung pro Programmlauf - damit sich Sitzungen trennen lassen
SITZUNG = f"{dt.datetime.now():%Y%m%d-%H%M%S}-{os.getpid()}"


def schreiben(rolle: str, text: str, modell: str = "") -> None:
    """Eine Äußerung festhalten. rolle: du | jarvis

    'modell' nur bei Jarvis-Antworten. Anlass: die Modellwahl steht auf
    "reihenfolge", vier Modelle stehen zur Wahl, und bei Belegung wird
    mitten im Betrieb gewechselt. Welches geantwortet hat, stand hinterher
    NIRGENDS - und ohne diese Angabe liess sich nicht entscheiden, ob eine
    seltsame Antwort am Prompt lag oder am Modell. Gemeldet von Mini-Jost,
    wo dieselbe Frage einmal knapp und einmal gegliedert zurueckkam.
    """
    from . import chats

    text = (text or "").strip()
    if not text or not config.ARCHIV_AN:
        return
    kennung = chats.aktiver()
    eintrag = {"zeit": dt.datetime.now().isoformat(timespec="seconds"),
               "sitzung": SITZUNG, "chat": kennung, "rolle": rolle,
               "text": text[:config.VERLAUF_MAX_ZEICHEN]}
    if modell:
        eintrag["modell"] = modell
    with _schloss:
        DATEI.parent.mkdir(parents=True, exist_ok=True)
        with DATEI.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(eintrag, ensure_ascii=False) + "\n")
    # Der Titel entsteht aus der ersten Frage - nicht aus Jarvis' Antwort,
    # die faengt gern mit "Sir," an und saehe in der Liste bei jedem Chat
    # gleich aus.
    chats.beruehren(kennung, text if rolle == "du" else "")


def _lesen() -> list[dict]:
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


def _chat_von(eintrag: dict) -> str:
    """Zu welchem Chat gehoert der Eintrag?

    Alles aus der Zeit vor den Chats traegt keine Kennung. Das verschwindet
    nicht, sondern sammelt sich unter einer eigenen.
    """
    from . import chats

    return eintrag.get("chat") or chats.FRUEHER


def letzte(anzahl: int = 30, chat: str = "") -> list[dict]:
    """Die juengsten Aeusserungen, aelteste zuerst - fuer die Oberflaeche.

    Ohne das startet die Weboberflaeche bei jedem Aufruf leer, waehrend
    Jarvis sich sehr wohl erinnert. Am Handy sieht man dann ein leeres Fenster
    und bekommt Antworten auf ein Gespraech, das man nicht sieht.

    Ohne chat wird der gerade offene genommen - die Oberflaeche zeigt immer
    genau einen, nie zwei durcheinander.
    """
    from . import chats

    kennung = chat or chats.aktiver()
    anzahl = max(1, min(int(anzahl or 30), 200))
    eintraege = [e for e in _lesen() if _chat_von(e) == kennung][-anzahl:]
    return [{"rolle": e["rolle"], "text": e["text"], "zeit": e["zeit"],
             "sitzung": e.get("sitzung", ""), "chat": _chat_von(e)}
            for e in eintraege]


def zaehlen_je_chat() -> dict[str, int]:
    gezaehlt: dict[str, int] = {}
    for e in _lesen():
        kennung = _chat_von(e)
        gezaehlt[kennung] = gezaehlt.get(kennung, 0) + 1
    return gezaehlt


PAPIERKORB = config.ROOT / "data" / "geloescht.jsonl"


def chat_loeschen(kennung: str) -> int:
    """Alle Nachrichten eines Chats wegwerfen. Gibt die Anzahl zurueck.

    "Wegwerfen" heisst hier: aus dem Archiv heraus und nach
    data/geloescht.jsonl hinein. Ein Gespraech ist gewachsen, nicht erzeugt -
    ein Fehlklick darf es nicht endgueltig vernichten. Die Datei wird von
    nichts gelesen und faellt niemandem auf; sie ist nur da, wenn jemand sie
    braucht.

    Nicht theoretisch: beim Testen dieser Funktion sind 375 echte Nachrichten
    verschwunden, und sie kamen nur zurueck, weil zufaellig eine ausgepackte
    Sicherung herumlag.
    """
    alle = _lesen()
    bleiben, weg = [], []
    for e in alle:
        (weg if _chat_von(e) == kennung else bleiben).append(e)
    if not weg:
        return 0

    zeitpunkt = dt.datetime.now().isoformat(timespec="seconds")
    with _schloss:
        PAPIERKORB.parent.mkdir(parents=True, exist_ok=True)
        with PAPIERKORB.open("a", encoding="utf-8") as fh:
            for e in weg:
                fh.write(json.dumps(
                    {**{k: v for k, v in e.items() if k != "wann"},
                     "geloescht_am": zeitpunkt, "geloeschter_chat": kennung},
                    ensure_ascii=False) + "\n")
    _neu_schreiben(bleiben)
    return len(weg)


def papierkorb() -> list[dict]:
    """Was geloescht wurde - juengstes zuletzt."""
    if not PAPIERKORB.exists():
        return []
    eintraege = []
    for zeile in PAPIERKORB.read_text(encoding="utf-8").splitlines():
        try:
            eintraege.append(json.loads(zeile))
        except json.JSONDecodeError:
            continue
    return eintraege


def _neu_schreiben(eintraege: list[dict]) -> None:
    """Die Datei neu aufbauen - fuer Loeschen und Aufraeumen.

    Ueber eine Nebendatei, die erst am Ende an ihren Platz kommt: bricht der
    Rechner mitten im Schreiben ab, ist das Archiv sonst halb weg. Das
    "wann", das beim Lesen dazugerechnet wurde, faellt hier wieder heraus.
    """
    with _schloss:
        DATEI.parent.mkdir(parents=True, exist_ok=True)
        neben = DATEI.with_suffix(".jsonl.neu")
        with neben.open("w", encoding="utf-8") as fh:
            for e in eintraege:
                fh.write(json.dumps(
                    {k: v for k, v in e.items() if k != "wann"},
                    ensure_ascii=False) + "\n")
        neben.replace(DATEI)


def suchen(frage: str = "", tage: int = 0, grenze: int = 8) -> list[dict]:
    """Im Archiv nachsehen. tage=1 heisst: nur gestern und heute."""
    frage = frage.strip().lower()
    grenzdatum = (dt.datetime.now() - dt.timedelta(days=tage)) if tage else None
    treffer = []
    for e in _lesen():
        if grenzdatum and e["wann"] < grenzdatum:
            continue
        if frage and frage not in e["text"].lower():
            continue
        treffer.append(e)
    return treffer[-grenze:]


def suchen_nach_sinn(frage: str = "", tage: int = 0,
                     grenze: int = 8) -> tuple[list[dict], str]:
    """Wie suchen(), aber nach Bedeutung statt nach Buchstaben.

    Gibt (Treffer, Weg) zurueck - "Bedeutung" oder "Text". Der Weg gehoert
    in die Antwort: findet Jarvis etwas nur ueber die Textsuche, hat er
    moeglicherweise Passendes uebersehen, und das soll man wissen.

    Der Rueckfall ist Absicht. Das Einbettungsmodell ist ein freier Endpunkt
    im Netz - es kann belegt sein, und dann muss das Archiv trotzdem
    durchsuchbar bleiben. Schlechter suchen ist besser als nicht suchen.
    """
    if not frage.strip():
        return suchen("", tage, grenze), "Text"

    grenzdatum = (dt.datetime.now() - dt.timedelta(days=tage)) if tage else None
    infrage = [e for e in _lesen()
               if not (grenzdatum and e["wann"] < grenzdatum)]
    if not infrage:
        return [], "Text"

    from . import bedeutung

    # Gleiche Texte kommen im Archiv mehrfach vor ("Alles klar, Sir."). Der
    # Vektor gehoert zum Text, also wird jeder Text nur einmal gewogen und
    # danach dem juengsten Eintrag zugeordnet.
    nach_text: dict[str, dict] = {}
    for e in infrage:
        nach_text[e["text"]] = e

    bewertet = bedeutung.suchen(frage, list(nach_text), grenze=grenze)
    if bewertet is None:
        return suchen(frage, tage, grenze), "Text"
    return [nach_text[text] for text, _wert in bewertet], "Bedeutung"


def letzte_sitzung() -> dict:
    """Was war beim letzten Mal? Ohne die aktuelle Sitzung."""
    frueher = [e for e in _lesen() if e["sitzung"] != SITZUNG]
    if not frueher:
        return {}
    letzte_kennung = frueher[-1]["sitzung"]
    dabei = [e for e in frueher if e["sitzung"] == letzte_kennung]
    fragen = [e["text"] for e in dabei if e["rolle"] == "du"]
    return {"wann": dabei[-1]["wann"], "anzahl": len(dabei),
            "themen": fragen[-3:]}


def aufraeumen() -> int:
    """Alles Ältere als VERLAUF_TAGE wegwerfen. Sonst waechst die Datei ewig."""
    if config.VERLAUF_TAGE <= 0:
        return 0
    grenze = dt.datetime.now() - dt.timedelta(days=config.VERLAUF_TAGE)
    alle = _lesen()
    bleiben = [e for e in alle if e["wann"] >= grenze]
    weg = len(alle) - len(bleiben)
    if weg:
        # Frueher wurden hier die Felder einzeln aufgezaehlt - und damit beim
        # ersten Aufraeumen still die Chat-Kennung abgeschnitten. Jetzt geht
        # es durch dieselbe Stelle wie das Loeschen, die alles uebernimmt.
        _neu_schreiben(bleiben)
    return weg


def fuer_systemprompt() -> str:
    """Eine Zeile fuer den Prompt - mehr nicht, das kostet sonst jedes Mal."""
    from .gedaechtnis import wie_lange_her

    letzte = letzte_sitzung()
    if not letzte:
        return ""
    themen = "; ".join(t[:70] for t in letzte["themen"])
    return (f"Euer letztes Gespraech war {wie_lange_her(letzte['wann'])} "
            f"({letzte['anzahl']} Nachrichten). Zuletzt ging es um: {themen}")
