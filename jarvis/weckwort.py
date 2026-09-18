"""Das Weckwort: "Hey Jarvis" - und er hört zu.

Der Unterschied zu allem anderen: hier läuft dauerhaft etwas mit. Deshalb ist
das Verfahren zweistufig.

Stufe eins ist ein winziges Netz (openWakeWord, wenige Megabyte), das nichts
anderes kann, als auf ein einziges Wort zu horchen. Es bekommt achtzig
Millisekunden Ton am Stück und sagt nur: war es das Wort, ja oder nein. Das
kostet ein paar Prozent eines Kerns.

Erst wenn es anschlägt, wird Stufe zwei geweckt - die große Spracherkennung,
die dann den eigentlichen Satz versteht. Sie liefe sonst dauerhaft mit 700 MB
im Speicher, und der Ton müsste ständig durch ein großes Modell.

Nichts davon verlässt den Rechner.
"""
from __future__ import annotations

import threading
import time

from . import config

ABTASTRATE = 16_000
BLOCK = 1280            # 80 ms - das erwartet openWakeWord


class Weckwort:
    def __init__(self, wort: str = "", schwelle: float = 0.0) -> None:
        self.wort = wort or config.WECKWORT
        self.schwelle = schwelle or config.WECKWORT_SCHWELLE
        self.laeuft = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.modell = None
        self.letzte_erkennung = 0.0

    def _laden(self) -> None:
        from openwakeword.model import Model

        self.modell = Model(wakeword_models=[self.wort],
                            inference_framework="onnx")

    def horchen(self, bei_weckwort, bei_pegel=None) -> None:
        """Blockiert und ruft bei_weckwort() bei jedem Treffer auf.

        bei_pegel bekommt laufend (Lautstaerke, bestes Weckwort-Ergebnis).
        Ohne das weiss niemand, ob ueberhaupt Ton ankommt: "Weckwort bereit"
        stand im Protokoll, waehrend das Mikrofon stumm war, und es sah
        genauso aus wie ein funktionierendes.
        """
        import numpy as np
        import sounddevice as sd

        if self.modell is None:
            self._laden()

        self.laeuft = True
        self._stop.clear()
        with sd.InputStream(samplerate=ABTASTRATE, channels=1, dtype="int16",
                            blocksize=BLOCK, device=config.MIKROFON or None
                            ) as strom:
            while not self._stop.is_set():
                daten, _ueberlauf = strom.read(BLOCK)
                welle = np.squeeze(daten)
                treffer = self.modell.predict(welle)
                wert = max(treffer.values()) if treffer else 0.0

                if bei_pegel is not None:
                    # Effektivwert, bezogen auf die Vollaussteuerung von
                    # int16 - eine Zahl zwischen 0 und 1.
                    gleit = welle.astype(np.float32) / 32768.0
                    lautstaerke = float(np.sqrt(np.mean(gleit ** 2)))
                    bei_pegel(lautstaerke, float(wert))

                # Eine Sperre danach: ein gesprochenes Wort schlaegt sonst
                # mehrmals hintereinander an
                if (wert > self.schwelle
                        and time.monotonic() - self.letzte_erkennung > 3):
                    self.letzte_erkennung = time.monotonic()
                    self.modell.reset()
                    bei_weckwort(wert)
        self.laeuft = False

    def im_hintergrund(self, bei_weckwort, bei_pegel=None) -> None:
        self._thread = threading.Thread(
            target=self.horchen, args=(bei_weckwort, bei_pegel), daemon=True,
            name="Weckwort")
        self._thread.start()

    def anhalten(self) -> None:
        self._stop.set()


def _modelldateien(wort: str) -> tuple[list[str], str]:
    """Welche Modelldateien fehlen - und wo sie hingehoeren.

    openwakeword bringt seine Modelle nicht im Paket mit, sondern laedt sie
    beim ersten Gebrauch nach. Auf einem frisch aufgesetzten Rechner ist der
    Ordner deshalb leer, und der Fehler heisst dann "NO_SUCHFILE" - was
    nach einem kaputten Paket aussieht und keines ist.
    """
    from pathlib import Path

    import openwakeword

    ordner = Path(openwakeword.__file__).parent / "resources" / "models"
    if not ordner.exists():
        return ["(der ganze Modellordner)"], str(ordner)

    vorhanden = {p.name for p in ordner.glob("*")}
    fehlend = []
    # Das Weckwort selbst - die Versionsnummer im Dateinamen kann sich
    # aendern, deshalb nach dem Anfang suchen.
    if not any(n.startswith(wort) for n in vorhanden):
        fehlend.append(f"{wort}_v0.1.onnx")
    # Ohne diese beiden laeuft gar kein Weckwort, egal welches.
    for grundlage in ("melspectrogram", "embedding_model"):
        if not any(n.startswith(grundlage) for n in vorhanden):
            fehlend.append(f"{grundlage}.onnx")
    return fehlend, str(ordner)


def verfuegbar() -> tuple[bool, str]:
    """Laesst sich das Weckwort ueberhaupt benutzen?

    Die Meldung muss die richtige Ursache nennen. "Nachinstallieren mit pip
    install openwakeword" war lange die einzige Antwort - und auf einem
    zweiten Rechner falsch: dort WAR es installiert, aber Windows Smart App
    Control blockierte eine DLL daraus. Wer der Meldung folgt, installiert
    ein vorhandenes Paket noch einmal und wundert sich, dass es nichts
    aendert.

    Inzwischen ein vierter Fall, gemeldet vom zweiten Rechner: Paket da,
    Import in Ordnung, aber die Modelldateien fehlen. Das trifft jeden
    frisch aufgesetzten Rechner.
    """
    try:
        import openwakeword  # noqa: F401
    except ImportError as fehler:
        wortlaut = str(fehler)
        if "DLL load failed" in wortlaut:
            return False, (
                "openwakeword ist installiert, aber Windows laesst eine "
                "seiner Programmbibliotheken nicht laufen: "
                f"{wortlaut[:120]}. Das ist kein Paketproblem - meist "
                "blockiert Smart App Control oder der Virenschutz die DLL. "
                "Nachinstallieren hilft dagegen nicht.")
        if "No module named" in wortlaut:
            return False, ("openwakeword fehlt - nachinstallieren mit "
                           "pip install openwakeword")
        return False, f"openwakeword laesst sich nicht laden: {wortlaut[:140]}"

    # Paket da, Import in Ordnung - aber liegen die Modelle auch?
    # openwakeword bringt sie nicht mit, sondern laedt sie beim ersten
    # Gebrauch nach. Fehlen sie, meldet es "NO_SUCHFILE", und das klingt
    # nach einem kaputten Paket.
    #
    # Jarvis laedt hier NICHTS von selbst nach - das ist so verabredet und
    # bleibt so. Die Meldung sagt dem Menschen, was er einmal von Hand
    # aufrufen kann; die Entscheidung bleibt bei ihm.
    try:
        fehlend, ordner = _modelldateien(config.WECKWORT)
    except Exception as exc:
        return False, f"Modellordner nicht lesbar: {type(exc).__name__}: {exc}"
    if fehlend:
        return False, (
            f"openwakeword ist installiert, aber die Modelldateien fehlen: "
            f"{', '.join(fehlend)}. Sie gehoeren nach {ordner}. "
            f"Einmalig holen laesst sie sich mit: "
            f"python -c \"from openwakeword.utils import download_models; "
            f"download_models()\" - das laedt aus dem Netz, deshalb macht "
            f"Jarvis es nicht von selbst.")

    try:
        import sounddevice as sd
        mikros = [g for g in sd.query_devices() if g["max_input_channels"] > 0]
        if not mikros:
            return False, "kein Mikrofon gefunden"
    except Exception as exc:
        return False, f"Mikrofon nicht ansprechbar: {exc}"
    return True, ""
