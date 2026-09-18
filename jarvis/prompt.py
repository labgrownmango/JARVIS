"""Eingabezeile mit Live-Vorschlaegen für Slash-Befehle.

Tippst du "/h", erscheint darunter sofort, welche Befehle damit anfangen.
Tab vervollständigt. Faellt zurück auf das normale input(), wenn die Eingabe
nicht von einer echten Tastatur kommt (z.B. bei Tests mit Pipe).
"""
from __future__ import annotations

import os
import sys
import threading
import time

ESC = "\x1b"
DIM, HELL, AUS = f"{ESC}[90m", f"{ESC}[96m", f"{ESC}[0m"

try:
    import msvcrt
except ImportError:                       # pragma: no cover - nur Windows
    msvcrt = None


def _vt_aktivieren() -> bool:
    """Windows-Konsole auf ANSI-Sequenzen umstellen (Cursor bewegen, Farben)."""
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)          # STD_OUTPUT_HANDLE
        modus = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(modus)):
            return False
        # ENABLE_VIRTUAL_TERMINAL_PROCESSING
        return bool(kernel32.SetConsoleMode(handle, modus.value | 0x0004))
    except Exception:
        return False


class EscWache:
    """Horcht während einer laufenden Antwort auf die Escape-Taste.

    Gedacht als Notbremse: hängt das Modell oder dreht sich Jarvis im Kreis,
    bricht Escape sofort ab, statt auf das Zeitlimit zu warten. Andere Tasten
    werden dabei geschluckt, damit sie nicht in der nächsten Eingabe landen.
    """

    def __init__(self, bei_abbruch) -> None:
        self._bei_abbruch = bei_abbruch
        self._stop = threading.Event()
        self.ausgeloest = False
        self.aktiv = bool(msvcrt) and sys.stdin.isatty()

    def _lauschen(self) -> None:
        while not self._stop.is_set():
            try:
                if msvcrt.kbhit():
                    taste = msvcrt.getwch()
                    if taste in ("\x00", "\xe0"):     # Sondertaste
                        msvcrt.getwch()
                    elif taste == "\x1b" and not self.ausgeloest:
                        self.ausgeloest = True
                        self._bei_abbruch()
            except Exception:
                return
            time.sleep(0.05)

    def __enter__(self) -> "EscWache":
        if self.aktiv:
            self._thread = threading.Thread(target=self._lauschen, daemon=True)
            self._thread.start()
        return self

    def __exit__(self, *_) -> None:
        self._stop.set()


class LineEditor:
    """Liest eine Zeile und blendet passende Befehle darunter ein."""

    MAX_VORSCHLAEGE = 8

    def __init__(self, befehle: dict[str, str]) -> None:
        """befehle: {"/hilfe": "zeigt alle Befehle", ...}"""
        self.befehle = befehle
        # JARVIS_SIMPLE_INPUT=1 erzwingt das schlichte input() - nötig für
        # Tests und für Konsolen, die keine Einzeltasten liefern.
        self.interaktiv = (
            os.getenv("JARVIS_SIMPLE_INPUT", "0") != "1"
            and bool(msvcrt) and sys.stdin.isatty() and _vt_aktivieren()
        )

    # -- Vorschlaege --------------------------------------------------------
    def _treffer(self, text: str) -> list[str]:
        if not text.startswith("/") or " " in text:
            return []
        return [b for b in sorted(self.befehle) if b.startswith(text.lower())]

    def _zeichne(self, prompt: str, text: str) -> None:
        treffer = self._treffer(text)
        aus = f"\r{ESC}[0J{prompt}{text}"
        if treffer:
            gezeigt = treffer[:self.MAX_VORSCHLAEGE]
            rest = len(treffer) - len(gezeigt)
            zeile = "  ".join(f"{HELL}{b}{AUS}" for b in gezeigt)
            if rest:
                zeile += f"{DIM}  (+{rest}){AUS}"
            if len(gezeigt) == 1:
                zeile += f"{DIM}   {self.befehle[gezeigt[0]]}{AUS}"
            aus += f"\n   {zeile}"
            aus += f"{ESC}[1A\r{ESC}[{len(prompt) + len(text)}C"
        sys.stdout.write(aus)
        sys.stdout.flush()

    @staticmethod
    def _gemeinsamer_anfang(woerter: list[str]) -> str:
        if not woerter:
            return ""
        kurz = min(woerter, key=len)
        for i, zeichen in enumerate(kurz):
            if any(w[i] != zeichen for w in woerter):
                return kurz[:i]
        return kurz

    # -- Hauptschleife ------------------------------------------------------
    def read(self, prompt: str) -> str:
        if not self.interaktiv:
            return input(prompt)

        text = ""
        self._zeichne(prompt, text)
        while True:
            zeichen = msvcrt.getwch()

            if zeichen in ("\r", "\n"):
                sys.stdout.write(f"\r{ESC}[0J{prompt}{text}\n")
                sys.stdout.flush()
                return text
            if zeichen == "\x03":                    # Strg+C
                sys.stdout.write("\n")
                raise KeyboardInterrupt
            if zeichen == "\x04":                    # Strg+D
                sys.stdout.write("\n")
                raise EOFError
            if zeichen in ("\x00", "\xe0"):          # Pfeil-/Funktionstaste
                msvcrt.getwch()                      # Zusatzcode wegwerfen
                continue
            if zeichen == "\x08":                    # Rückschritt
                text = text[:-1]
            elif zeichen == "\x1b":                  # Escape leert die Zeile
                text = ""
            elif zeichen == "\t":
                treffer = self._treffer(text)
                if treffer:
                    text = self._gemeinsamer_anfang(treffer)
                    if len(treffer) == 1:
                        text += " "
            elif zeichen >= " ":
                text += zeichen

            self._zeichne(prompt, text)
