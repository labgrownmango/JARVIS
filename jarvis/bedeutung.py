"""Suchen nach Bedeutung statt nach Buchstaben.

Bisher suchte das Archiv nach Zeichenketten. Wer "worueber haben wir wegen
dem Drucker geredet" fragte, fand nichts, wenn im Gespraech "Papierstau"
oder "Toner" stand. Ein Mensch haette es gefunden.

Hier wird jeder Eintrag in einen Vektor uebersetzt und die Frage ebenso; was
naeh beieinanderliegt, gehoert zusammen. Das Modell dafuer ist
nemotron-3-embed-1b, ein freier Endpunkt - 2048 Dimensionen, und es
unterscheidet ausdruecklich zwischen Frage (query) und Fundstueck (passage).

Drei Dinge, die hier bewusst so sind:

  ZWISCHENSPEICHER  Jeder Text wird genau einmal uebersetzt; das Ergebnis
                    steht in data/einbettungen.jsonl unter dem Fingerabdruck
                    des Textes. Ein Archiv mit tausend Eintraegen jedes Mal
                    neu durchzurechnen waere Verschwendung und langsam.
  KEIN ZWANG        Ist das Netz weg oder das Modell belegt, faellt die Suche
                    auf die Textsuche zurueck. Sie wird schlechter, nicht
                    kaputt.
  NICHTS WAECHST UNBEGRENZT  Der Zwischenspeicher wird beschnitten, sobald er
                    zu gross wird - sonst liegt irgendwann ein Vielfaches des
                    Archivs daneben.
"""
from __future__ import annotations

import hashlib
import json
import math
import threading

from . import config

DATEI = config.ROOT / "data" / "einbettungen.jsonl"
MODELL = "nvidia/nemotron-3-embed-1b"

# So viele Texte gehen in einem Aufruf mit. Mehr waere schneller, aber eine
# zu grosse Anfrage wird abgelehnt und dann ist gar nichts gewonnen.
BUENDEL = 32
# Hoechstens so viele Vektoren behalten. 2048 Zahlen je Eintrag sind rund
# 20 KB als Text - bei 5000 Eintraegen also etwa 100 MB. Das ist die Grenze.
HOECHSTENS = 5000

_schloss = threading.Lock()
_speicher: dict[str, list[float]] | None = None


def _fingerabdruck(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:16]


def _laden() -> dict[str, list[float]]:
    global _speicher
    with _schloss:
        if _speicher is not None:
            return _speicher
        _speicher = {}
        if DATEI.exists():
            for zeile in DATEI.read_text(encoding="utf-8").splitlines():
                try:
                    eintrag = json.loads(zeile)
                    _speicher[eintrag["id"]] = eintrag["v"]
                except (json.JSONDecodeError, KeyError):
                    continue
        return _speicher


def _anhaengen(neue: dict[str, list[float]]) -> None:
    if not neue:
        return
    with _schloss:
        DATEI.parent.mkdir(parents=True, exist_ok=True)
        with DATEI.open("a", encoding="utf-8") as fh:
            for kennung, vektor in neue.items():
                fh.write(json.dumps({"id": kennung, "v": vektor}) + "\n")
        if _speicher is not None:
            _speicher.update(neue)
    _beschneiden()


def _beschneiden() -> None:
    """Die aeltesten Vektoren wegwerfen, wenn es zu viele werden."""
    speicher = _laden()
    if len(speicher) <= HOECHSTENS:
        return
    with _schloss:
        behalten = dict(list(speicher.items())[-HOECHSTENS:])
        neben = DATEI.with_suffix(".jsonl.neu")
        with neben.open("w", encoding="utf-8") as fh:
            for kennung, vektor in behalten.items():
                fh.write(json.dumps({"id": kennung, "v": vektor}) + "\n")
        neben.replace(DATEI)
        globals()["_speicher"] = behalten


def _holen(texte: list[str], art: str) -> list[list[float]] | None:
    """Vektoren vom Modell. Gibt None zurueck, wenn es nicht klappt."""
    import httpx

    try:
        r = httpx.post(
            f"{config.BASE_URL}/embeddings",
            headers={"Authorization": f"Bearer {config.API_KEY}"},
            timeout=60,
            json={"model": MODELL, "input": texte, "input_type": art,
                  "encoding_format": "float"})
    except Exception:
        return None
    if r.status_code != 200:
        return None
    try:
        daten = sorted(r.json()["data"], key=lambda d: d.get("index", 0))
        return [d["embedding"] for d in daten]
    except (KeyError, ValueError, TypeError):
        return None


def vektoren(texte: list[str]) -> dict[str, list[float]] | None:
    """Vektoren fuer Fundstuecke - aus dem Zwischenspeicher oder frisch."""
    speicher = _laden()
    fehlend, zuordnung = [], {}
    for text in texte:
        kennung = _fingerabdruck(text)
        zuordnung[text] = kennung
        if kennung not in speicher and text not in fehlend:
            fehlend.append(text)

    neue: dict[str, list[float]] = {}
    for i in range(0, len(fehlend), BUENDEL):
        teil = fehlend[i:i + BUENDEL]
        antwort = _holen(teil, "passage")
        if antwort is None:
            return None                    # unvollstaendig ist wertlos
        for text, vektor in zip(teil, antwort):
            neue[_fingerabdruck(text)] = vektor
    _anhaengen(neue)

    speicher = _laden()
    return {text: speicher[kennung] for text, kennung in zuordnung.items()
            if kennung in speicher}


def frage_vektor(frage: str) -> list[float] | None:
    """Die Frage wird als 'query' uebersetzt, nicht als 'passage'.

    Das Modell unterscheidet das ausdruecklich, und es macht einen
    messbaren Unterschied: eine Frage und ihre Antwort sehen sprachlich
    verschieden aus, meinen aber dasselbe.
    """
    antwort = _holen([frage], "query")
    return antwort[0] if antwort else None


def aehnlichkeit(a: list[float], b: list[float]) -> float:
    """Kosinus - wie klein ist der Winkel zwischen den beiden?"""
    laenge_a = math.sqrt(sum(x * x for x in a))
    laenge_b = math.sqrt(sum(x * x for x in b))
    if not laenge_a or not laenge_b:
        return 0.0
    return sum(x * y for x, y in zip(a, b)) / (laenge_a * laenge_b)


def verfuegbar() -> bool:
    """Antwortet das Einbettungsmodell gerade?"""
    return frage_vektor("Test") is not None


# Wie weit ein Treffer aus dem Rest herausragen muss - in Streuungen.
#
# Eine feste Zahl kann hier nicht stimmen: bei zehn Eintraegen liegen alle
# Aehnlichkeiten niedriger als bei dreihundert, und nach der Zentrierung
# sinken sie noch einmal. Eine Schwelle von 0,20 verwarf deshalb im kleinen
# Archiv richtige Treffer, die auf Platz 1 standen.
#
# Was sich NICHT mit der Groesse aendert: bei einer echten Frage sticht ein
# Treffer heraus, bei einer unsinnigen ist alles gleich mittelmaessig.
# Gemessen (z = wie viele Streuungen ueber dem Mittel):
#     "Druckerproblem"      z=2.5    "Grafikkarte"   z=2.7
#     "Bild vom Schnitzel"  z=3.8    "ueber Schlaf"  z=3.0
#     Unsinnsfrage          z=2.0 und z=2.2
# Der Abstand allein reicht also knapp nicht - deshalb zusaetzlich ein
# niedriger Boden auf dem Rohwert. Beides zusammen trennt alle neun
# gemessenen Faelle richtig.
STREUUNGEN = 2.0
BODEN = 0.12


def _zentrieren(vektoren_liste: list[list[float]]) -> list[float]:
    """Der Schwerpunkt aller Vektoren."""
    anzahl = len(vektoren_liste)
    laenge = len(vektoren_liste[0])
    return [sum(v[i] for v in vektoren_liste) / anzahl for i in range(laenge)]


def suchen(frage: str, texte: list[str], grenze: int = 8
           ) -> list[tuple[str, float]] | None:
    """Die passendsten Texte zur Frage, beste zuerst.

    None heisst: ging nicht - dann nimmt der Aufrufer die Textsuche. Eine
    leere Liste heisst dagegen: hat geklappt, es passte nur nichts.

    Vor dem Vergleich wird der Schwerpunkt aller Vektoren abgezogen. Ohne
    das ziehen kurze, nichtssagende Eintraege alles an: gemessen landete
    "wie geht es dir" bei der Frage nach Preisen auf Platz 1 - vor der
    Nachricht, in der wirklich nach einem Preis gefragt wurde. Zentriert
    bleibt das uebrig, was einen Text von den anderen UNTERSCHEIDET, und
    derselbe Fall rueckte auf Platz 1 vor.
    """
    if not texte:
        return []
    ziel = frage_vektor(frage)
    if ziel is None:
        return None
    karte = vektoren(texte)
    if not karte:
        return None if karte is None else []

    mittel = _zentrieren(list(karte.values()))
    ziel_z = [x - m for x, m in zip(ziel, mittel)]
    bewertet = [(text, aehnlichkeit(ziel_z, [x - m for x, m in zip(v, mittel)]))
                for text, v in karte.items()]
    bewertet.sort(key=lambda p: p[1], reverse=True)

    werte = [w for _t, w in bewertet]
    if len(werte) < 3:                     # zu wenig fuer eine Streuung
        return [(t, w) for t, w in bewertet if w >= BODEN][:grenze]
    durchschnitt = sum(werte) / len(werte)
    streuung = math.sqrt(
        sum((w - durchschnitt) ** 2 for w in werte) / len(werte))
    schwelle = max(durchschnitt + STREUUNGEN * streuung, BODEN)
    return [(t, w) for t, w in bewertet if w >= schwelle][:grenze]
