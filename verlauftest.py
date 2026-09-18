"""Prüft das Gesprächsarchiv und den Autostart."""
import datetime as dt
import json

from jarvis import autostart, commands, config, tools, verlauf

print("=== Etwas ins Archiv schreiben ===")
verlauf.schreiben("du", "Wie warm wird es morgen in Hamburg?")
verlauf.schreiben("jarvis", "Zwanzig Grad und leichter Regen, Sir.")
verlauf.schreiben("du", "Und schreib mir bitte ein Backup-Skript.")
verlauf.schreiben("jarvis", "Liegt in werkstatt/backup.py, Sir.")
print(f"  {len(verlauf._lesen())} Einträge, Sitzung {verlauf.SITZUNG}")

print("\n=== Durchsuchen ===")
print(" ", tools.search_conversation("Hamburg")[:130])
print(" ", tools.search_conversation("Backup")[:130])
print(" ", tools.search_conversation("gibtsnichtxyz")[:90])

print("\n=== Eine frühere Sitzung vortäuschen ===")
# So sieht es aus, wenn Jarvis gestern schon einmal lief
gestern = dt.datetime.now() - dt.timedelta(days=1)
with verlauf.DATEI.open("a", encoding="utf-8") as fh:
    for rolle, text in (("du", "Erklär mir, wie das Weckwort funktioniert."),
                        ("jarvis", "Ein kleines Netz horcht dauerhaft, Sir."),
                        ("du", "Und was kostet das an Rechenleistung?")):
        fh.write(json.dumps({"zeit": gestern.isoformat(timespec="seconds"),
                             "sitzung": "gestern-test", "rolle": rolle,
                             "text": text}, ensure_ascii=False) + "\n")

letzte = verlauf.letzte_sitzung()
print(f"  wann: {letzte['wann']:%d.%m. %H:%M}, {letzte['anzahl']} Nachrichten")
print(f"  Themen: {letzte['themen']}")

print("\n=== Was davon im Systemprompt landet ===")
zeile = verlauf.fuer_systemprompt()
print(f"  {zeile}")
assert "gestern" in zeile

print("\n=== Nur die letzten Tage durchsuchen ===")
print(" ", tools.search_conversation("Weckwort", tage=2)[:120])
print(" ", tools.search_conversation("Weckwort", tage=0)[:120])

print("\n=== Agenten schreiben NICHT ins Archiv ===")
from jarvis.brain import Brain
haupt = Brain()
agent = Brain(system_prompt="Du bist Mk 9.")
print(f"  Jarvis archiviert: {haupt.archivieren}")
print(f"  Agent archiviert : {agent.archivieren}")
assert haupt.archivieren and not agent.archivieren

print("\n=== Aufräumen nach Ablauf ===")
alt = config.VERLAUF_TAGE
config.VERLAUF_TAGE = 0
print(f"  mit 0 Tagen (= nie aufräumen): {verlauf.aufraeumen()} entfernt")
config.VERLAUF_TAGE = alt

print("\n=== Autostart ===")
lage = autostart.zustand()
print(f"  Zustand jetzt: {lage}")
print(f"  Ordner: {autostart.ordner()}")
print(f"  {'existiert' if autostart.ordner().exists() else 'FEHLT'}")


class StummerSprecher:
    enabled = True

    def say(self, t, sprache=None): ...
    def say_teile(self, teile): ...
    def wait(self, timeout=0): ...
    def verstummen(self): ...


class FakeBrain:
    history = []
    model = "x"
    rangliste = []
    ping = []

    def reset(self): ...


ctx = commands.Kontext(FakeBrain(), StummerSprecher(), False)
print(" ", commands.ausfuehren("/autostart", ctx).replace("\n", "\n  "))

print("\n=== Verlauf-Befehl ===")
print(commands.ausfuehren("/verlauf Hamburg", ctx))

print("\nFertig.")
