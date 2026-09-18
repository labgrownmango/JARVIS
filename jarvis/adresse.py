"""Unter welcher Adresse ist die Oberflaeche erreichbar?

Gebaut, weil "Jarvis Oberflaeche.bat" die Zahl 8765 dreimal fest eingetippt
hatte. Inzwischen ist 80 die Vorgabe und 8765 nur noch der Ausweichport -
also griff die Laufpruefung ins Leere, der Browser oeffnete einen toten
Port, und danach startete ein zweiter Server daneben.

Eine feste Zahl in einer .bat ist immer falsch, sobald sie sich woanders
aendert. Und ein Pflaster (80 statt 8765 eintippen) verschiebt den Fehler
nur: sobald 80 belegt ist und Jarvis auf 8765 ausweicht, stimmt die neue
Zahl auch nicht mehr.

Deshalb wird hier GEFRAGT statt geraten - und zwar in der Reihenfolge, die
der Wirklichkeit entspricht: erst nachsehen, wo wirklich einer lauscht,
dann erst raten, wo einer landen wuerde.

Aufruf von aussen:
    python -m jarvis.adresse             gibt die Adresse aus
    python -m jarvis.adresse --port      gibt nur die Portnummer aus
    python -m jarvis.adresse --zustand   "laeuft <adresse>" oder "neu <adresse>"

Der Rueckgabewert sagt dasselbe (0 = laeuft schon), aber VERLASS DICH NICHT
DARAUF in einer .bat: cmd reicht den Rueckgabewert eines Befehls aus
`for /f ... in (`...`)` nicht verlaesslich nach aussen. Das Symptom waere
still und haesslich - der Browser geht auf, und ein zweiter Server startet
trotzdem daneben. Deshalb gibt es --zustand: da steht die Auskunft in der
AUSGABE, und die kommt immer an.
"""
from __future__ import annotations

import socket

from . import config


def _antwortet(port: int, sekunden: float = 0.6) -> bool:
    """Lauscht auf diesem Port wirklich jemand?"""
    pruefer = socket.socket()
    pruefer.settimeout(sekunden)
    try:
        return pruefer.connect_ex(("127.0.0.1", port)) == 0
    except OSError:
        return False
    finally:
        pruefer.close()


def laufender_port() -> int | None:
    """Auf welchem Port laeuft Jarvis GERADE? None, wenn keiner laeuft."""
    for port in (config.WEB_PORT, config.WEB_PORT_AUSWEICH):
        if _antwortet(port):
            return port
    return None


def kuenftiger_port() -> int:
    """Auf welchem Port wuerde er starten, wenn man ihn jetzt startet?"""
    from .web import _freier_port

    return _freier_port(config.WEB_PORT)


def adresse(port: int | None = None, fuer_diesen_rechner: bool = True) -> str:
    """Die Adresse zum Oeffnen im Browser.

    fuer_diesen_rechner=True gibt 127.0.0.1 zurueck, nicht den Kurznamen.
    Das ist Absicht: "http://jarvis" steht in der hosts-Datei DIESES
    Rechners. Auf einem zweiten Rechner zeigt derselbe Name entweder
    nirgendwohin - oder, wenn "jarvis" ein Tailscale-Name ist, auf einen
    ganz anderen Computer. Eine .bat, die den Browser oeffnet, laeuft immer
    dort, wo auch der Server laeuft; 127.0.0.1 stimmt dort immer.
    """
    if port is None:
        port = laufender_port() or kuenftiger_port()
    name = "127.0.0.1"
    if not fuer_diesen_rechner:
        from .web import _kurzname_gesetzt

        if _kurzname_gesetzt():
            name = config.WEB_NAME
    nummer = "" if port == 80 else f":{port}"
    return f"http://{name}{nummer}"


# Browser, die wir ansprechen koennen, mit ihrem Prozessnamen.
_BROWSER = (
    ("brave.exe", "brave"),
    ("firefox.exe", "firefox"),
    ("chrome.exe", "chrome"),
    ("msedge.exe", "msedge"),
)


def offener_browser() -> str | None:
    """Welcher Browser laeuft gerade? Gibt den Programmnamen zurueck.

    Gedacht fuer die Startdatei: sie oeffnete die Oberflaeche immer im
    Standardbrowser, also in Edge - auch wenn daneben ein Brave mit allen
    Anmeldungen offenstand. Wer Brave benutzt, will die Seite dort haben,
    nicht in einem zweiten Browser.

    Laeuft keiner, wird None zurueckgegeben - dann entscheidet Windows,
    und das ist auch richtig so.
    """
    try:
        import psutil
    except ImportError:
        return None
    laufend = set()
    try:
        for prozess in psutil.process_iter(["name"]):
            name = (prozess.info.get("name") or "").lower()
            if name:
                laufend.add(name)
    except Exception:
        return None
    for prozessname, programm in _BROWSER:
        if prozessname in laufend:
            return programm
    return None


def warten_bis_da(sekunden: float = 25.0) -> bool:
    """Wartet, bis der Server antwortet. True, wenn er kam.

    Die Startdatei oeffnete den Browser SOFORT und startete den Server erst
    danach. Der Browser traf also auf einen toten Port, zeigte einen Fehler,
    und nach einmal Aktualisieren ging es - das war ein Teil des "mal geht
    es, mal nicht".
    """
    import time

    ende = time.time() + sekunden
    while time.time() < ende:
        if laufender_port() is not None:
            return True
        time.sleep(0.4)
    return False


def oeffnen(ziel: str = "") -> str:
    """Die Oberflaeche im passenden Browser oeffnen.

    Bevorzugt einen bereits laufenden Browser, sonst den Standardbrowser.
    """
    import os
    import shutil
    import subprocess

    ziel = ziel or adresse()
    programm = offener_browser()
    if programm:
        pfad = shutil.which(programm)
        if pfad:
            try:
                subprocess.Popen([pfad, ziel])
                return f"{programm} ({ziel})"
            except Exception:
                pass
    try:
        os.startfile(ziel)
        return f"Standardbrowser ({ziel})"
    except Exception as exc:
        return f"konnte nicht oeffnen: {exc}"


def main() -> int:
    import sys

    laeuft = laufender_port()
    port = laeuft if laeuft is not None else kuenftiger_port()

    if "--oeffnen" in sys.argv:
        if "--warten" in sys.argv and laeuft is None:
            if not warten_bis_da():
                print("Der Server kam nicht hoch - nichts geoeffnet.")
                return 1
            port = laufender_port() or port
        print(oeffnen(adresse(port)))
    elif "--port" in sys.argv:
        print(port)
    elif "--zustand" in sys.argv:
        # Zustand UND Adresse in einer Zeile, durch ein Leerzeichen getrennt.
        # Eine .bat liest das mit "tokens=1,2" und braucht kein errorlevel.
        print(f"{'laeuft' if laeuft is not None else 'neu'} {adresse(port)}")
    else:
        print(adresse(port))
    return 0 if laeuft is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
