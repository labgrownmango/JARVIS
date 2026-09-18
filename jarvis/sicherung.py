"""Kopien von dem, was nicht wiederherstellbar ist.

Gedaechtnis, Gespraechsarchiv und Erinnerungen sind gewachsen, nicht erzeugt.
Geht die Datei kaputt - ein abgebrochener Schreibvorgang, ein Griff daneben -
ist das weg, und kein Neuinstallieren bringt es zurueck. Der geschriebene
Code in werkstatt/ genauso.

Was NICHT gesichert wird: die Wikipedia-Datei. Sie ist 4,2 GB gross, laesst
sich jederzeit neu laden und wuerde jede Sicherung unbenutzbar machen. Und
die .env - dort steht das Passwort im Klartext; Kopien davon zu streuen waere
das Gegenteil von Sicherheit.
"""
from __future__ import annotations

import datetime as dt
import shutil
import zipfile
from pathlib import Path

from . import config

ORDNER = config.ROOT / "data" / "sicherungen"

# Was hinein gehoert. Alles klein, alles unersetzlich.
_DATEIEN = ("gedaechtnis.jsonl", "memory.jsonl", "verlauf.jsonl",
            "erinnerungen.json", "werkzeuge.json", "wachhund.json")
_ORDNER_MIT = ("werkstatt",)

# Absichtlich draussen - jeweils mit Grund
_NIEMALS = {".env", ".env.example"}          # Zugangsdaten im Klartext
_ZU_GROSS = 50_000_000                       # die Wikipedia faellt hierunter


def _quellen() -> list[tuple[Path, str]]:
    """(Datei, Name im Archiv) - nur das Kleine und Unersetzliche."""
    gefunden = []
    for name in _DATEIEN:
        pfad = config.ROOT / "data" / name
        if pfad.exists() and pfad.stat().st_size < _ZU_GROSS:
            gefunden.append((pfad, f"data/{name}"))
    for ordnername in _ORDNER_MIT:
        wurzel = config.ROOT / ordnername
        if not wurzel.exists():
            continue
        for pfad in wurzel.rglob("*"):
            # __pycache__ entsteht beim naechsten Start von selbst neu
            if "__pycache__" in pfad.parts or pfad.suffix == ".pyc":
                continue
            if (pfad.is_file() and pfad.name not in _NIEMALS
                    and pfad.stat().st_size < _ZU_GROSS):
                gefunden.append((pfad, f"{ordnername}/"
                                 f"{pfad.relative_to(wurzel).as_posix()}"))
    return gefunden


def anlegen(grund: str = "") -> str:
    """Eine Sicherung schreiben. Gibt eine Meldung in Worten zurueck."""
    quellen = _quellen()
    if not quellen:
        return "Es gibt nichts zu sichern."

    ORDNER.mkdir(parents=True, exist_ok=True)
    stempel = dt.datetime.now().strftime("%Y-%m-%d_%H%M")
    ziel = ORDNER / f"jarvis_{stempel}.zip"

    # Erst daneben schreiben, dann umbenennen: bricht es mittendrin ab,
    # bleibt die vorige Sicherung heil und es entsteht keine halbe Datei,
    # die aussieht wie eine ganze.
    vorlaeufig = ziel.with_suffix(".zip.teil")
    try:
        with zipfile.ZipFile(vorlaeufig, "w", zipfile.ZIP_DEFLATED) as archiv:
            for pfad, name in quellen:
                archiv.write(pfad, name)
        if ziel.exists():
            ziel.unlink()
        vorlaeufig.rename(ziel)
    except Exception as exc:
        vorlaeufig.unlink(missing_ok=True)
        return f"Sicherung fehlgeschlagen: {type(exc).__name__}"

    entfernt = aufraeumen()
    groesse = ziel.stat().st_size / 1024
    zusatz = f", {entfernt} alte geloescht" if entfernt else ""
    hinweis = f" ({grund})" if grund else ""
    return (f"Gesichert{hinweis}: {len(quellen)} Dateien, {groesse:.0f} KB "
            f"in data/sicherungen/{ziel.name}{zusatz}")


def aufraeumen(behalten: int = None) -> int:
    """Alte Sicherungen wegwerfen. Gibt zurueck, wie viele gingen."""
    behalten = config.SICHERUNG_ANZAHL if behalten is None else behalten
    if not ORDNER.exists():
        return 0
    alle = sorted(ORDNER.glob("jarvis_*.zip"), key=lambda p: p.name)
    zu_viel = alle[:-behalten] if len(alle) > behalten else []
    for pfad in zu_viel:
        try:
            pfad.unlink()
        except OSError:
            pass
    return len(zu_viel)


def letzte() -> dt.datetime | None:
    if not ORDNER.exists():
        return None
    alle = sorted(ORDNER.glob("jarvis_*.zip"), key=lambda p: p.name)
    if not alle:
        return None
    return dt.datetime.fromtimestamp(alle[-1].stat().st_mtime)


def faellig() -> bool:
    """Ist seit der letzten Sicherung genug Zeit vergangen?"""
    if not config.SICHERUNG_AN:
        return False
    wann = letzte()
    if wann is None:
        return True
    return (dt.datetime.now() - wann).total_seconds() >= config.SICHERUNG_ABSTAND


def beim_start() -> str:
    """Einmal taeglich beim Hochfahren - kostet Millisekunden."""
    return anlegen("beim Start") if faellig() else ""


def uebersicht() -> str:
    if not ORDNER.exists() or not any(ORDNER.glob("jarvis_*.zip")):
        return "Es gibt noch keine Sicherung."
    alle = sorted(ORDNER.glob("jarvis_*.zip"), key=lambda p: p.name,
                  reverse=True)
    zeilen = []
    for pfad in alle[:8]:
        wann = dt.datetime.fromtimestamp(pfad.stat().st_mtime)
        zeilen.append(f"{wann.strftime('%d.%m. %H:%M')} "
                      f"({pfad.stat().st_size/1024:.0f} KB)")
    return f"{len(alle)} Sicherungen: " + ", ".join(zeilen)


def zurueckholen(name: str, ziel_ordner: Path | None = None) -> str:
    """Eine Sicherung auspacken - aber NICHT ueber die laufenden Dateien.

    Wiederherstellen ist ein Eingriff, den ein Mensch sehen soll, bevor er
    wirkt. Deshalb landet alles in einem eigenen Ordner, und er entscheidet,
    was er davon zurueckkopiert.
    """
    quelle = ORDNER / (name if name.endswith(".zip") else f"{name}.zip")
    if not quelle.exists():
        return f"Die Sicherung '{name}' gibt es nicht. {uebersicht()}"
    ziel = ziel_ordner or (config.ROOT / "data" / "wiederhergestellt"
                           / quelle.stem)
    ziel.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(quelle) as archiv:
            archiv.extractall(ziel)
    except Exception as exc:
        return f"Auspacken fehlgeschlagen: {type(exc).__name__}"
    # Liegt das Ziel ausserhalb des Projekts, gibt es keinen relativen Pfad -
    # relative_to() warf dort eine ValueError und riss die ganze Funktion mit,
    # nachdem sie ihre Arbeit bereits getan hatte. Dann lieber den vollen Pfad.
    try:
        wohin = ziel.relative_to(config.ROOT)
    except ValueError:
        wohin = ziel
    return (f"Ausgepackt nach {wohin}. Die laufenden "
            f"Dateien sind unberuehrt - was zurueck soll, kopierst du selbst.")
