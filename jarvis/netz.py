"""Ist ueberhaupt Internet da?

Ohne diese Unterscheidung meldet jedes Werkzeug seinen eigenen Fehler:
"DDGSException", "ConnectError", "Wetterdienst nicht erreichbar". Der Mensch
sucht dann den Fehler bei Jarvis, obwohl schlicht das WLAN weg ist.

Die Antwort wird kurz gemerkt. Ein Netzausfall dauert selten weniger als ein
paar Sekunden, und bei jedem Werkzeugaufruf neu nachzusehen kostet Zeit, die
gerade dann fehlt, wenn ohnehin nichts geht.
"""
from __future__ import annotations

import socket
import threading
import time

# Wohin geklopft wird. Absichtlich drei verschiedene Betreiber: faellt einer
# aus, heisst das noch lange nicht, dass das Internet weg ist.
_ZIELE = (("1.1.1.1", 53), ("8.8.8.8", 53), ("9.9.9.9", 53))

_MERKZEIT = 20.0          # Sekunden, die eine Antwort gilt
_schloss = threading.Lock()
_stand: tuple[float, bool] = (0.0, True)


def erreichbar(frisch: bool = False) -> bool:
    """Kommt man ins Netz? Gemerkt fuer ein paar Sekunden."""
    global _stand

    with _schloss:
        wann, antwort = _stand
        if not frisch and time.monotonic() - wann < _MERKZEIT:
            return antwort

    ergebnis = False
    for wirt, port in _ZIELE:
        try:
            with socket.create_connection((wirt, port), timeout=1.5):
                ergebnis = True
                break
        except OSError:
            continue

    with _schloss:
        _stand = (time.monotonic(), ergebnis)
    return ergebnis


def erklaerung(dienst: str, fehler: str = "") -> str:
    """Eine ehrliche Meldung statt eines Ausnahmenamens.

    Unterscheidet die beiden Faelle, die sich fuer den Menschen voellig
    verschieden anfuehlen: das Netz ist weg (sein Problem, schnell behoben)
    oder ein einzelner Dienst hakt (nicht sein Problem, nichts zu machen).
    """
    if not erreichbar():
        return ("Der Rechner ist gerade nicht im Internet - deshalb geht das "
                "nicht. Sag das klar und biete an, es spaeter zu versuchen. "
                "Was ohne Netz laeuft: nachschlagen in der Wikipedia auf der "
                "Platte, rechnen, Uhrzeit, Systemdaten, Programme, "
                "Lautstaerke, Helligkeit, Erinnerungen, Gedaechtnis.")
    zusatz = f" ({fehler})" if fehler else ""
    return (f"{dienst} antwortet gerade nicht{zusatz}, das Internet selbst "
            f"laeuft aber. Sag das so und rate, es gleich noch einmal zu "
            f"versuchen.")
