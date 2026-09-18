"""Prüft Folgefragen - also das, was ein Gespräch von Einzelfragen trennt.

Alle anderen Tests stellen eine Frage und sehen sich die Antwort an. Damit
blieb ungeprüft, was im Alltag ständig vorkommt: "und wer hatte die Vorarbeit
dazu geleistet" - ohne Fragezeichen, mit einem "dazu", das sich auf die
vorige Antwort bezieht, und mit einem Suchbegriff, den erst das Modell aus
dem Zusammenhang herleiten muss.

Geprüft wird nicht die Formulierung - die gerät diesem Modell regelmäßig
daneben -, sondern ob der Faden hält: Bezieht es "dazu" richtig? Fragt es
sinnvoll nach? Steht der richtige Name in der Antwort?
"""
import json
import re

import httpx

from jarvis import config, tools

H = {"Authorization": f"Bearer {config.API_KEY}"}
MODELL = "openai/gpt-oss-20b"
fehler = 0
uebersprungen = 0


def pruefe(bedingung: bool, text: str, zusatz: str = "") -> None:
    global fehler
    fehler += not bedingung
    print(f"  {'ok    ' if bedingung else 'FEHLER'} {text}")
    if not bedingung and zusatz:
        print(f"         {zusatz}")


def gespraech(fragen: list[str], runden: int = 4) -> list[dict]:
    """Führt die Fragen NACHEINANDER mit gemeinsamem Verlauf.

    Gibt je Frage zurück, welche Werkzeuge griffen und was geantwortet wurde.
    """
    verlauf = [{"role": "system", "content": config.SYSTEM_PROMPT}]
    ergebnisse = []
    for frage in fragen:
        tools.anfrage_beginnt()
        verlauf.append({"role": "user", "content": frage})
        benutzt, antwort, argumente = [], "", []
        for _ in range(runden):
            try:
                r = httpx.post(f"{config.BASE_URL}/chat/completions",
                               headers=H, timeout=180,
                               json={"model": MODELL, "max_tokens": 700,
                                     "tools": tools.schema(),
                                     "messages": verlauf})
            except Exception as exc:
                antwort = f"[{type(exc).__name__}]"
                break
            if r.status_code != 200:
                antwort = f"[{r.status_code}]"
                break
            try:
                m = r.json()["choices"][0]["message"]
            except (KeyError, IndexError, ValueError):
                antwort = "[leere Antwort]"
                break
            rufe = m.get("tool_calls") or []
            if not rufe:
                antwort = (m.get("content") or "").strip()
                verlauf.append({"role": "assistant", "content": antwort})
                break
            verlauf.append(m)
            for a in rufe:
                name = tools._saeubern(a["function"]["name"])
                benutzt.append(name)
                try:
                    args = json.loads(a["function"]["arguments"] or "{}")
                except Exception:
                    args = {}
                argumente.append(args)
                verlauf.append({"role": "tool", "tool_call_id": a["id"],
                                "content": tools.call(name, args)})
        ergebnisse.append({"frage": frage, "werkzeuge": benutzt,
                           "argumente": argumente, "antwort": antwort})
    return ergebnisse


print("=== Eine Folgefrage ohne Fragezeichen ===")
# "dazu" zeigt zurück auf die vorige Antwort, und der Suchbegriff für die
# zweite Frage steht nirgends - das Modell muss ihn aus dem Artikel der
# ersten Frage herleiten.
HAWKING = ["was ist die Hawking strahlung und wann wurde sie von wem "
           "entdeckt und begruendet?",
           "und wer hatte die vorarbeit dazu geleistet"]

# Zwei Anlaeufe, so wie es ichtest.py seit jeher haelt. Gemessen: derselbe
# Abschnitt wurde in einem Reihenlauf rot ("kein Werkzeug benutzt", "nennt
# Bekenstein nicht") und lief unmittelbar danach allein gruen durch. Das
# ist die Tagesform des Modells, nicht eine Faehigkeit, die fehlt - und ein
# Test, der daran ein ums andere Mal rot wird, wird nach dem dritten Mal
# ignoriert. Dann nuetzt er gar nichts mehr.
#
# Wiederholt wird nur, was WACKELT: schlaegt er beim ersten Mal nach und
# nennt Bekenstein, bleibt es beim ersten Lauf. Sonst ein zweiter, und der
# zaehlt.
lauf = gespraech(HAWKING)
if not (lauf and "wikipedia" in lauf[0]["werkzeuge"]
        and "bekenstein" in lauf[1]["antwort"].lower()):
    print("  (~~ erster Anlauf unvollstaendig - zweiter Versuch)")
    lauf = gespraech(HAWKING)

for schritt in lauf:
    print(f"\n  > {schritt['frage'][:64]}")
    print(f"    Werkzeuge: {schritt['werkzeuge'] or '(keine)'}")
    print(f"    {schritt['antwort'][:150]}")

erste, zweite = lauf[0], lauf[1]

if any(a.startswith("[") for a in (erste["antwort"], zweite["antwort"])):
    uebersprungen += 1
    print("\n  ~~     Das Modell antwortete nicht - übersprungen")
else:
    print()
    pruefe("wikipedia" in erste["werkzeuge"],
           "erste Frage: schlägt nach statt zu raten",
           str(erste["werkzeuge"]))
    pruefe("hawking" in erste["antwort"].lower(),
           "erste Frage: nennt Hawking")
    # Die Strahlung wurde nie beobachtet. Geprüft wird deshalb, dass er das
    # NICHT behauptet - nicht, ob er ein bestimmtes Wort benutzt.
    #
    # Die erste Fassung verlangte eines aus einer Wortliste ("vorhergesagt",
    # "theoretisch", ...) und fiel bei dieser Antwort durch: "die laut der
    # Quantenfeldtheorie Schwarze Löcher abgeben". Das ist eine einwandfreie
    # theoretische Einordnung - nur eben mit anderen Worten. Eine Wortliste
    # misst die Formulierung, und die gerät diesem Modell jedes Mal anders.
    unten = erste["antwort"].lower()
    _BEHAUPTET = re.compile(
        r"(wurde[n]?\s+(?:\w+\s+){0,3}(entdeckt|nachgewiesen|beobachtet|"
        r"gemessen)|hat\s+sie\s+entdeckt|entdeckte\s+die\s+hawking)")
    behauptet = [t.group(0) for t in _BEHAUPTET.finditer(unten)
                 if "nie" not in unten[max(0, t.start() - 40):t.end() + 30]
                 and "nicht" not in unten[max(0, t.start() - 40):t.end() + 30]]
    pruefe(not behauptet,
           "erste Frage: behauptet keine Entdeckung",
           f"steht da: {behauptet} in {erste['antwort'][:110]}")
    # Eine ausdrückliche Einordnung ist die Zugabe, nicht der Prüfstein.
    if any(w in unten for w in ("vorhergesagt", "theoretisch", "vorhersage",
                                "postuliert", "hergeleitet", "laut der",
                                "theorie")):
        print("  ok     erste Frage: ordnet sie zusätzlich als Theorie ein")
    else:
        print("  ~~     erste Frage: ohne ausdrückliche Einordnung - "
              "aber auch ohne falsche Behauptung")

    # Ob er dafür nochmal nachschlägt, ist ihm überlassen: steht die Antwort
    # schon im Verlauf, ist Nachschlagen Verschwendung. Geprüft wird das
    # Ergebnis. Schlägt er nach, muss der Begriff aber aus dem Zusammenhang
    # kommen - in der Frage steht er nicht.
    # ALLE Argumentwerte ansehen, nicht nur "begriff". Die Werkzeuge nennen
    # ihre Eingabe verschieden: wikipedia hat "begriff", search_web hat
    # "frage". Die erste Fassung sah nur nach "begriff" - schlug das Modell
    # also über die Suche nach, war das Feld leer, und der Test meldete
    # "der Begriff kam aus dem Nichts", obwohl der Suchbegriff einwandfrei
    # hergeleitet war.
    begriffe = " ".join(str(w) for a in zweite["argumente"]
                        for w in a.values() if isinstance(w, str))
    if zweite["werkzeuge"]:
        pruefe(any(w in begriffe.lower() for w in ("bekenstein", "hawking",
                                                   "entropie", "schwarz")),
               f"zweite Frage: hergeleiteter Suchbegriff ({begriffe[:46]})",
               "der Begriff kam aus dem Nichts")
    else:
        print("  ~~     zweite Frage: aus dem Verlauf beantwortet, "
              "ohne neues Nachschlagen - auch richtig")

    pruefe("bekenstein" in zweite["antwort"].lower(),
           "zweite Frage: nennt Bekenstein",
           zweite["antwort"][:150])
    # Die Jahreszahl ist eine Zugabe, kein Prüfstein. Geprüft wird, ob der
    # Faden hält und der richtige Name kommt - das ist die Fähigkeit. Ob er
    # zusätzlich das Jahr nennt, schwankt von Lauf zu Lauf, und daran den
    # ganzen Testlauf scheitern zu lassen misst die Tagesform, nicht das
    # Können. "1972/73" ist übrigens genauer als "1973".
    if any(j in zweite["antwort"] for j in ("1972", "1973", "1974")):
        print("  ok     zweite Frage: nennt zusätzlich die Jahreszahl")
    else:
        print("  ~~     zweite Frage: ohne Jahreszahl - Name stimmt, "
              "reicht für den Faden")

print("\n=== Der Faden hält auch über drei Schritte ===")
lauf2 = gespraech([
    "Wo kommt die Regenbogenforelle her?",
    "und wie heisst sie wissenschaftlich",
    "wurde sie dort ausgesetzt oder ist sie heimisch",
])
for schritt in lauf2:
    print(f"\n  > {schritt['frage'][:60]}")
    print(f"    {schritt['antwort'][:130]}")

if any(s["antwort"].startswith("[") for s in lauf2):
    uebersprungen += 1
    print("\n  ~~     Das Modell antwortete nicht - übersprungen")
else:
    print()
    # Geprueft wird die SACHE, nicht die Schreibweise. Gemessen wurde der
    # Test rot bei zwei Antworten, die beide richtig waren:
    #
    #   "<en>The rainbow trout originates from western North America ...</en>"
    #   "... gehoert zur Fischfauna West-Nord-Amerikas"   (mit U+2011,
    #                                                      geschuetzten
    #                                                      Bindestrichen)
    #
    # Im ersten Fall antwortete das Modell englisch - das ist ein anderer
    # Mangel, und dafuer gibt es einen eigenen Test. Im zweiten stand der
    # richtige Erdteil da, nur mit einem Zeichen, das wie ein Bindestrich
    # aussieht und keiner ist. Ein Test, der beides als "Herkunft falsch"
    # meldet, schickt die Fehlersuche in die falsche Richtung.
    herkunft = lauf2[0]["antwort"].lower()
    for strich in ("‐", "‑", "‒", "–", "—", "-", " "):
        herkunft = herkunft.replace(strich, "")
    pruefe(any(w in herkunft for w in ("nordamerika", "northamerica")),
           "Herkunft richtig: Nordamerika", lauf2[0]["antwort"][:110])
    pruefe("mykiss" in lauf2[1]["antwort"].lower(),
           "wissenschaftlicher Name aus dem Zusammenhang",
           lauf2[1]["antwort"][:110])
    # Die dritte Frage sagt nicht, wovon die Rede ist - "sie" und "dort"
    # ergeben sich nur aus den beiden Antworten davor.
    dritte = lauf2[2]["antwort"].lower()
    pruefe(any(w in dritte for w in ("forelle", "mykiss", "ausgesetzt",
                                     "eingefuehrt", "eingeführt", "besetzt",
                                     "heimisch", "nordamerika")),
           "dritte Frage bleibt beim Thema", lauf2[2]["antwort"][:110])

print(f"\n  {fehler} Fehler"
      + (f", {uebersprungen} übersprungen" if uebersprungen else ""))
raise SystemExit(1 if fehler else 0)
