"""Das Symbol in der Taskleiste - Jarvis' sichtbare Anwesenheit.

Ohne das hätte der Autostart ein Problem: ein Programm, das still im
Hintergrund läuft, das man nicht sehen und nicht beenden kann. Hier ist es
sichtbar, ein Klick öffnet die Oberfläche, ein Rechtsklick beendet sie.

Das Symbol ist ein Arc-Reaktor - gezeichnet, nicht geladen, damit keine
Bilddatei mitgeschleppt werden muss.
"""
from __future__ import annotations

import threading
import webbrowser

from . import config


def _symbol(farbe=(59, 169, 255), groesse: int = 64):
    """Zeichnet den Arc-Reaktor: zwei Ringe und ein Kern."""
    from PIL import Image, ImageDraw

    bild = Image.new("RGBA", (groesse, groesse), (0, 0, 0, 0))
    stift = ImageDraw.Draw(bild)
    m = groesse // 2

    stift.ellipse([2, 2, groesse - 3, groesse - 3],
                  outline=farbe + (255,), width=4)
    stift.ellipse([m - 16, m - 16, m + 16, m + 16],
                  outline=farbe + (180,), width=3)
    stift.ellipse([m - 7, m - 7, m + 7, m + 7], fill=farbe + (255,))
    return bild


class Tray:
    def __init__(self, adresse: str, beim_beenden=None) -> None:
        self.adresse = adresse
        self.beim_beenden = beim_beenden
        self.symbol = None

    def _oeffnen(self, *_):
        webbrowser.open(self.adresse)

    def _beenden(self, *_):
        if self.symbol:
            self.symbol.stop()
        if self.beim_beenden:
            self.beim_beenden()

    def _autostart_text(self, *_) -> str:
        from . import autostart

        lage = autostart.zustand()
        return (f"Autostart: {lage['art']}" if lage["an"]
                else "Autostart: aus")

    def _autostart_umschalten(self, *_):
        from . import autostart

        if autostart.zustand()["an"]:
            autostart.ausschalten()
        else:
            autostart.einschalten("oberflaeche")

    def bauen(self):
        import pystray

        menue = pystray.Menu(
            pystray.MenuItem("Jarvis öffnen", self._oeffnen, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(self._autostart_text, self._autostart_umschalten),
            pystray.MenuItem(lambda _: f"Adresse: {self.adresse}",
                             self._oeffnen),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Beenden", self._beenden),
        )
        self.symbol = pystray.Icon("jarvis", _symbol(), "JARVIS", menue)
        return self.symbol

    def starten_im_hintergrund(self) -> None:
        """Das Symbol läuft in einem eigenen Faden, der Server im Haupt-Faden."""
        symbol = self.bauen()
        threading.Thread(target=symbol.run, daemon=True,
                         name="Taskleiste").start()

    def laufen(self) -> None:
        self.bauen().run()


def verfuegbar() -> bool:
    try:
        import PIL  # noqa: F401
        import pystray  # noqa: F401
        return True
    except ImportError:
        return False
