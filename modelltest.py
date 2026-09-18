"""Welches der freien Modelle taugt als Jarvis' Kopf?

Nicht nach Datenblatt, sondern nach dem, was hier wirklich gebraucht wird:

  1. IST ES DA?            Ein belegtes Modell ist kein Modell. kimi-k3 steht
                           seit Wochen in der Liste und antwortet praktisch nie.
  2. NIMMT ES WERKZEUGE?   Ohne Werkzeugaufrufe ist Jarvis ein Chatfenster.
  3. ANTWORTET ES DEUTSCH? Ohne englisches Selbstgespraech in der Antwort -
                           das war der Fehler, der zuletzt sichtbar wurde.
  4. WIE LANGE DAUERT ES?  Eine Auskunft, die zwanzig Sekunden braucht, wird
                           nicht benutzt.

Aufruf:
    modelltest.py            die aussichtsreichen Kandidaten
    modelltest.py alle       auch die, die vermutlich nichts koennen
    modelltest.py <teil>     nur Modelle, deren Name das enthaelt
"""
import json
import sys
import time

import httpx

from jarvis import config, tools

H = {"Authorization": f"Bearer {config.API_KEY}"}

# Die freien Endpunkte, die ueberhaupt als Gespraechsmodell in Frage kommen.
# Bild-, Sprach- und Fachmodelle stehen weiter unten in EXTRA - sie werden
# hier nicht geprueft, weil sie eine andere Aufgabe haetten.
KANDIDATEN = [
    ("openai/gpt-oss-20b", "der jetzige Kopf"),
    ("moonshotai/kimi-k3", "2.8T multimodal, in der Praxis fast nie frei"),
    ("deepseek-ai/deepseek-v4-flash-0731", "284B MoE, 13B aktiv, agentisch"),
    ("deepseek-ai/deepseek-v4-pro-0813", "262K Kontext, aufs Programmieren"),
    ("nvidia/nemotron-3.5-lightning-30b-a3b", "schnellstes 30B, agentisch"),
    ("nvidia/nemotron-3-super-120b-a12b", "120B, 1M Kontext, Werkzeuge"),
    ("nvidia/nemotron-3-ultra-550b-a55b", "550B, 1M Kontext, Werkzeuge"),
    ("meta/muse-glimmer-30b", "getrennte Denkausgabe - passt zu unserem Kanal"),
    ("google/gemma-4-31b-it", "dense 31B, agentisch"),
    ("mistralai/mistral-nemotron", "auf Funktionsaufrufe gebaut"),
    ("poolside/laguna-xs-2.1", "33B MoE, agentisches Programmieren"),
    ("google/diffusiongemma-26b-a4b-it", "Diffusionsmodell, sehr schnell"),
]

# Nur der Vollstaendigkeit halber - diese sind fuer ein Gespraechsmodell
# ungeeignet, und der Testlauf soll das zeigen statt es zu behaupten.
UNGEEIGNET = [
    ("nvidia/nemotron-voicechat", "nur Englisch"),
    ("google/google-paligemma", "Bildmodell, kein Gespraech"),
]

FRAGE_WERKZEUG = "Wie warm wird es morgen in Hamburg?"
FRAGE_TEXT = "Antworte in einem kurzen Satz auf Deutsch: Wer war Ada Lovelace?"

# Woran man englisches Selbstgespraech in einer deutschen Antwort erkennt
ENGLISCH = ("we need", "the user", "let's", "i should", "need answer",
            "i need to", "let me", "okay, so")


def rufen(modell: str, frage: str, mit_werkzeugen: bool, grenze: int = 500):
    rumpf = {"model": modell, "max_tokens": grenze,
             "messages": [{"role": "system", "content": config.SYSTEM_PROMPT},
                          {"role": "user", "content": frage}]}
    if mit_werkzeugen:
        rumpf["tools"] = tools.schema()
    start = time.perf_counter()
    try:
        r = httpx.post(f"{config.BASE_URL}/chat/completions", headers=H,
                       timeout=90, json=rumpf)
    except Exception as exc:
        return {"fehler": type(exc).__name__,
                "dauer": time.perf_counter() - start}
    dauer = time.perf_counter() - start
    if r.status_code != 200:
        kurz = {400: "Anfrage abgelehnt", 402: "kostenpflichtig",
                404: "gibt es nicht", 410: "Kontingent aufgebraucht",
                429: "belegt", 503: "nicht erreichbar"}.get(
                    r.status_code, f"HTTP {r.status_code}")
        # Bei 400 steht oft der eigentliche Grund im Rumpf - etwa "does not
        # support tools". Das ist genau die Auskunft, die hier zaehlt.
        grund = ""
        try:
            grund = (r.json().get("detail") or r.json().get("title") or "")[:70]
        except Exception:
            grund = r.text[:70]
        return {"fehler": kurz, "grund": grund, "dauer": dauer}
    try:
        nachricht = r.json()["choices"][0]["message"]
    except (KeyError, IndexError, ValueError):
        return {"fehler": "leere Antwort", "dauer": dauer}
    return {"nachricht": nachricht, "dauer": dauer}


def pruefen(modell: str, hinweis: str) -> dict:
    ergebnis = {"modell": modell, "hinweis": hinweis}

    # 1. Werkzeugaufruf
    antwort = rufen(modell, FRAGE_WERKZEUG, mit_werkzeugen=True)
    if "fehler" in antwort:
        ergebnis["zustand"] = antwort["fehler"]
        ergebnis["grund"] = antwort.get("grund", "")
        ergebnis["dauer"] = antwort["dauer"]
        return ergebnis
    rufe = antwort["nachricht"].get("tool_calls") or []
    namen = [tools._saeubern(a["function"]["name"]) for a in rufe]
    ergebnis["werkzeug"] = ", ".join(namen) or "(keins)"
    ergebnis["dauer"] = antwort["dauer"]

    # 2. Deutsche Antwort ohne Selbstgespraech
    zweite = rufen(modell, FRAGE_TEXT, mit_werkzeugen=False, grenze=300)
    if "fehler" in zweite:
        ergebnis["zustand"] = zweite["fehler"]
        return ergebnis
    text = (zweite["nachricht"].get("content") or "").strip()
    ergebnis["text"] = text[:110]
    unten = text.lower()
    ergebnis["selbstgespraech"] = any(w in unten for w in ENGLISCH)
    ergebnis["deutsch"] = any(w in unten for w in
                              (" der ", " die ", " das ", " und ", " war ",
                               " eine ", " ist "))
    ergebnis["zustand"] = "frei"
    ergebnis["dauer2"] = zweite["dauer"]
    return ergebnis


def urteil(e: dict) -> str:
    if e.get("zustand") != "frei":
        return "-"
    if not e.get("deutsch"):
        return "kein Deutsch"
    if e.get("selbstgespraech"):
        return "denkt laut"
    if "get_weather" in e.get("werkzeug", ""):
        return "GEEIGNET"
    if e.get("werkzeug", "(keins)") != "(keins)":
        return "Werkzeug ok"
    return "ohne Werkzeug"


wahl = sys.argv[1].lower() if len(sys.argv) > 1 else ""
liste = KANDIDATEN + UNGEEIGNET if wahl == "alle" else KANDIDATEN
if wahl and wahl != "alle":
    liste = [k for k in liste if wahl in k[0].lower()]

print(f"{len(liste)} Modelle, je zwei Anfragen\n")
ergebnisse = []
for modell, hinweis in liste:
    print(f"  {modell:42} ", end="", flush=True)
    e = pruefen(modell, hinweis)
    ergebnisse.append(e)
    print(f"{urteil(e):14} {e.get('zustand', '?'):22} "
          f"{e.get('dauer', 0):5.1f}s")
    if e.get("grund"):
        print(f"      {e['grund']}")
    if e.get("text"):
        print(f"      Werkzeug: {e.get('werkzeug')}")
        print(f"      {e['text']}")

print("\n--- Zusammenfassung ---")
geeignet = [e for e in ergebnisse if urteil(e) == "GEEIGNET"]
for e in sorted(geeignet, key=lambda x: x.get("dauer", 99)):
    print(f"  {e['dauer']:5.1f}s  {e['modell']:42} {e['hinweis']}")
if not geeignet:
    print("  keins - das waere ein schlechter Tag.")
