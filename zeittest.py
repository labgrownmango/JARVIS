"""Prüft Zeitbezug, Begrüßung, Erinnerungen und das Gedächtnis mit Datum."""
import datetime as dt
import time
from unittest import mock

from jarvis import gedaechtnis, tools, zeit

print("=== Leerlauf (kommt von Windows selbst) ===")
print(f"  {zeit.leerlauf_sekunden():.1f} Sekunden -> {zeit.leerlauf_text()}")
print(f"  Tageszeit: {zeit.tageszeit()}")
print(f"  {tools.idle_time()}")

print("\n=== Begrüßung je nach Lage ===")
faelle = [
    ("morgens, gerade aktiv", dt.datetime(2026, 9, 13, 8, 30), 30),
    ("mittags, 50 Minuten weg", dt.datetime(2026, 9, 13, 12, 15), 50 * 60),
    ("abends, 5 Stunden weg", dt.datetime(2026, 9, 13, 20, 0), 5 * 3600),
    ("nachts, gerade aktiv", dt.datetime(2026, 9, 13, 1, 20), 60),
    ("nachts, 3 Stunden still", dt.datetime(2026, 9, 13, 2, 40), 3 * 3600),
]
for name, wann, leer in faelle:
    with mock.patch.object(zeit.dt, "datetime", mock.Mock(
            now=lambda w=wann: w, fromisoformat=dt.datetime.fromisoformat)), \
         mock.patch.object(zeit, "leerlauf_sekunden", lambda l=leer: l):
        print(f"  [{name:24}] {zeit.begruessung('Sir')}")

print("\n=== Gedächtnis mit Datum ===")
gedaechtnis.DATEI.parent.mkdir(parents=True, exist_ok=True)
print(" ", tools.remember("Jost arbeitet an einem Jarvis-Nachbau.", "vorhaben"))
print(" ", tools.remember("Der Rechner ist ein ausgemusterter Praxis-PC.", "fakt"))
print(" ", tools.remember("Jost mag kurze Antworten.", "vorliebe"))
print(" ", tools.recall("jarvis")[:120])

print("\n=== Wie lange ist das her? ===")
for tage, erwartet in ((0, "gerade eben"), (1, "gestern"), (2, "vorgestern"),
                       (4, "vor 4 Tagen"), (9, "vor einer Woche"),
                       (30, "vor 4 Wochen"), (200, "vor 6 Monaten"),
                       (400, "vor einem Jahr")):
    wann = dt.datetime.now() - dt.timedelta(days=tage)
    print(f"  {tage:>4} Tage -> {gedaechtnis.wie_lange_her(wann)}")

print("\n=== Was davon landet im Systemprompt ===")
print(gedaechtnis.fuer_systemprompt().format(name="Sir"))

print("\n=== Erinnerungen ===")
print(" ", tools.set_reminder("den Ofen ausmachen", in_minuten=0.05))
print(" ", tools.set_reminder("Zahnarzt anrufen", um="15:30"))
print(" ", tools.list_reminders())

gesagt = []
zeit.wecker_starten(sprecher=gesagt.append)
print("  warte, bis die erste faellig wird ...")
time.sleep(14)
print(f"  gesprochen: {gesagt}")
assert gesagt, "die Erinnerung hat sich nicht gemeldet"
print(" ", tools.list_reminders())
print(" ", tools.cancel_reminder())

print("\n=== Aufräumen ===")
print(" ", tools.forget("Jost"))
print(" ", tools.forget("Praxis-PC"))
print("\nFertig.")
