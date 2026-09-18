"""Der Hangar: Hintergrundagenten für längere Aufgaben.

Jeder Agent ist ein eigenes Gehirn mit eigenem Gesprächsverlauf und eigenen
Werkzeugen. Er arbeitet allein an einer Aufgabe und meldet am Ende einen
kurzen Bericht an Jarvis zurück.

Benannt wie Tony Starks Anzüge: Mk 1, Mk 2, Mk 3 ... Die Nummer wird nie
wiederverwendet, auch wenn ein Anzug längst eingemottet ist.

Aufgeräumt wird konsequent: sobald ein Bericht abgeholt ist, fliegen Gehirn
und Verlauf des Agenten weg. Zurück bleibt nur der Bericht als Text.
"""
from __future__ import annotations

import os
import threading
import time

from . import config, tools
from .brain import AbbruchError, Brain


def _obergrenze() -> int:
    """Wie viele Anzüge gleichzeitig fliegen dürfen.

    Agenten warten überwiegend auf die API, sie rechnen kaum - ein Kern pro
    Agent wäre Verschwendung. Ein Drittel der logischen Prozessoren ist ein
    vernünftiger Kompromiss, gedeckelt, weil sonst das Anfragelimit des
    Anbieters zuschlägt, lange bevor der Rechner ins Schwitzen kommt.
    """
    gesetzt = os.getenv("JARVIS_MAX_AGENTEN")
    if gesetzt and gesetzt.isdigit() and int(gesetzt) > 0:
        return int(gesetzt)
    kerne = os.cpu_count() or 2
    return max(1, min(kerne // 3, 4))


class Agent:
    """Ein Anzug. Lebt in seinem eigenen Thread."""

    def __init__(self, nummer: int, aufgabe: str) -> None:
        self.name = f"Mk {nummer}"
        self.aufgabe = aufgabe.strip()
        self.zustand = "startet"          # startet|arbeitet|fertig|gescheitert|gestoppt
        self.bericht = ""
        self.grund = ""                   # warum abgebrochen, falls abgebrochen
        self.start = time.monotonic()
        self.ende: float | None = None
        self._brain: Brain | None = None
        self._thread: threading.Thread | None = None

    @property
    def dauer(self) -> float:
        return (self.ende or time.monotonic()) - self.start

    @property
    def verlauf_zeichen(self) -> int:
        """Wie viel Text der Agent bisher angehaeuft hat."""
        if self._brain is None:
            return 0
        return sum(len(str(n.get("content") or "")) for n in self._brain.history)

    def ueberziehung(self) -> str:
        """Prueft die Reissleinen. Gibt den Grund zurueck oder ""."""
        if not self.laeuft:
            return ""
        if self.dauer > config.AGENT_ZEITLIMIT:
            return (f"Zeitlimit von {config.AGENT_ZEITLIMIT:.0f}s "
                    f"ueberschritten")
        zeichen = self.verlauf_zeichen
        if zeichen > config.AGENT_MAX_VERLAUF:
            return (f"Verlauf zu gross ({zeichen} Zeichen) - "
                    f"vermutlich eine Schleife")
        return ""

    def starten(self) -> None:
        self._thread = threading.Thread(target=self._arbeiten, daemon=True,
                                        name=self.name)
        self._thread.start()

    def _arbeiten(self) -> None:
        self.zustand = "arbeitet"
        try:
            self._brain = Brain(
                system_prompt=config.AGENT_PROMPT.format(name=self.name),
                max_tokens=config.AGENT_TOKENS)
            # Agenten melden nichts an die Statuszeile - dort spricht Jarvis.
            # Der Aufruf bleibt thread-lokal, also stoert er niemanden.
            tools.setze_melder(None)
            self._brain.rangliste = list(config.MODELS)
            self.bericht = self._brain.ask(self.aufgabe,
                                           max_tool_rounds=config.AGENT_RUNDEN)
            if self.grund:                       # von der Wache abgebrochen
                self.zustand = "abgebrochen"
                self.bericht = f"Abgebrochen: {self.grund}."
            else:
                self.zustand = "fertig" if self.bericht else "gestoppt"
        except AbbruchError:
            self.zustand = "abgebrochen" if self.grund else "gestoppt"
            self.bericht = (f"Abgebrochen: {self.grund}."
                            if self.grund else self.bericht)
        except Exception as exc:
            self.zustand = "gescheitert"
            self.bericht = f"{type(exc).__name__}: {exc}"
        finally:
            self.ende = time.monotonic()
            self._aufraeumen()

    def _aufraeumen(self) -> None:
        """Gehirn und Verlauf freigeben. Der Bericht ist ja gerettet."""
        if self._brain is not None:
            self._brain.history.clear()
            self._brain = None

    def stoppen(self, grund: str = "") -> None:
        if grund:
            self.grund = grund
        if self._brain is not None:
            self._brain.abbrechen()
        self.zustand = "abgebrochen" if grund else "gestoppt"

    @property
    def laeuft(self) -> bool:
        return self.zustand in ("startet", "arbeitet")


class Hangar:
    """Verwaltet die Anzüge: Nummern vergeben, Limit wahren, ausmisten."""

    def __init__(self) -> None:
        self.agenten: dict[str, Agent] = {}
        self._naechste_nummer = 1
        self._gemeldet: set[str] = set()
        self._schloss = threading.Lock()
        self._wache: threading.Thread | None = None

    @property
    def grenze(self) -> int:
        return _obergrenze()

    # -- Wache ---------------------------------------------------------------
    @staticmethod
    def _prozess_mb() -> float:
        try:
            import psutil
            return psutil.Process().memory_info().rss / 1e6
        except Exception:
            return 0.0

    @staticmethod
    def _frei_mb() -> float:
        try:
            import psutil
            return psutil.virtual_memory().available / 1e6
        except Exception:
            return 1e9          # nicht messbar: nicht im Weg stehen

    def _wache_starten(self) -> None:
        if self._wache and self._wache.is_alive():
            return
        self._wache = threading.Thread(target=self._wachen, daemon=True,
                                       name="Hangar-Wache")
        self._wache.start()

    def _runde(self) -> bool:
        """Eine Kontrollrunde. False, wenn nichts mehr zu bewachen ist.

        Bewusst eine eigene Methode: so verschwinden alle Verweise auf die
        Agenten, sobald sie zurueckkehrt. Haelt die Wache sie ueber ihren
        Schlaf hinweg fest, kann ein fertiger Agent nicht freigegeben werden.
        """
        laufende = self.laufende()
        if not laufende:
            return False

        for agent in laufende:
            grund = agent.ueberziehung()
            if grund:
                print(f"\n  [{agent.name} abgebrochen: {grund}]")
                agent.stoppen(grund)

        # Speicherbremse. Sie sieht auf den freien Speicher des Rechners, nicht
        # nur auf die eigene Groesse: mit geladener Spracherkennung wiegt der
        # Prozess schon rund ein Gigabyte, ohne dass ein Agent schuld waere.
        # Erst wenn dem Rechner die Luft ausgeht, wird jemand nach Hause
        # geschickt - und zwar der aelteste.
        frei = self._frei_mb()
        prozess = self._prozess_mb()
        eng = frei < config.AGENT_MIN_FREI_MB
        zu_dick = (config.AGENT_MAX_PROZESS_MB > 0
                   and prozess > config.AGENT_MAX_PROZESS_MB)
        if eng or zu_dick:
            aeltester = max(laufende, key=lambda a: a.dauer, default=None)
            if aeltester is not None:
                grund = (f"nur noch {frei:.0f} MB frei" if eng else
                         f"Prozess bei {prozess:.0f} von "
                         f"{config.AGENT_MAX_PROZESS_MB} MB")
                print(f"\n  [{aeltester.name} abgebrochen: {grund}]")
                aeltester.stoppen(grund)
        return True

    def _wachen(self) -> None:
        """Sieht alle zwei Sekunden nach, ob ein Agent aus dem Ruder laeuft."""
        while self._runde():
            time.sleep(2)

    def laufende(self) -> list[Agent]:
        return [a for a in self.agenten.values() if a.laeuft]

    def starten(self, aufgabe: str) -> tuple[Agent | None, str]:
        frei = self._frei_mb()
        if frei < config.AGENT_MIN_FREI_MB:
            return None, (f"Zu wenig Arbeitsspeicher frei ({frei:.0f} MB, "
                          f"noetig sind {config.AGENT_MIN_FREI_MB}). "
                          f"Erst Platz schaffen.")
        with self._schloss:
            laufend = len(self.laufende())
            if laufend >= self.grenze:
                namen = ", ".join(a.name for a in self.laufende())
                return None, (f"Schon {laufend} Agenten unterwegs ({namen}), "
                              f"mehr als {self.grenze} gleichzeitig geht nicht. "
                              f"Warte, bis einer fertig ist.")
            agent = Agent(self._naechste_nummer, aufgabe)
            self._naechste_nummer += 1
            self.agenten[agent.name] = agent
        agent.starten()
        self._wache_starten()
        return agent, f"{agent.name} ist unterwegs."

    def fertige_ohne_meldung(self) -> list[Agent]:
        """Agenten, die fertig sind und deren Bericht noch niemand kennt."""
        neu = [a for a in self.agenten.values()
               if not a.laeuft and a.name not in self._gemeldet]
        self._gemeldet.update(a.name for a in neu)
        return neu

    def abholen(self, name: str) -> str:
        """Bericht holen und den Anzug einmotten - er wird nicht mehr gebraucht."""
        agent = self.agenten.get(name)
        if agent is None:
            return f"Einen {name} gibt es nicht."
        if agent.laeuft:
            return f"{agent.name} arbeitet noch ({agent.dauer:.0f}s bisher)."
        bericht = agent.bericht or "(kein Bericht)"
        self.entfernen(name)
        return f"{name} ({agent.zustand} nach {agent.dauer:.0f}s): {bericht}"

    def entfernen(self, name: str) -> None:
        with self._schloss:
            agent = self.agenten.pop(name, None)
            self._gemeldet.discard(name)
        if agent is not None:
            agent._aufraeumen()

    def aufraeumen(self, aelter_als: float = 0) -> int:
        """Eingemottete Anzüge endgültig verschrotten."""
        weg = [a.name for a in list(self.agenten.values())
               if not a.laeuft and a.name in self._gemeldet
               and a.dauer >= aelter_als]
        for name in weg:
            self.entfernen(name)
        return len(weg)

    def alle_stoppen(self) -> int:
        laufend = self.laufende()
        for agent in laufend:
            agent.stoppen()
        return len(laufend)

    def uebersicht(self) -> str:
        if not self.agenten:
            return (f"Der Hangar ist leer. Bis zu {self.grenze} Agenten "
                    f"gleichzeitig möglich.")
        zeilen = []
        for agent in self.agenten.values():
            kurz = agent.aufgabe[:40] + ("..." if len(agent.aufgabe) > 40 else "")
            zeichen = agent.verlauf_zeichen
            last = f" {zeichen // 1000}k" if zeichen else ""
            zeilen.append(f"  {agent.name:6} {agent.zustand:12} "
                          f"{agent.dauer:5.0f}s{last:>5}  {kurz}")
        return (f"{len(self.laufende())} von {self.grenze} unterwegs "
                f"(Prozess {self._prozess_mb():.0f} MB, "
                f"Zeitlimit {config.AGENT_ZEITLIMIT:.0f}s):\n"
                + "\n".join(zeilen))


HANGAR = Hangar()
