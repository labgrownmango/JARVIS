"""Prüft den Stimmwechsel über /stimme - beide Wege."""
from jarvis import commands, config, voice


class StummerSprecher:
    enabled = True

    def say(self, text, sprache=None): ...
    def say_teile(self, teile): ...
    def wait(self, timeout=0): ...
    def verstummen(self): ...


class FakeBrain:
    history = []
    model = "x"
    rangliste = []
    ping = []

    def reset(self): ...
    def pingen(self): return []


ctx = commands.Kontext(FakeBrain(), StummerSprecher(), False)

print("=== Übersicht ===")
print(commands.ausfuehren("/stimme", ctx))

print("\n=== Auf eine Windows-Stimme wechseln ===")
print(" ", commands.ausfuehren("/stimme Katja", ctx))
print(f"  Backend jetzt: {config.TTS_BACKEND}, Stimme: {config.WIN_STIMME}")
assert config.TTS_BACKEND == "windows"

print("\n=== Erzeugt die Weboberfläche jetzt auch damit? ===")
import time
start = time.perf_counter()
ton = voice.zu_wav("Kurzer Satz zur Probe.")
print(f"  {len(ton)//1024} KB in {time.perf_counter()-start:.2f}s")
assert ton

print("\n=== Zurück auf Piper ===")
print(" ", commands.ausfuehren("/stimme thorsten-medium", ctx))
print(f"  Backend jetzt: {config.TTS_BACKEND}, Stimme: {config.PIPER_VOICE}")
assert config.TTS_BACKEND == "piper"

start = time.perf_counter()
ton = voice.zu_wav("Kurzer Satz zur Probe.")
print(f"  {len(ton)//1024} KB in {time.perf_counter()-start:.2f}s")

print("\n=== Unbekannte Stimme ===")
print(" ", commands.ausfuehren("/stimme quatschxyz", ctx)[:110])

print("\nFertig.")
