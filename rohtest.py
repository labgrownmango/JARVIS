"""Zeigt die unbearbeitete Antwort des Modells - setzt es die <en>-Markierung?"""
import httpx

from jarvis import config

FRAGEN = [
    "Wie sagt man 'Guten Morgen' auf Englisch?",
    "Wie heisst der Menuepunkt zum Speichern unter in Word?",
    "Zitier mir einen Satz von Tony Stark.",
]

H = {"Authorization": f"Bearer {config.API_KEY}"}
modell = config.MODELS[0]
print(f"Modell: {modell}\n")

for frage in FRAGEN:
    try:
        r = httpx.post(f"{config.BASE_URL}/chat/completions", headers=H, json={
            "model": modell, "max_tokens": 200,
            "messages": [{"role": "system", "content": config.SYSTEM_PROMPT},
                         {"role": "user", "content": frage}]}, timeout=120)
        if r.status_code != 200:
            print(f"  {frage}\n  -> {r.status_code} {r.json().get('title','')}\n")
            continue
        roh = (r.json()["choices"][0]["message"].get("content") or "").strip()
    except Exception as exc:
        print(f"  {frage}\n  -> {type(exc).__name__}\n")
        continue

    markiert = "<en>" in roh
    print(f"  FRAGE : {frage}")
    print(f"  ROH   : {roh[:160]}")
    print(f"  Markierung gesetzt: {'JA' if markiert else 'nein - Wortliste springt ein'}\n")
