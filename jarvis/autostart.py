"""Autostart: Jarvis ist da, wenn Windows hochfährt.

Im Film startet niemand Jarvis - er ist einfach da. Das ist der Unterschied
zwischen einem Programm und einem Assistenten.

Gearbeitet wird mit einer Verknüpfung im Autostart-Ordner des Benutzers, nicht
mit einem Registrierungseintrag: sie ist sichtbar, lässt sich von Hand
löschen, und braucht keine Administratorrechte.

Zwei Betriebsarten:
  oberflaeche  der Webserver läuft still im Hintergrund; du öffnest die Seite,
               wenn du ihn brauchst. Kein Fenster, kein Mikrofon.
  weckwort     er hört dauerhaft auf "Hey Jarvis". Braucht ein Fenster und
               belegt das Mikrofon.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from . import config

NAME = "Jarvis.lnk"


def ordner() -> Path:
    return (Path(os.environ["APPDATA"])
            / "Microsoft/Windows/Start Menu/Programs/Startup")


def pfad() -> Path:
    return ordner() / NAME


def _pythonw() -> str:
    """pythonw statt python: startet ohne Konsolenfenster."""
    ohne_fenster = Path(sys.executable).with_name("pythonw.exe")
    return str(ohne_fenster if ohne_fenster.exists() else sys.executable)


def zustand() -> dict:
    verknuepfung = pfad()
    if not verknuepfung.exists():
        return {"an": False, "art": "", "ziel": ""}
    art = "weckwort" if "weckwort" in _ziel_lesen(verknuepfung) else "oberflaeche"
    return {"an": True, "art": art, "ziel": str(verknuepfung)}


def _ziel_lesen(verknuepfung: Path) -> str:
    try:
        import pythoncom
        from win32com.shell import shell

        link = pythoncom.CoCreateInstance(
            shell.CLSID_ShellLink, None, pythoncom.CLSCTX_INPROC_SERVER,
            shell.IID_IShellLink)
        link.QueryInterface(pythoncom.IID_IPersistFile).Load(str(verknuepfung))
        return f"{link.GetPath(0)[0]} {link.GetArguments()}"
    except Exception:
        return ""


def einschalten(art: str = "oberflaeche") -> str:
    """Legt die Verknüpfung an. art: oberflaeche | weckwort"""
    try:
        import pythoncom
        from win32com.shell import shell
    except ImportError:
        return "pywin32 fehlt - ohne das kann ich keine Verknüpfung anlegen."

    if art not in ("oberflaeche", "weckwort"):
        return f"'{art}' kenne ich nicht. Möglich: oberflaeche, weckwort."

    if art == "weckwort":
        # Braucht ein Fenster, weil dort die Rückfragen erscheinen
        programm = str(Path(sys.executable))
        argumente = "-m jarvis.main --weckwort"
        stil = 7                      # minimiert starten
    else:
        programm = _pythonw()         # still, ohne Fenster
        argumente = "-m jarvis.web"
        stil = 7

    try:
        ordner().mkdir(parents=True, exist_ok=True)
        link = pythoncom.CoCreateInstance(
            shell.CLSID_ShellLink, None, pythoncom.CLSCTX_INPROC_SERVER,
            shell.IID_IShellLink)
        link.SetPath(programm)
        link.SetArguments(argumente)
        link.SetWorkingDirectory(str(config.ROOT))
        link.SetDescription("JARVIS")
        link.SetShowCmd(stil)
        link.QueryInterface(pythoncom.IID_IPersistFile).Save(str(pfad()), 0)
    except Exception as exc:
        return f"Konnte den Autostart nicht einrichten: {exc}"

    wie = ("still im Hintergrund, erreichbar unter "
           "http://127.0.0.1:8765" if art == "oberflaeche"
           else "mit Weckwort, minimiert")
    return f"Autostart eingerichtet - {wie}. Gilt ab dem nächsten Anmelden."


def desktop_verknuepfung() -> str:
    """Ein Symbol auf dem Desktop, das die Oberfläche öffnet.

    Ohne das müsste man sich http://127.0.0.1:8765 merken - das tut niemand.
    """
    try:
        import pythoncom
        from win32com.shell import shell
    except ImportError:
        return "pywin32 fehlt."

    desktop = Path(os.environ["USERPROFILE"]) / "Desktop"
    ziel = desktop / "Jarvis öffnen.lnk"
    try:
        link = pythoncom.CoCreateInstance(
            shell.CLSID_ShellLink, None, pythoncom.CLSCTX_INPROC_SERVER,
            shell.IID_IShellLink)
        # Der Browser oeffnet die Seite; laeuft der Server nicht, startet ihn
        # der Autostart oder "Jarvis Oberflaeche.bat"
        link.SetPath(str(config.ROOT / "Jarvis Oberflaeche.bat"))
        link.SetWorkingDirectory(str(config.ROOT))
        link.SetDescription("JARVIS - Oberfläche öffnen")
        link.SetIconLocation(
            str(Path(os.environ["SYSTEMROOT"]) / "System32/shell32.dll"), 13)
        link.QueryInterface(pythoncom.IID_IPersistFile).Save(str(ziel), 0)
    except Exception as exc:
        return f"Konnte die Verknüpfung nicht anlegen: {exc}"
    return f"Verknüpfung liegt auf dem Desktop: {ziel.name}"


def kurzname(an: bool = True) -> str:
    """Traegt "jarvis" in die hosts-Datei ein - dann geht http://jarvis:8765.

    Das ist eine systemweite Datei. Sie wird nur um eine Zeile ergaenzt und
    laesst sich genauso wieder entfernen.
    """
    pfad_hosts = Path(os.environ["SYSTEMROOT"]) / "System32/drivers/etc/hosts"
    marke = "# JARVIS"
    try:
        zeilen = pfad_hosts.read_text(encoding="utf-8").splitlines()
    except Exception as exc:
        return f"hosts-Datei nicht lesbar: {exc}"

    ohne = [z for z in zeilen if marke not in z]
    if an:
        ohne.append(f"127.0.0.1 jarvis          {marke}")
    try:
        pfad_hosts.write_text("\n".join(ohne) + "\n", encoding="utf-8")
    except PermissionError:
        return ("Dafür fehlen die Rechte - die hosts-Datei gehört Windows. "
                "Mit Administratorrechten ginge es.")
    except Exception as exc:
        return f"Konnte die hosts-Datei nicht ändern: {exc}"
    return ("Kurzname eingetragen: http://jarvis:8765 funktioniert jetzt."
            if an else "Kurzname entfernt.")


def ausschalten() -> str:
    verknuepfung = pfad()
    if not verknuepfung.exists():
        return "Der Autostart war gar nicht eingerichtet."
    try:
        verknuepfung.unlink()
    except OSError as exc:
        return f"Konnte die Verknüpfung nicht löschen: {exc}"
    return "Autostart abgeschaltet."
