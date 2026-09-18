"""Wie schnell merkt Jarvis, dass jemand ausgeredet hat?

Zwei gemessene Aergernisse:

  1. Nach JEDER Aeusserung wurden 1,2 Sekunden Stille abgewartet - auch
     nach "Hallo?". Das ist laenger als das Wort selbst, und die Antwort
     fuehlt sich traege an, obwohl nichts langsam ist.
  2. Sprach niemand, lief das Mikrofon die vollen zwanzig Sekunden des
     Zeitlimits weiter, bevor "nichts verstanden" kam.

Geprueft wird ohne Mikrofon: das Aufnehmen bekommt einen erfundenen
Tonstrom untergeschoben, dann laesst sich in Bloecken nachrechnen, wann
abgebrochen wird. Kein Geraet, keine Wartezeit, jedes Mal dasselbe
Ergebnis.
"""
import numpy as np

from jarvis import config
from jarvis.voice import Ears

fehler = 0
RATE = 16000
BLOCK = 1024
PRO_SEKUNDE = RATE / BLOCK


def pruefe(bedingung: bool, text: str, zusatz: str = "") -> None:
    global fehler
    fehler += not bedingung
    print(f"  {'ok    ' if bedingung else 'FEHLER'} {text}")
    if not bedingung and zusatz:
        print(f"         {zusatz}")


class Tonstrom:
    """Spielt eine vorgegebene Folge aus Sprache und Stille ab."""

    def __init__(self, muster: list[tuple[str, float]]):
        self.bloecke = []
        for art, sekunden in muster:
            anzahl = int(sekunden * PRO_SEKUNDE)
            wert = 0.2 if art == "laut" else 0.0
            for _ in range(anzahl):
                self.bloecke.append(
                    np.full((BLOCK, 1), wert, dtype="float32"))
        self.gelesen = 0

    def read(self, _anzahl):
        if self.gelesen < len(self.bloecke):
            block = self.bloecke[self.gelesen]
        else:
            block = np.zeros((BLOCK, 1), dtype="float32")   # danach Stille
        self.gelesen += 1
        return block, False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class SdAttrappe:
    def __init__(self, strom):
        self.strom = strom

    def InputStream(self, **_kw):
        return self.strom


def aufnehmen(muster) -> tuple[float, int]:
    """Gibt (Sekunden bis zum Abbruch, Laenge der Aufnahme) zurueck."""
    ohren = Ears.__new__(Ears)
    ohren.np = np
    strom = Tonstrom(muster)
    ohren.sd = SdAttrappe(strom)
    ohren.SAMPLE_RATE = RATE
    daten = ohren.record_until_silence()
    return strom.gelesen / PRO_SEKUNDE, len(daten)


print("=== Kurzes Wort: schnell fertig ===")
# "Hallo?" - ein halbe Sekunde Sprache, dann Stille.
dauer, laenge = aufnehmen([("still", 0.3), ("laut", 0.5), ("still", 3.0)])
print(f"         Abbruch nach {dauer:.2f}s Aufnahme")
pruefe(laenge > 0, "etwas aufgenommen")
pruefe(dauer < 1.4,
       f"nach kurzem Wort schnell fertig ({dauer:.2f}s)",
       "frueher waren es 1,2s Stille PLUS die Sprache")

print("\n=== Langer Satz: Denkpause wird nicht abgeschnitten ===")
# Drei Sekunden Sprache, dann eine Pause von 0,7s mitten im Satz, dann
# weitere Sprache. Die Pause darf NICHT als Ende gelten.
dauer, laenge = aufnehmen([("laut", 3.0), ("still", 0.7), ("laut", 1.5),
                           ("still", 3.0)])
print(f"         Abbruch nach {dauer:.2f}s Aufnahme")
pruefe(dauer > 5.0,
       f"die Denkpause unterbricht nicht ({dauer:.2f}s)",
       "bei 0,45s Fenster waere hier mitten im Satz Schluss")

print("\n=== Wer nicht spricht, wartet nicht zwanzig Sekunden ===")
dauer, laenge = aufnehmen([("still", 20.0)])
print(f"         Abbruch nach {dauer:.2f}s Aufnahme")
pruefe(laenge == 0, "nichts aufgenommen")
pruefe(dauer < config.STT_VORLAUF + 0.5,
       f"gibt nach {dauer:.2f}s auf (Vorlauf {config.STT_VORLAUF}s)",
       "frueher lief das Mikrofon die vollen 20s weiter")

print("\n=== Das Fenster waechst mit der Laenge ===")
ohren = Ears.__new__(Ears)
kurz = ohren.stille_fuer(0.5)
mittel = ohren.stille_fuer(2.0)
lang = ohren.stille_fuer(5.0)
print(f"         0,5s Sprache -> {kurz:.2f}s   "
      f"2s -> {mittel:.2f}s   5s -> {lang:.2f}s")
pruefe(kurz == config.STT_STILLE_KURZ, "kurz bleibt kurz")
pruefe(lang == config.STT_STILLE_LANG, "lang bleibt lang")
pruefe(kurz < mittel < lang, "dazwischen waechst es gleichmaessig")

print("\n=== Die Werte lassen sich einstellen ===")
alt = config.STT_STILLE_KURZ
config.STT_STILLE_KURZ = 0.2
pruefe(ohren.stille_fuer(0.5) == 0.2, "ueber die .env aenderbar")
config.STT_STILLE_KURZ = alt

print(f"\n  {fehler} Fehler")
raise SystemExit(1 if fehler else 0)
