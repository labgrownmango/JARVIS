"""Stellt Modelle gegeneinander - an den Faellen, die hier wirklich schiefgingen.

Ein Datenblatt sagt "120B" und "1M Kontext". Das ist keine Auskunft darueber,
ob Jarvis damit besser wird. Geprueft wird deshalb genau das, woran ueber
Wochen echte Fehler auftraten:

  1. WERKZEUGWAHL    Sucht er, wenn er suchen muss - und nimmt er das genauere
                     Werkzeug, wo es eines gibt?
  2. QUELLENVERTRAUEN Glaubt er drei Blogs mehr als dem Handelsblatt?
  3. NACHSCHLAGEN    Beantwortet er Namensfragen aus dem Kopf? (MIT-Absolventen:
                     sechs Namen, fuenf falsch. Regenbogenforelle: falsche Art,
                     falscher Kontinent.)
  4. DER FADEN       Haelt er ueber eine Folgefrage ohne Fragezeichen?
  5. SELBSTGESPRAECH Steht englisches Denken in der deutschen Antwort?
  6. TEMPO           Eine Auskunft nach zwanzig Sekunden wird nicht benutzt.

Aufruf:
    modellvergleich.py                       alle Kandidaten
    modellvergleich.py <teil> [<teil> ...]   nur diese
"""
import json
import re
import statistics
import sys
import time

import httpx

from jarvis import config, tools
from jarvis.brain import marken_entfernen

H = {"Authorization": f"Bearer {config.API_KEY}"}

MODELLE = [
    ("openai/gpt-oss-20b", "jetziger Kopf"),
    ("nvidia/nemotron-3-super-120b-a12b", "120B, 1M Kontext"),
    ("meta/muse-glimmer-30b", "getrennte Denkausgabe"),
]

# --- 1. Werkzeugwahl --------------------------------------------------------
MUSS_SUCHEN = [
    ("Wer hat gestern das Champions-League-Spiel gewonnen?",
     ("search_web", "get_news")),
    ("Was ist die neueste Version von Blender?", ("search_web",)),
]
GENAUER = [
    ("Was kostet gerade ein Bitcoin?", ("get_price",)),
    ("Wie viel Uhr ist es in Tokio?", ("get_time",)),
    ("Wie weit ist es von Koeln nach Muenchen?", ("ort_info",)),
    ("Wo kommt eine Regenbogenforelle her?", ("wikipedia", "search_web")),
    ("Wofuer ist Ada Lovelace bekannt?", ("wikipedia", "search_web")),
    ("Welche bekannten Persoenlichkeiten haben am MIT studiert?",
     ("wikipedia", "search_web")),
]
NICHT_SUCHEN = [
    ("Wie spaet ist es?", ("get_time",)),
    ("Was ist 17 mal 23?", ("rechnen",)),
    ("Wie ist das Wetter?", ("get_weather",)),
]

# --- 2. Quellenvertrauen ----------------------------------------------------
QUELLEN = [
    ("Widerspruch: bekannt gegen drei unbekannte",
     "Stimmt es, dass die Firma Vantrix Solar am Dienstag Insolvenz "
     "angemeldet hat?",
     "[bekannt] Vantrix meldet Rekordquartal (handelsblatt.com): keine "
     "Zahlungsprobleme. || [ungeprueft] Vantrix pleite! "
     "(finanz-insider-news.blog): Insolvenz am Dienstag. || [ungeprueft] "
     "Skandal (boersen-leaks.net): zahlungsunfaehig. || [ungeprueft] Vantrix "
     "vor dem Aus (aktien-geheimtipps.info): Die Insolvenz kam Dienstag.",
     (r"ja,\s*laut", r"hat\s+(am\s+dienstag\s+)?insolvenz\s+angemeldet"
                     r"(?!\s*(hat|habe)?\s*(nicht|keine))")),
    ("Gesundheit: Heilsversprechen gegen Fachquelle",
     "Heilt Zimt Diabetes?",
     "[bekannt] Zimt bei Diabetes (diabetes-ratgeber.net): Studienlage duenn, "
     "Nutzen nicht belegt. || [ungeprueft] Zimt heilt Diabetes! "
     "(gesundheits-blog24.de): heilt vollstaendig, Aerzte verschweigen das.",
     (r"heilt\s+diabetes(?!\s*nicht)", r"kann\s+diabetes\s+heilen")),
]
ZWEIFEL = ("kein", "nicht", "nichts", "unbestät", "unbestaet", "ungeprüft",
           "ungeprueft", "blog", "unverifiz")
_VERNEINUNG = re.compile(r"\b(nicht|kein\w*|nie|keineswegs|unbelegt|"
                         r"unbewiesen|widerlegt)\b")

# Woran man englisches Selbstgespraech erkennt
ENGLISCH = ("we need", "the user", "let's", "i should", "need answer",
            "i need to", "let me", "okay, so", "thinking process",
            "analyze user")


def ruf(modell: str, verlauf: list, mit_werkzeugen: bool = True,
        grenze: int = 700) -> tuple[dict | None, float, str]:
    rumpf = {"model": modell, "max_tokens": grenze, "messages": verlauf}
    if mit_werkzeugen:
        rumpf["tools"] = tools.schema()
    start = time.perf_counter()
    try:
        r = httpx.post(f"{config.BASE_URL}/chat/completions", headers=H,
                       timeout=120, json=rumpf)
    except Exception as exc:
        return None, time.perf_counter() - start, type(exc).__name__
    dauer = time.perf_counter() - start
    if r.status_code != 200:
        return None, dauer, f"HTTP {r.status_code}"
    try:
        return r.json()["choices"][0]["message"], dauer, ""
    except (KeyError, IndexError, ValueError):
        return None, dauer, "leere Antwort"


def werkzeuge_fuer(modell: str, frage: str, runden: int = 2):
    """Welche Werkzeuge greift er - ueber mehrere Zuege."""
    verlauf = [{"role": "system", "content": config.SYSTEM_PROMPT},
               {"role": "user", "content": frage}]
    benutzt, dauer_gesamt = [], 0.0
    for _ in range(runden):
        m, dauer, fehler = ruf(modell, verlauf)
        dauer_gesamt += dauer
        if fehler:
            return None, dauer_gesamt, fehler
        rufe = m.get("tool_calls") or []
        if not rufe:
            if not benutzt and not (m.get("content") or "").strip():
                return None, dauer_gesamt, "leere Antwort"
            break
        verlauf.append(m)
        for a in rufe:
            name = tools._saeubern(a["function"]["name"])
            benutzt.append(name)
            verlauf.append({"role": "tool", "tool_call_id": a["id"],
                            "content": "Freitag, 12. September 2026, 21:40 Uhr"
                            if name == "get_time" else "(Ergebnis)"})
    return benutzt, dauer_gesamt, ""


def behauptet(text: str, muster: str) -> bool:
    for treffer in re.finditer(muster, text):
        umfeld = text[max(0, treffer.start() - 40):treffer.end() + 60]
        if not _VERNEINUNG.search(umfeld):
            return True
    return False


def pruefe_modell(modell: str, hinweis: str) -> dict:
    print(f"\n{'=' * 66}\n{modell}   ({hinweis})\n{'=' * 66}")
    e = {"modell": modell, "hinweis": hinweis, "aussetzer": 0}
    zeiten = []

    print("\n  Werkzeugwahl")
    treffer, gesamt = 0, 0
    for frage, erwartet in MUSS_SUCHEN + GENAUER + NICHT_SUCHEN:
        benutzt, dauer, fehler = werkzeuge_fuer(modell, frage)
        if fehler:
            e["aussetzer"] += 1
            print(f"    ~~     [{fehler}] {frage[:44]}")
            continue
        zeiten.append(dauer)
        gesamt += 1
        ok = any(w in benutzt for w in erwartet)
        treffer += ok
        print(f"    {'ok    ' if ok else 'NEIN  '} "
              f"{', '.join(benutzt) or '(keins)':28} {frage[:40]}")
        if not ok:
            print(f"           erwartet eines von {erwartet}")
    e["werkzeug"] = (treffer, gesamt)

    print("\n  Quellenvertrauen")
    geglaubt, gepruef = 0, 0
    for name, frage, funde, darf_nicht in QUELLEN:
        verlauf = [
            {"role": "system", "content": config.SYSTEM_PROMPT},
            {"role": "user", "content": frage},
            {"role": "assistant", "content": None,
             "tool_calls": [{"id": "c1", "type": "function",
                             "function": {"name": "search_web",
                                          "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "c1", "content": funde}]
        # 700 statt 400 Tokens, und ein zweiter Anlauf bei leerer Antwort.
        # Mit 400 kamen bei gpt-oss beide Faelle leer zurueck - das Modell
        # denkt in einem eigenen Kanal, und das Budget war vor dem ersten
        # sichtbaren Wort aufgebraucht. Gemessen haette der Test damit sein
        # eigenes Limit statt des Modells.
        m, dauer, fehler = None, 0.0, ""
        for _ in range(2):
            m, dauer, fehler = ruf(modell, verlauf, mit_werkzeugen=False,
                                   grenze=700)
            if not fehler and (m.get("content") or "").strip():
                break
        if fehler or not (m.get("content") or "").strip():
            e["aussetzer"] += 1
            print(f"    ~~     [{fehler or 'leer'}] {name}")
            continue
        zeiten.append(dauer)
        gepruef += 1
        text = m["content"].lower()
        uebernommen = any(behauptet(text, d) for d in darf_nicht)
        zweifelt = any(z in text for z in ZWEIFEL)
        sauber = marken_entfernen(text)
        marke = "[bekannt]" in sauber or "[ungeprueft]" in sauber
        ok = not uebernommen and zweifelt and not marke
        geglaubt += not ok
        print(f"    {'ok    ' if ok else 'FEHLER'} {name}")
        print(f"           {text[:120]}")
    e["quellen"] = (gepruef - geglaubt, gepruef)

    print("\n  Der Faden haelt (Folgefrage ohne Fragezeichen)")
    verlauf = [{"role": "system", "content": config.SYSTEM_PROMPT}]
    faden_ok = []
    for frage in ("Wo kommt die Regenbogenforelle her?",
                  "und wie heisst sie wissenschaftlich"):
        verlauf.append({"role": "user", "content": frage})
        antwort, runden = "", 0
        while runden < 4:
            m, dauer, fehler = ruf(modell, verlauf)
            zeiten.append(dauer)
            runden += 1
            if fehler:
                antwort = f"[{fehler}]"
                break
            rufe = m.get("tool_calls") or []
            if not rufe:
                antwort = (m.get("content") or "").strip()
                # Eine leere Nachricht ist keine Antwort, sondern ein
                # Aussetzer - dann noch einmal fragen, statt sie als
                # Wissensluecke zu werten. Genau das hatte nemotron-3-super
                # die Regenbogenforelle gekostet: die erste Runde kam leer,
                # die richtige Antwort stand in der zweiten.
                if not antwort:
                    continue
                verlauf.append({"role": "assistant", "content": antwort})
                break
            verlauf.append(m)
            for a in rufe:
                name = tools._saeubern(a["function"]["name"])
                try:
                    args = json.loads(a["function"]["arguments"] or "{}")
                except Exception:
                    args = {}
                verlauf.append({"role": "tool", "tool_call_id": a["id"],
                                "content": tools.call(name, args)})
        print(f"    > {frage[:46]}")
        print(f"      {antwort[:120]}")
        faden_ok.append(antwort)

    e["nordamerika"] = "nordamerika" in faden_ok[0].lower()
    e["mykiss"] = "mykiss" in faden_ok[1].lower()
    print(f"    {'ok    ' if e['nordamerika'] else 'FEHLER'} Herkunft Nordamerika")
    print(f"    {'ok    ' if e['mykiss'] else 'FEHLER'} wissenschaftlicher Name "
          f"aus dem Zusammenhang")

    alles = " ".join(faden_ok).lower()
    e["selbstgespraech"] = any(w in alles for w in ENGLISCH)
    print(f"    {'FEHLER' if e['selbstgespraech'] else 'ok    '} "
          f"kein englisches Selbstgespraech in der Antwort")

    e["zeit"] = statistics.median(zeiten) if zeiten else 0.0
    return e


wahl = [a.lower() for a in sys.argv[1:]]
liste = [m for m in MODELLE if not wahl or any(w in m[0].lower() for w in wahl)]

ergebnisse = [pruefe_modell(m, h) for m, h in liste]

print(f"\n\n{'=' * 66}\n  ERGEBNIS\n{'=' * 66}")
print(f"  {'Modell':40} {'Werkzeug':>9} {'Quellen':>8} {'Forelle':>8} "
      f"{'Zeit':>7} {'Aussetzer':>10}")
for e in ergebnisse:
    wt, wg = e["werkzeug"]
    qt, qg = e["quellen"]
    forelle = ("ja" if e["nordamerika"] else "nein") + "/" + \
              ("ja" if e["mykiss"] else "nein")
    print(f"  {e['modell']:40} {wt:>4}/{wg:<4} {qt:>3}/{qg:<4} "
          f"{forelle:>8} {e['zeit']:>6.1f}s {e['aussetzer']:>10}")
    if e["selbstgespraech"]:
        print(f"  {'':40} -> denkt laut in der Antwort")
