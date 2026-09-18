"""Vergleicht die Stimmen sauber: nur das Erzeugen, ohne Abspielen."""
import io
import time
import wave

import numpy as np
import psutil
import sounddevice as sd

from jarvis import config, voice

SATZ = ("Guten Abend, Sir. Alle Systeme sind bereit, und das Laufwerk "
        "hat noch achtundsiebzig Gigabyte frei.")
ich = psutil.Process()


def spielen(pcm, rate):
    sd.play(pcm, rate)
    sd.wait()
    time.sleep(0.4)


print(f"{'Stimme':30} {'Erzeugen':>9} {'Tonlaenge':>10} {'Tempo':>8} {'Speicher':>9}")
print("-" * 72)

# --- Piper ---
config.TTS_BACKEND = "piper"
for stimme in ("de_DE-thorsten-medium", "de_DE-thorsten-high"):
    pfad = config.ROOT / "voices" / f"{stimme}.onnx"
    if not pfad.exists():
        continue
    config.PIPER_VOICE, config.PIPER_MODEL = stimme, pfad
    voice._stimmen_web.clear()
    vorher = ich.memory_info().rss / 1e6
    start = time.perf_counter()
    daten = voice.zu_wav(SATZ)
    dauer = time.perf_counter() - start
    speicher = ich.memory_info().rss / 1e6 - vorher

    with wave.open(io.BytesIO(daten)) as d:
        pcm = np.frombuffer(d.readframes(d.getnframes()), dtype=np.int16)
        rate = d.getframerate()
    laenge = len(pcm) / rate
    print(f"{'Piper ' + stimme[6:]:30} {dauer:8.2f}s {laenge:9.1f}s "
          f"{laenge/dauer:7.1f}x {speicher:8.0f} MB")
    spielen(pcm, rate)

# --- Windows ---
sprecher = voice.WindowsSpeaker.__new__(voice.WindowsSpeaker)
sprecher._setup()
for name in ("Stefan", "Katja"):
    config.WIN_STIMME = name
    sprecher._setup()
    vorher = ich.memory_info().rss / 1e6
    start = time.perf_counter()
    roh, rate = sprecher._erzeugen(SATZ, "de")
    dauer = time.perf_counter() - start
    speicher = ich.memory_info().rss / 1e6 - vorher
    pcm = np.frombuffer(roh, dtype=np.int16)
    laenge = len(pcm) / rate
    print(f"{'Windows ' + name:30} {dauer:8.2f}s {laenge:9.1f}s "
          f"{laenge/dauer:7.1f}x {speicher:8.0f} MB")
    spielen(pcm, rate)

print("\nTempo: wie viel schneller als Echtzeit erzeugt wird.")
print("Unter 1x kaeme Jarvis mit dem Reden nicht hinterher.")
