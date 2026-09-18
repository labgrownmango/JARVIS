"""Prüft den Hangar: Nummern, Limit, Berichte, Aufräumen - ohne echte API."""
import gc
import os
import threading
import time
import weakref

from jarvis import config
from jarvis.agenten import HANGAR, Agent, _obergrenze

print("=== Obergrenze richtet sich nach dem Rechner ===")
print(f"  {os.cpu_count()} logische Prozessoren -> {_obergrenze()} Agenten")
assert _obergrenze() >= 1

# Statt echter API-Aufrufe: eine Aufgabe, die einfach wartet
def falsche_arbeit(dauer, ergebnis="Erledigt."):
    def arbeiten(self):
        self.zustand = "arbeitet"
        time.sleep(dauer)
        self.bericht = ergebnis
        self.zustand = "fertig"
        self.ende = time.monotonic()
        self._aufraeumen()
    return arbeiten


print("\n=== Nummern werden durchgezaehlt, nie wiederverwendet ===")
Agent._arbeiten = falsche_arbeit(0.3)
namen = []
for _ in range(3):
    agent, meldung = HANGAR.starten("Testaufgabe")
    namen.append(agent.name)
print(f"  {namen}")
assert namen == ["Mk 1", "Mk 2", "Mk 3"]

time.sleep(0.6)
for n in namen:
    HANGAR.abholen(n)
agent, _ = HANGAR.starten("noch eine")
print(f"  nach dem Einmotten von Mk 1-3 kommt: {agent.name}")
assert agent.name == "Mk 4", agent.name
time.sleep(0.5)
HANGAR.abholen("Mk 4")

print("\n=== Das Limit haelt ===")
Agent._arbeiten = falsche_arbeit(2.0)
grenze = HANGAR.grenze
gestartet, abgelehnt = 0, 0
for _ in range(grenze + 2):
    agent, meldung = HANGAR.starten("lange Aufgabe")
    if agent:
        gestartet += 1
    else:
        abgelehnt += 1
        letzte_meldung = meldung
print(f"  {gestartet} gestartet, {abgelehnt} abgelehnt (Grenze {grenze})")
print(f"  Meldung: {letzte_meldung[:80]}")
assert gestartet == grenze and abgelehnt == 2

print("\n=== Uebersicht ===")
print(HANGAR.uebersicht())

print("\n=== Nach dem Abholen ist der Speicher frei ===")
time.sleep(2.3)
ein_agent = next(iter(HANGAR.agenten.values()))
name = ein_agent.name
spur = weakref.ref(ein_agent)
bericht = HANGAR.abholen(name)
print(f"  {bericht[:60]}")
assert name not in HANGAR.agenten, "Agent haengt noch im Hangar"
del ein_agent
gc.collect()
print(f"  Objekt im Speicher: {'ja - Leck!' if spur() else 'nein, freigegeben'}")
assert spur() is None

print("\n=== Reste aufraeumen ===")
for a in list(HANGAR.agenten.values()):
    HANGAR.abholen(a.name)
print(f"  Hangar: {len(HANGAR.agenten)} Agenten")
assert not HANGAR.agenten

print("\n=== Stoppen: der Agent hoert auf das Signal ===")
gestoppt_bei = []


def arbeit_die_hinhoert(self):
    """Wie ein echter Agent: prüft zwischen den Schritten, ob er noch soll."""
    self.zustand = "arbeitet"
    for schritt in range(60):
        if self.zustand == "gestoppt":
            gestoppt_bei.append(schritt)
            break
        time.sleep(0.05)
    self.ende = time.monotonic()
    self._aufraeumen()


Agent._arbeiten = arbeit_die_hinhoert
agent, _ = HANGAR.starten("endlose Aufgabe")
time.sleep(0.3)
zahl = HANGAR.alle_stoppen()
time.sleep(0.3)
print(f"  {zahl} gestoppt, Agent brach bei Schritt {gestoppt_bei} ab")
assert gestoppt_bei, "der Agent hat das Stoppsignal ignoriert"
for a in list(HANGAR.agenten.values()):
    HANGAR.entfernen(a.name)

time.sleep(0.2)
uebrig = [t.name for t in threading.enumerate() if t.name.startswith("Mk")]
print(f"  noch laufende Agent-Threads: {uebrig or 'keine'}")
assert not uebrig

print("\n=== Reissleine 1: Zeitlimit ===")
config.AGENT_ZEITLIMIT = 1.0


def endlose_arbeit(self):
    self.zustand = "arbeitet"
    for _ in range(200):
        if not self.laeuft:
            break
        time.sleep(0.05)
    self.ende = time.monotonic()
    self._aufraeumen()


Agent._arbeiten = endlose_arbeit
agent, _ = HANGAR.starten("laeuft und laeuft")
start = time.monotonic()
while agent.laeuft and time.monotonic() - start < 10:
    time.sleep(0.2)
print(f"  nach {agent.dauer:.1f}s: {agent.zustand}, Grund: {agent.grund}")
assert agent.zustand == "abgebrochen", agent.zustand
assert "Zeitlimit" in agent.grund
HANGAR.entfernen(agent.name)
config.AGENT_ZEITLIMIT = 300

print("\n=== Reissleine 2: Verlauf laeuft voll ===")
config.AGENT_MAX_VERLAUF = 500


class VollerVerlauf:
    """Tut so, als haette der Agent sich in einer Schleife vollgeschrieben."""
    history = [{"content": "x" * 1000}]

    def abbrechen(self): ...


agent = Agent(99, "Schleife")
agent.zustand = "arbeitet"
agent._brain = VollerVerlauf()
print(f"  Verlauf: {agent.verlauf_zeichen} Zeichen bei Grenze "
      f"{config.AGENT_MAX_VERLAUF}")
grund = agent.ueberziehung()
print(f"  Wache sagt: {grund}")
assert "Verlauf zu gross" in grund
config.AGENT_MAX_VERLAUF = 80000

print("\n=== Reissleine 3: zu wenig Arbeitsspeicher zum Starten ===")
config.AGENT_MIN_FREI_MB = 10_000_000      # absichtlich unerreichbar
agent, meldung = HANGAR.starten("darf nicht starten")
print(f"  {meldung[:90]}")
assert agent is None
config.AGENT_MIN_FREI_MB = 400

print("\n=== Hangar ist leer ===")
for a in list(HANGAR.agenten.values()):
    HANGAR.entfernen(a.name)
print(f"  {len(HANGAR.agenten)} Agenten")

print("\nAlles wie erwartet.")
