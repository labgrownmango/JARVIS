"""Grenzt ein, woran der Zugriff scheitert. Gibt den Key nie aus."""
import httpx

from jarvis import config

H = {"Authorization": f"Bearer {config.API_KEY}"}

r = httpx.get(f"{config.BASE_URL}/models", headers=H, timeout=30)
print(f"Key-Laenge {len(config.API_KEY)} | GET /models -> {r.status_code}")
if r.status_code != 200:
    raise SystemExit(r.text[:300])

alle = sorted(m["id"] for m in r.json().get("data", []))
print(f"{len(alle)} Modelle sichtbar")
print("Kimi:", [m for m in alle if "kimi" in m.lower()], "\n")

kandidaten = ["moonshotai/kimi-k3"] + [
    m for m in alle
    if any(w in m.lower() for w in ("gemma", "nemotron", "llama", "qwen", "deepseek"))
][:8]

print(f"{'Modell':44} {'Code':5} Antwort")
print("-" * 82)
erfolg = []
for modell in kandidaten:
    try:
        r = httpx.post(f"{config.BASE_URL}/chat/completions", headers=H, json={
            "model": modell, "max_tokens": 8,
            "messages": [{"role": "user", "content": "Antworte nur mit: ok"}]},
            timeout=90)
        if r.status_code == 200:
            antwort = r.json()["choices"][0]["message"]["content"].strip()[:30]
            erfolg.append(modell)
        else:
            antwort = r.json().get("title", r.text[:50])
    except Exception as exc:
        r, antwort = None, str(exc)[:50]
    code = r.status_code if r is not None else "---"
    print(f"{modell:44} {code:<5} {antwort}")

print()
if erfolg:
    print("Das Konto kann rechnen - bewiesen durch:", erfolg[0])
    print("K3 mit 429 heißt dann: das Modell ist ausgelastet, nicht dein Key.")
else:
    print("Kein einziges Modell lieferte 200 - dann liegt es am Konto.")
