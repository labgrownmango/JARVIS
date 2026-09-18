"""Prüft das Weckwort - ohne dass jemand danebensitzen muss.

Trick: Jarvis' eigene Stimme spricht das Weckwort, die Aufnahme geht durch den
Erkenner. Das ist strenger als ein echter Sprecher, weil die Stimme nie darauf
trainiert wurde.
"""
import io
import time
import wave

import numpy as np

from jarvis import config, voice, weckwort

print("=== Ist es verfügbar? ===")
geht, grund = weckwort.verfuegbar()
print(f"  {geht}  {grund}")
assert geht

print("\n=== Erkenner laden ===")
start = time.perf_counter()
w = weckwort.Weckwort()
w._laden()
print(f"  '{w.wort}' geladen in {time.perf_counter() - start:.1f}s, "
      f"Schwelle {w.schwelle}")


def als_pcm(text: str) -> np.ndarray:
    """Text sprechen und als 16-kHz-Mono zurueckgeben."""
    daten = voice.zu_wav(text)
    with wave.open(io.BytesIO(daten)) as datei:
        roh = np.frombuffer(datei.readframes(datei.getnframes()), dtype=np.int16)
        rate = datei.getframerate()
    # openWakeWord will genau 16 kHz
    ziel = np.interp(np.arange(0, len(roh), rate / 16000),
                     np.arange(len(roh)), roh).astype(np.int16)
    return ziel


def hoechster_wert(pcm: np.ndarray) -> float:
    w.modell.reset()
    hoechst = 0.0
    for i in range(0, len(pcm) - weckwort.BLOCK, weckwort.BLOCK):
        ergebnis = w.modell.predict(pcm[i:i + weckwort.BLOCK])
        hoechst = max(hoechst, max(ergebnis.values()) if ergebnis else 0.0)
    return hoechst


def mit_nachlauf(pcm: np.ndarray, sekunden: float = 1.0) -> np.ndarray:
    """Im echten Betrieb laeuft das Mikrofon nach dem Wort weiter. Ohne
    diesen Nachlauf ist der Puffer des Erkenners noch nicht voll."""
    return np.concatenate([pcm, np.zeros(int(16000 * sekunden), dtype=np.int16)])


print("\n=== Muss anschlagen ===")
for satz in ("Hey Jarvis", "Hey Jarvis, wie spaet ist es?",
             "Hey Jarvis. Mach mal lauter."):
    ohne = hoechster_wert(als_pcm(satz))
    mit = hoechster_wert(mit_nachlauf(als_pcm(satz)))
    ok = mit > w.schwelle
    print(f"  {'ok    ' if ok else 'DANEBEN'} {mit:.2f} (ohne Nachlauf "
          f"{ohne:.2f})  {satz!r}")
    assert ok, satz

print("\n=== Darf NICHT anschlagen ===")
for satz in ("Guten Morgen, Sir.",
             "Der Arbeitsspeicher liegt bei siebzig Prozent.",
             "Hey, das ist ein ganz normaler Satz ueber das Wetter."):
    wert = hoechster_wert(als_pcm(satz))
    ok = wert <= w.schwelle
    print(f"  {'ok    ' if ok else 'FEHLALARM'} {wert:.2f}  {satz!r}")

print("\n=== Was kostet das Dauerhorchen? ===")
import psutil
ich = psutil.Process()
stille = np.zeros(weckwort.BLOCK, dtype=np.int16)
vorher = ich.memory_info().rss / 1e6
start = time.perf_counter()
runden = 250                                  # 250 x 80 ms = 20 Sekunden Ton
for _ in range(runden):
    w.modell.predict(stille)
dauer = time.perf_counter() - start
nachher = ich.memory_info().rss / 1e6
print(f"  {runden} Bloecke (= {runden*0.08:.0f}s Ton) in {dauer:.2f}s gerechnet")
print(f"  Das ist {dauer/(runden*0.08)*100:.1f} Prozent eines Kerns")
print(f"  Speicher: {vorher:.0f} -> {nachher:.0f} MB")
print("\nFertig.")
