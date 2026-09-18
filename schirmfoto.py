"""Macht ein Foto des Bildschirms und legt es als PNG ab."""
import sys

import mss
from PIL import Image

ziel = sys.argv[1] if len(sys.argv) > 1 else "schirm.png"

with mss.MSS() as schirm:
    roh = schirm.grab(schirm.monitors[1])

bild = Image.frombytes("RGB", roh.size, roh.rgb)
bild.save(ziel, "PNG")
print(f"{ziel}: {bild.width}x{bild.height}")
