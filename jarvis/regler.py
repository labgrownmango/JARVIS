"""Lautstärke und Helligkeit - die beiden Regler, die man ständig anfasst.

Lautstärke ist einfach: Windows hat eine Schnittstelle, die den echten Wert
kennt und setzen kann. "Stell auf dreißig Prozent" geht damit wirklich, statt
nur blind auf die Leiser-Taste zu hämmern.

Helligkeit ist es nicht. Es gibt drei Wege, und welcher funktioniert, hängt
am Bildschirm:

  WMI      nur Laptops - dort sitzt das Hintergrundlicht am Mainboard
  DDC/CI   externe Monitore, sofern sie darauf antworten. Viele tun es nicht.
  Gamma    dunkelt das Bild per Software ab. Funktioniert immer, ändert aber
           nicht das Hintergrundlicht - der Bildschirm strahlt weiter, das
           Bild wird nur dunkler gerechnet.

Auf diesem Rechner bleibt nur der dritte Weg. Das wird auch so gesagt, statt
Helligkeit vorzutäuschen.
"""
from __future__ import annotations

import ctypes
import subprocess
import threading

_schloss = threading.Lock()
_regler = None
_gamma_urzustand = None
_gamma_stand = 100


# --- Lautstärke -------------------------------------------------------------
def _lautstaerkeregler():
    """Windows' echten Lautstärkeregler holen - einmal, dann gemerkt."""
    global _regler
    with _schloss:
        if _regler is not None:
            return _regler
        from ctypes import POINTER, cast

        import comtypes
        from pycaw.api.endpointvolume import IAudioEndpointVolume
        from pycaw.api.mmdeviceapi import IMMDeviceEnumerator
        from pycaw.constants import CLSID_MMDeviceEnumerator, EDataFlow, ERole

        comtypes.CoInitialize()
        zaehler = comtypes.CoCreateInstance(
            CLSID_MMDeviceEnumerator, IMMDeviceEnumerator,
            comtypes.CLSCTX_INPROC_SERVER)
        geraet = zaehler.GetDefaultAudioEndpoint(EDataFlow.eRender.value,
                                                 ERole.eMultimedia.value)
        schnittstelle = geraet.Activate(IAudioEndpointVolume._iid_,
                                        comtypes.CLSCTX_ALL, None)
        _regler = cast(schnittstelle, POINTER(IAudioEndpointVolume))
        return _regler


def lautstaerke_lesen() -> tuple[int, bool]:
    r = _lautstaerkeregler()
    return round(r.GetMasterVolumeLevelScalar() * 100), bool(r.GetMute())


def lautstaerke_setzen(prozent: float) -> int:
    r = _lautstaerkeregler()
    ziel = max(0.0, min(float(prozent), 100.0)) / 100
    r.SetMasterVolumeLevelScalar(ziel, None)
    if ziel > 0 and r.GetMute():
        r.SetMute(0, None)          # lauter drehen und stumm bleiben waere albern
    return round(r.GetMasterVolumeLevelScalar() * 100)


def lautstaerke_aendern(schritte: float) -> int:
    jetzt, _ = lautstaerke_lesen()
    return lautstaerke_setzen(jetzt + schritte)


def stumm_setzen(an: bool) -> bool:
    r = _lautstaerkeregler()
    r.SetMute(1 if an else 0, None)
    return bool(r.GetMute())


# --- Helligkeit -------------------------------------------------------------
def _wmi_lesen() -> int | None:
    """Laptops melden hier ihr Hintergrundlicht."""
    try:
        roh = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance -Namespace root/wmi -ClassName "
             "WmiMonitorBrightness -ErrorAction Stop).CurrentBrightness"],
            capture_output=True, text=True, timeout=20)
        werte = [int(z) for z in roh.stdout.split() if z.strip().isdigit()]
        return werte[0] if werte else None
    except Exception:
        return None


def _wmi_setzen(prozent: int) -> bool:
    try:
        roh = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"(Get-CimInstance -Namespace root/wmi -ClassName "
             f"WmiMonitorBrightnessMethods -ErrorAction Stop)."
             f"WmiSetBrightness(1,{int(prozent)})"],
            capture_output=True, text=True, timeout=20)
        return roh.returncode == 0 and "Exception" not in roh.stderr
    except Exception:
        return False


def _ddc_monitore():
    try:
        from monitorcontrol import get_monitors
        return get_monitors()
    except Exception:
        return []


def _ddc_lesen() -> int | None:
    for m in _ddc_monitore():
        try:
            with m:
                return m.get_luminance()
        except Exception:
            continue
    return None


def _ddc_setzen(prozent: int) -> bool:
    erfolg = False
    for m in _ddc_monitore():
        try:
            with m:
                m.set_luminance(int(prozent))
                erfolg = True
        except Exception:
            continue
    return erfolg


_waerme = 0          # 0 = neutral, 100 = maximal warm (Nachtmodus)

# Wie stark die Farbkanaele bei voller Waerme gedaempft werden. Blau kraeftig,
# Gruen leicht, Rot gar nicht - das ergibt den warmen Ton, den Blaulichtfilter
# erzeugen. Die Werte entsprechen grob 3400 Kelvin.
_WAERME_FAKTOR = {"rot": 1.00, "gruen": 0.78, "blau": 0.52}


def _gamma_versuch(dc, anteil: float, waerme: int = 0) -> bool:
    """Setzt die Gammakurve aus Helligkeit und Waerme zusammen.

    Beides geht durch dieselbe Kurve - deshalb muss es gemeinsam gerechnet
    werden, sonst loescht das eine das andere.
    """
    gdi = ctypes.windll.gdi32
    anteil_waerme = max(0, min(waerme, 100)) / 100
    kanal = [1.0 - (1.0 - _WAERME_FAKTOR[f]) * anteil_waerme
             for f in ("rot", "gruen", "blau")]

    neu = (ctypes.c_ushort * 256 * 3)()
    for i in range(256):
        grund = i * 257 * anteil
        for k in range(3):
            neu[k][i] = int(min(65535, grund * kanal[k]))
    return bool(gdi.SetDeviceGammaRamp(dc, ctypes.byref(neu)))


def _gamma_setzen(prozent: float) -> bool:
    """Dunkelt das Bild rechnerisch ab.

    Windows nimmt nicht jede Kurve an: zu starkes Abdunkeln wird abgelehnt,
    damit keine Software den Bildschirm unlesbar machen kann. Wo genau die
    Grenze liegt, sagt Windows nicht - deshalb wird herangetastet und der
    dunkelste noch erlaubte Wert genommen.
    """
    global _gamma_urzustand, _gamma_stand

    gdi, user = ctypes.windll.gdi32, ctypes.windll.user32
    dc = user.GetDC(None)
    try:
        if _gamma_urzustand is None:
            urzustand = (ctypes.c_ushort * 256 * 3)()
            if not gdi.GetDeviceGammaRamp(dc, ctypes.byref(urzustand)):
                return False
            _gamma_urzustand = urzustand

        gewuenscht = max(0.0, min(float(prozent), 100.0))
        for wert in range(int(gewuenscht), 101, 5):
            if _gamma_versuch(dc, wert / 100, _waerme):
                _gamma_stand = wert
                return True
        return False
    finally:
        user.ReleaseDC(None, dc)


def gamma_grenze() -> int:
    """Wie dunkel laesst Windows es zu? Einmal ausprobiert, dann bekannt."""
    global _gamma_stand

    vorher = _gamma_stand
    user, gdi = ctypes.windll.user32, ctypes.windll.gdi32
    dc = user.GetDC(None)
    try:
        if _gamma_urzustand is None:
            urzustand = (ctypes.c_ushort * 256 * 3)()
            if not gdi.GetDeviceGammaRamp(dc, ctypes.byref(urzustand)):
                return 100
            globals()["_gamma_urzustand"] = urzustand
        grenze = 100
        for wert in range(10, 101, 5):
            if _gamma_versuch(dc, wert / 100, _waerme):
                grenze = wert
                break
        _gamma_versuch(dc, vorher / 100)
        return grenze
    finally:
        user.ReleaseDC(None, dc)


def gamma_zuruecksetzen() -> None:
    global _gamma_stand, _waerme

    if _gamma_urzustand is None:
        return
    user, gdi = ctypes.windll.user32, ctypes.windll.gdi32
    dc = user.GetDC(None)
    gdi.SetDeviceGammaRamp(dc, ctypes.byref(_gamma_urzustand))
    user.ReleaseDC(None, dc)
    _gamma_stand, _waerme = 100, 0


# --- Nachtmodus -------------------------------------------------------------
def nachtmodus_setzen(an: bool, staerke: int = 100) -> tuple[bool, int]:
    """Blaulichtfilter an oder aus.

    Gebaut wie f.lux: der Blauanteil wird gedaempft, Gruen leicht, Rot gar
    nicht. Windows' eigener Nachtmodus liesse sich nur ueber einen
    undokumentierten Eintrag in der Registrierung schalten - das ist bei
    jedem Update wieder kaputt. Ueber die Gammakurve gehoert es uns.
    """
    global _waerme, _gamma_urzustand

    user, gdi = ctypes.windll.user32, ctypes.windll.gdi32
    dc = user.GetDC(None)
    try:
        if _gamma_urzustand is None:
            urzustand = (ctypes.c_ushort * 256 * 3)()
            if not gdi.GetDeviceGammaRamp(dc, ctypes.byref(urzustand)):
                return False, _waerme
            _gamma_urzustand = urzustand

        gewuenscht = max(0, min(int(staerke), 100)) if an else 0
        # Helligkeit und Waerme teilen sich eine Kurve. Beides stark gesetzt
        # macht Blau so dunkel, dass Windows ablehnt - dann wird die Waerme
        # so weit zurueckgenommen, bis es angenommen wird.
        for ziel in range(gewuenscht, -1, -10):
            if _gamma_versuch(dc, _gamma_stand / 100, ziel):
                _waerme = ziel
                return True, _waerme
        return False, _waerme
    finally:
        user.ReleaseDC(None, dc)


def nachtmodus_lesen() -> tuple[bool, int]:
    return _waerme > 0, _waerme


def nachtzeit(jetzt=None) -> bool:
    """Liegt die Uhrzeit im Nachtfenster? Es geht ueber Mitternacht."""
    import datetime as dt

    from . import config

    jetzt = jetzt or dt.datetime.now()
    minute = jetzt.hour * 60 + jetzt.minute
    von = config.NACHT_VON_STUNDE * 60 + config.NACHT_VON_MINUTE
    bis = config.NACHT_BIS_STUNDE * 60 + config.NACHT_BIS_MINUTE
    return minute >= von or minute < bis


# Welcher Weg auf diesem Rechner funktioniert, aendert sich nicht. Einmal
# herausfinden und merken - sonst laeuft jeder Helligkeitsbefehl erst in das
# Zeitlimit von WMI und DDC/CI, bevor er bei der Gammakurve ankommt. Das
# kostete gemessen ueber zwanzig Sekunden pro Aufruf.
_weg: str | None = None


def _weg_finden() -> str:
    global _weg
    if _weg is not None:
        return _weg
    with _schloss:
        if _weg is not None:
            return _weg
        if _wmi_lesen() is not None:
            _weg = "wmi"
        elif _ddc_lesen() is not None:
            _weg = "ddc"
        else:
            _weg = "gamma"
    return _weg


WEGNAME = {"wmi": "Hintergrundlicht", "ddc": "Monitor (DDC/CI)",
           "gamma": "Bild abgedunkelt"}


def helligkeit_lesen() -> tuple[int | None, str]:
    """Gibt (Wert, Weg) zurueck. Weg sagt, woher der Wert stammt."""
    weg = _weg_finden()
    if weg == "wmi":
        return _wmi_lesen(), WEGNAME[weg]
    if weg == "ddc":
        return _ddc_lesen(), WEGNAME[weg]
    return _gamma_stand, WEGNAME[weg]


def helligkeit_setzen(prozent: float) -> tuple[int, str]:
    ziel = int(max(0, min(prozent, 100)))
    weg = _weg_finden()
    if weg == "wmi" and _wmi_setzen(ziel):
        return ziel, WEGNAME[weg]
    if weg == "ddc" and _ddc_setzen(ziel):
        return ziel, WEGNAME[weg]
    if _gamma_setzen(ziel):
        return ziel, WEGNAME["gamma"]
    return ziel, "nicht moeglich"
