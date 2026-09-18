"""Welche kostenlose Suche funktioniert von hier aus?"""
import httpx

FRAGE = "Wer ist der aktuelle Bundeskanzler"

print("=== DuckDuckGo (ohne Schlüssel) ===")
try:
    from ddgs import DDGS

    with DDGS() as suche:
        treffer = list(suche.text(FRAGE, region="de-de", max_results=3))
    for t in treffer:
        print(f"  {t.get('title', '')[:70]}")
        print(f"    {t.get('body', '')[:100]}")
except ImportError:
    print("  ddgs fehlt noch")
except Exception as exc:
    print(f"  Fehler: {type(exc).__name__}: {exc}")

print("\n=== Wikipedia (offene Schnittstelle) ===")
try:
    r = httpx.get("https://de.wikipedia.org/w/api.php", timeout=20, params={
        "action": "query", "list": "search", "srsearch": FRAGE,
        "format": "json", "srlimit": 2})
    for t in r.json()["query"]["search"]:
        import re
        text = re.sub("<[^>]+>", "", t["snippet"])
        print(f"  {t['title']}: {text[:90]}")
except Exception as exc:
    print(f"  Fehler: {type(exc).__name__}: {exc}")
