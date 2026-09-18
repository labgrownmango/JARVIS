"""Prueft die Modelle, die antworten, auf das, was Jarvis wirklich braucht:
Deutsch, Werkzeug-Aufrufe und Tempo. Gibt den Key nie aus."""
import time

import httpx

from jarvis import config, tools

H = {"Authorization": f"Bearer {config.API_KEY}"}

KANDIDATEN = [
    "deepseek-ai/deepseek-v4-flash-0731",
    "openai/gpt-oss-20b",
    "nvidia/nemotron-3.5-lightning-30b-a3b",
    "nvidia/ising-calibration-1.5-31b",
    "meta/muse-glimmer-30b",
    "meta/llama-3.2-11b-vision-instruct",
]

# Diese Frage MUSS ein Werkzeug ausloesen - das Modell kann das Wetter nicht wissen
FRAGE = [{"role": "system", "content": config.SYSTEM_PROMPT},
         {"role": "user", "content": "Wie ist das Wetter gerade?"}]


def pruefe(modell: str) -> None:
    start = time.monotonic()
    try:
        r = httpx.post(f"{config.BASE_URL}/chat/completions", headers=H, json={
            "model": modell, "messages": FRAGE, "tools": tools.SCHEMA,
            "max_tokens": 300}, timeout=180)
    except Exception as exc:
        print(f"{modell:40} ---   {type(exc).__name__}")
        return
    dauer = time.monotonic() - start

    if r.status_code != 200:
        print(f"{modell:40} {r.status_code}   {r.json().get('title', '')}")
        return

    m = r.json()["choices"][0]["message"]
    aufrufe = m.get("tool_calls") or []
    if aufrufe:
        namen = ", ".join(a["function"]["name"] for a in aufrufe)
        print(f"{modell:40} 200   {dauer:5.1f}s  WERKZEUG: {namen}")
    else:
        text = (m.get("content") or "").strip().replace("\n", " ")[:60]
        print(f"{modell:40} 200   {dauer:5.1f}s  nur Text: {text}")


print(f"{'Modell':40} {'Code':5} {'Zeit':6}  Verhalten bei 'Wie ist das Wetter?'")
print("-" * 100)
for modell in KANDIDATEN:
    pruefe(modell)

print("\nWERKZEUG = taugt als Ersatzmodell für Jarvis.")
print("nur Text = kann keine Werkzeuge; Wetter und Nachrichten fänden nicht statt.")
