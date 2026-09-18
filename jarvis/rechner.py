"""Rechnen, ohne das Modell rechnen zu lassen.

Sprachmodelle rechnen schlecht. Gemessen in dieser Sitzung: "66.490.00 Euro"
als Preisangabe, erfundene Namen in einer Wikipedia-Zusammenfassung, ein Wort
namens "Kommandooszillationskopf". Bei Zahlen ist das kein Schoenheitsfehler -
eine falsche Summe sieht genauso souveraen aus wie eine richtige.

Deshalb wird hier wirklich gerechnet. Kein eval(): der Ausdruck wird zerlegt
und nur das ausgewertet, was in einer Rechnung vorkommen darf. Ein eval()
haette Zugriff auf alles, was Python kann - und der Ausdruck kommt vom Modell,
also mittelbar aus dem Netz.
"""
from __future__ import annotations

import ast
import math
import operator
import re

# Was gerechnet werden darf - mehr nicht
_ZWEISTELLIG = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_EINSTELLIG = {ast.UAdd: operator.pos, ast.USub: operator.neg}

_FUNKTIONEN = {
    "wurzel": math.sqrt, "sqrt": math.sqrt,
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "log": math.log10, "ln": math.log, "log2": math.log2,
    "exp": math.exp, "abs": abs, "betrag": abs,
    "runden": round, "round": round,
    "boden": math.floor, "decke": math.ceil,
    "floor": math.floor, "ceil": math.ceil,
    "fakultaet": math.factorial, "fak": math.factorial,
    "min": min, "max": max, "summe": lambda *a: sum(a),
    "grad": math.degrees, "bogen": math.radians,
}
_WERTE = {"pi": math.pi, "e": math.e, "tau": math.tau}

# Wie Menschen schreiben, nicht wie Python liest
_ERSATZ = [
    (r"\s+", " "),
    (r"(?i)\bmal\b|×|·|✕", "*"),
    (r"(?i)\bgeteilt durch\b|\bdurch\b|÷|:(?![0-9]{2}\b)", "/"),
    (r"(?i)\bplus\b", "+"),
    (r"(?i)\bminus\b", "-"),
    (r"(?i)\bhoch\b|\^", "**"),
    (r"(?i)\bvon hundert\b|\bprozent von\b", "% von "),
    (r"√", "wurzel"),
    (r"(?i)\bquadrat\b", "**2"),
]


class RechenFehler(Exception):
    pass


def _vorbereiten(roh: str) -> str:
    text = roh.strip().rstrip("=?").strip()
    for muster, ersatz in _ERSATZ:
        text = re.sub(muster, ersatz, text)

    # "20% von 80" ist eine der haeufigsten Alltagsfragen und in Python kein
    # gueltiger Ausdruck - % ist dort der Rest einer Division.
    text = re.sub(r"([\d.,]+)\s*%\s*von\s*([\d.,()+\-*/ ]+)",
                  r"((\1)/100*(\2))", text, flags=re.IGNORECASE)

    # "123 456 789" - Leerzeichen als Tausendertrennung
    text = re.sub(r"(?<=\d) (?=\d{3}(\D|$))", "", text)

    # "1.000 * 3" ergab 3: ohne Komma wurde "1.000" als eins-komma-null
    # gelesen. Ein deutscher Tausenderpunkt steht immer vor GENAU drei
    # Ziffern und wiederholt sich ("1.234.567") - "3.14" und "2.5" bleiben
    # deshalb unberuehrt.
    text = re.sub(r"\b\d{1,3}(?:\.\d{3})+\b",
                  lambda t: t.group(0).replace(".", ""), text)
    return text


def _komma_deutsch(text: str) -> str:
    """1.234,56 -> 1234.56. Nur anwenden, wenn ein Komma vorkommt."""
    if "," not in text:
        return text
    ohne_tausender = re.sub(r"(?<=\d)\.(?=\d{3}\b)", "", text)
    return ohne_tausender.replace(",", ".")


def _auswerten(knoten):
    if isinstance(knoten, ast.Constant):
        if isinstance(knoten.value, (int, float)):
            return knoten.value
        raise RechenFehler(f"{knoten.value!r} ist keine Zahl")
    if isinstance(knoten, ast.BinOp):
        rechnung = _ZWEISTELLIG.get(type(knoten.op))
        if rechnung is None:
            raise RechenFehler("Diesen Rechenschritt kenne ich nicht")
        links, rechts = _auswerten(knoten.left), _auswerten(knoten.right)
        # Ein Rechner, der den Rechner aufhaengt, ist keiner: 9**9**9 laeuft
        # sonst minutenlang und frisst den Speicher.
        if isinstance(knoten.op, ast.Pow) and (abs(rechts) > 1000
                                               or abs(links) > 1e12):
            raise RechenFehler("Die Potenz ist zu gross")
        return rechnung(links, rechts)
    if isinstance(knoten, ast.UnaryOp):
        rechnung = _EINSTELLIG.get(type(knoten.op))
        if rechnung is None:
            raise RechenFehler("Dieses Vorzeichen kenne ich nicht")
        return rechnung(_auswerten(knoten.operand))
    if isinstance(knoten, ast.Name):
        if knoten.id.lower() in _WERTE:
            return _WERTE[knoten.id.lower()]
        raise RechenFehler(f"'{knoten.id}' sagt mir nichts")
    if isinstance(knoten, ast.Call):
        name = getattr(knoten.func, "id", "").lower()
        funktion = _FUNKTIONEN.get(name)
        if funktion is None:
            raise RechenFehler(f"Die Funktion '{name}' kenne ich nicht")
        if knoten.keywords:
            raise RechenFehler("Benannte Angaben gehen hier nicht")
        werte = [_auswerten(a) for a in knoten.args]
        if name in ("fakultaet", "fak") and (werte[0] > 1000 or werte[0] < 0):
            raise RechenFehler("Die Fakultaet ist zu gross")
        return funktion(*werte)
    raise RechenFehler("Das ist keine Rechnung")


def rechne(ausdruck: str) -> tuple[float, str]:
    """Gibt (Ergebnis, aufbereiteter Ausdruck) zurueck."""
    if not ausdruck.strip():
        raise RechenFehler("Was soll ich rechnen?")
    vorbereitet = _vorbereiten(ausdruck)
    if len(vorbereitet) > 400:
        raise RechenFehler("Die Rechnung ist zu lang")

    # Das Komma ist zweideutig: in "3,5 * 2" ist es ein Dezimalzeichen, in
    # "max(3,9,2)" trennt es Argumente. Statt zu raten wird jede Lesart ganz
    # durchgerechnet - die deutsche zuerst, weil hier deutsch geschrieben
    # wird. Nur zerlegen reicht nicht: "min(5,2)" wird deutsch zu "min(5.2)",
    # das ist gueltiger Python-Code und trotzdem Unsinn.
    kandidaten = [_komma_deutsch(vorbereitet)]
    if vorbereitet not in kandidaten:
        kandidaten.append(vorbereitet)

    letzter = None
    for kandidat in kandidaten:
        try:
            baum = ast.parse(kandidat, mode="eval")
            return _auswerten(baum.body), kandidat
        except SyntaxError:
            letzter = letzter or RechenFehler(
                f"'{ausdruck}' ergibt keine Rechnung")
        except ZeroDivisionError:
            raise RechenFehler("Durch null teilen geht nicht") from None
        except RechenFehler as exc:
            letzter = letzter or exc
        except (TypeError, ValueError, OverflowError) as exc:
            letzter = letzter or RechenFehler(f"Das geht nicht aus: {exc}")
    raise letzter or RechenFehler(f"'{ausdruck}' ergibt keine Rechnung")


def formatiere(zahl: float) -> str:
    """Deutsche Schreibweise, ohne Nachkommastellen, die niemand braucht."""
    if isinstance(zahl, int) or (isinstance(zahl, float) and zahl.is_integer()):
        roh = f"{int(zahl):,}"
    elif abs(zahl) >= 1e12 or (zahl != 0 and abs(zahl) < 1e-4):
        return f"{zahl:.6g}".replace(".", ",")
    else:
        roh = f"{zahl:,.6f}".rstrip("0").rstrip(".")
    # Punkt und Komma tauschen - im Deutschen andersherum als im Englischen
    return roh.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
