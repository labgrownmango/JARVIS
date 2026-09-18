"""Entscheidet das Modell selbst, wann ein Agent losgeschickt wird -
und wann eben nicht?"""
import httpx

from jarvis import config, tools

H = {"Authorization": f"Bearer {config.API_KEY}"}
MODELL = config.MODELS[0]

SOLL_DELEGIEREN = [
    "Kuemmer dich mal in Ruhe darum, das Wetter der naechsten drei Tage fuer "
    "Berlin, Hamburg, Muenchen und Koeln zu vergleichen.",
    "Recherchier mir bitte in aller Ruhe, was heute in den Nachrichten zu "
    "Energiepolitik steht, und fass es zusammen.",
    "Sammle mal alle Systemwerte, das Wetter und die Schlagzeilen und mach "
    "mir daraus einen Lagebericht. Hat Zeit.",
]

SOLL_DIREKT = [
    "Wie spaet ist es?",
    "Wie geht es dir?",
    "Wie ist das Wetter?",
    "Mach mal lauter.",
]


def frage(text: str) -> tuple[str, str]:
    """Gibt (Werkzeugname, Antworttext) zurueck."""
    r = httpx.post(f"{config.BASE_URL}/chat/completions", headers=H, timeout=180,
                   json={"model": MODELL, "max_tokens": 300,
                         "tools": tools.SCHEMA,
                         "messages": [
                             {"role": "system", "content": config.SYSTEM_PROMPT},
                             {"role": "user", "content": text}]})
    if r.status_code != 200:
        return f"[{r.status_code}]", ""
    m = r.json()["choices"][0]["message"]
    aufrufe = m.get("tool_calls") or []
    namen = ", ".join(a["function"]["name"] for a in aufrufe)
    return namen or "(keins)", (m.get("content") or "").strip()[:70]


print(f"Modell: {MODELL}\n")
fehler = 0

print("=== Diese Aufgaben gehoeren an einen Agenten ===")
for text in SOLL_DELEGIEREN:
    werkzeug, _ = frage(text)
    ok = "start_agent" in werkzeug
    fehler += not ok
    print(f"  {'ok    ' if ok else 'NEIN  '} {werkzeug:20} {text[:52]}")

print("\n=== Diese soll Jarvis selbst beantworten ===")
for text in SOLL_DIREKT:
    werkzeug, antwort = frage(text)
    ok = "start_agent" not in werkzeug
    fehler += not ok
    print(f"  {'ok    ' if ok else 'NEIN  '} {werkzeug:20} {text[:30]:32} "
          f"{antwort[:30]}")

print(f"\n{fehler} Fehlentscheidungen von "
      f"{len(SOLL_DELEGIEREN) + len(SOLL_DIREKT)}")
