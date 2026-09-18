"""Prueft die Installation, ohne die API zu belasten.

    .venv\\Scripts\\python.exe selbsttest.py
"""
from jarvis import config, tools
import jarvis.voice, jarvis.brain, jarvis.main   # nur Import-Check  # noqa: F401

print("Imports OK | Modell:", config.MODEL, "|", config.BASE_URL)
print("Key vorhanden:", "ja" if config.API_KEY else "NEIN - .env ausfuellen")
print("Zeit    :", tools.get_time())
print("System  :", tools.system_status())
print("Sperre  :", tools.open_app("virus.exe"))
print("Merken  :", tools.remember("Selbsttest"))
print("Abruf   :", tools.recall("Selbsttest"))
print("Werkzeug:", [s["function"]["name"] for s in tools.SCHEMA])

print("Piper   :", "vorhanden" if config.PIPER_MODEL.exists()
      else f"FEHLT ({config.PIPER_MODEL.name}) - siehe README, Abschnitt Stimme")
try:
    import win32com.client
    voices = win32com.client.Dispatch("SAPI.SpVoice").GetVoices()
    print("SAPI    :", [v.GetDescription() for v in voices])
except Exception as exc:
    print("SAPI    : FEHLER", exc)

try:
    import sounddevice as sd
    mics = [d["name"] for d in sd.query_devices() if d["max_input_channels"] > 0]
    print("Mikrofon:", mics[:5] or "KEINES GEFUNDEN")
except Exception as exc:
    print("Mikrofon: FEHLER", exc)
