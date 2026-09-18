"""Wie lange dauert der lokale Teil nach dem Weckwort - ohne API?"""
import io
import time
import wave

import numpy as np

from jarvis import config, voice, weckwort

SATZ = "Hey Jarvis, wie spaet ist es?"


def als_pcm(text: str) -> np.ndarray:
    daten = voice.zu_wav(text)
    with wave.open(io.BytesIO(daten)) as d:
        roh = np.frombuffer(d.readframes(d.getnframes()), dtype=np.int16)
        rate = d.getframerate()
    return np.interp(np.arange(0, len(roh), rate / 16000),
                     np.arange(len(roh)), roh).astype(np.int16)


print("=== Erkennung des Weckworts ===")
w = weckwort.Weckwort()
w._laden()
pcm = np.concatenate([als_pcm(SATZ), np.zeros(16000, dtype=np.int16)])

w.modell.reset()
start = time.perf_counter()
erkannt_nach = None
for i in range(0, len(pcm) - weckwort.BLOCK, weckwort.BLOCK):
    ergebnis = w.modell.predict(pcm[i:i + weckwort.BLOCK])
    if max(ergebnis.values()) > w.schwelle and erkannt_nach is None:
        erkannt_nach = time.perf_counter() - start
        tonposition = i / 16000
        break
print(f"  Rechenzeit bis zum Treffer: {erkannt_nach*1000:.0f} ms")
print(f"  (im Ton lag das Wort bei Sekunde {tonposition:.1f})")

print("\n=== 'Ja?' erzeugen - der Satz, der sofort kommt ===")
for backend, stimme in (("windows", "Stefan"), ("piper", "de_DE-thorsten-medium")):
    config.TTS_BACKEND = backend
    if backend == "piper":
        config.PIPER_VOICE = stimme
        config.PIPER_MODEL = config.ROOT / "voices" / f"{stimme}.onnx"
        voice._stimmen_web.clear()
    else:
        config.WIN_STIMME = stimme
        voice._win_web = None
    voice.zu_wav("warmlaufen")          # einmal laden, dann messen
    start = time.perf_counter()
    ton = voice.zu_wav("Ja?")
    print(f"  {backend:8} {stimme:22} {(time.perf_counter()-start)*1000:6.0f} ms")

print("\n=== Deinen Satz verstehen (faster-whisper, lokal) ===")
ton = voice.zu_wav("Wie spaet ist es?")
voice.verstehen(ton)                    # einmal laden
start = time.perf_counter()
text = voice.verstehen(ton)
print(f"  {(time.perf_counter()-start)*1000:.0f} ms -> {text!r}")

print("\n  Alles davon laeuft auf diesem Rechner. Zur API geht nur die Frage.")
