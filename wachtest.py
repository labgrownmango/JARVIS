"""Prüft den Wachhund: schlägt er an, und hält er sich zurück?"""
import datetime as dt
import time
from pathlib import Path
from unittest import mock

from jarvis import config, wachhund, zeit

gesagt = []
hund = wachhund.Wachhund(sprechen=gesagt.append)

print("=== Welche Regeln gibt es? ===")
for r in hund.uebersicht():
    sperre = ("je Ereignis" if not r["sperrzeit"]
              else f"{r['sperrzeit']/60:.0f} min")
    print(f"  {r['name']:10} {sperre:12} "
          f"{'auch nachts' if r['dringend'] else '':12} {r['beschreibung']}")

print("\n=== Download erkennen ===")
ordner = Path.home() / "Downloads"
ordner.mkdir(exist_ok=True)
probe = ordner / "jarvis-probe.bin"
probe.unlink(missing_ok=True)

wachhund._downloads_bekannt = set()
wachhund._downloads_pruefen()                      # erster Lauf: nur merken
print(f"  {len(wachhund._downloads_bekannt)} Dateien gemerkt")

probe.write_bytes(b"x" * 3_000_000)                 # "Download" kommt an
print(f"  Datei angelegt -> {wachhund._downloads_pruefen()!r} (waechst noch)")
print(f"  zweite Runde   -> {wachhund._downloads_pruefen()!r}")
probe.unlink(missing_ok=True)

print("\n=== Voller Speicher: Schwelle absichtlich unterschreiten ===")
alt = config.WACH_RAM_PROZENT
config.WACH_RAM_PROZENT = 1
print(" ", wachhund._speicher_pruefen())
config.WACH_RAM_PROZENT = alt
print("  mit echter Schwelle:", wachhund._speicher_pruefen() or "(still)")

print("\n=== Volle Platte ===")
alt = config.WACH_PLATTE_GB
config.WACH_PLATTE_GB = 99999
print(" ", wachhund._platte_pruefen())
config.WACH_PLATTE_GB = alt

print("\n=== Laufzeit ===")
print(" ", wachhund._laufzeit_pruefen() or "(still - laeuft nicht lang genug)")

print("\n=== Nachrichten, während niemand da war ===")
# Sammeln soll er die ganze Zeit, reden erst, wenn jemand zurück ist - sonst
# spräche er ins Leere. Und er liest nicht vor, er BIETET AN: der Text geht
# später direkt an die Stimme, nicht durch das Modell.
from jarvis import melder

_echt_leerlauf = zeit.leerlauf_sekunden
melder.BRIEFKASTEN._eintraege = [{
    "id": 9001, "app": "WhatsApp", "art": "person",
    "bedeutung": "Nachrichten von Menschen",
    "zeit": dt.datetime.now(), "titel": "Caitlin",
    "texte": ["Caitlin", "Bringst du Brot mit?"]}]

zeit.leerlauf_sekunden = lambda: config.WACH_ANWESEND + 600   # weg
wachhund._war_weg = False
still = wachhund._benachrichtigungen_pruefen()
print(f"  weg      -> {still or '(still - richtig)'}")
assert not still, "Während der Abwesenheit soll er schweigen"

zeit.leerlauf_sekunden = lambda: 3                            # wieder da
melder.BRIEFKASTEN._eintraege = [{
    "id": 9002, "app": "WhatsApp", "art": "person",
    "bedeutung": "Nachrichten von Menschen",
    "zeit": dt.datetime.now(), "titel": "Caitlin",
    "texte": ["Caitlin", "Bringst du Brot mit?"]}]
zurueck = wachhund._benachrichtigungen_pruefen()
print(f"  zurück   -> {zurueck[:90]}")
assert "Caitlin" in zurueck, "Beim Zurückkommen soll er berichten"
assert "Soll ich vorlesen" in zurueck, "Er soll anbieten, nicht vorlesen"
assert "Brot" not in zurueck, "Der Nachrichtentext darf nicht auftauchen"

nochmal = wachhund._benachrichtigungen_pruefen()
print(f"  nochmal  -> {nochmal or '(still - richtig)'}")
assert not nochmal, "Er soll sich nicht wiederholen"

zeit.leerlauf_sekunden = _echt_leerlauf
melder.BRIEFKASTEN._eintraege.clear()

print("\n=== Ruhezeit richtig rechnen ===")
# Die alte Fassung rechnete immer so, als liefe das Fenster über Mitternacht.
# Bei 23-7 stimmte das; eine Mittagsruhe von 13-15 hätte fast jede Stunde als
# Ruhezeit gewertet - und Jarvis hätte den ganzen Tag geschwiegen. Weil sich
# die Zeiten in der Oberfläche einstellen lassen, ist das kein Sonderfall.
_von, _bis = config.WACH_RUHE_VON, config.WACH_RUHE_BIS
_hund = wachhund.Wachhund(lambda t: None)
for von, bis, stunde, soll in (
        (23, 7, 23, True), (23, 7, 2, True), (23, 7, 6, True),
        (23, 7, 7, False), (23, 7, 14, False),      # über Mitternacht
        (13, 15, 14, True), (13, 15, 13, True),
        (13, 15, 15, False), (13, 15, 9, False),
        (13, 15, 23, False), (13, 15, 2, False),    # innerhalb eines Tages
        (0, 0, 12, False)):                         # kein Fenster
    config.WACH_RUHE_VON, config.WACH_RUHE_BIS = von, bis
    with mock.patch("jarvis.wachhund.dt") as falsch:
        falsch.datetime.now.return_value = dt.datetime(2026, 9, 13, stunde, 30)
        ist = _hund._nachtruhe()
    marke = "ok" if ist == soll else "FALSCH"
    print(f"  {marke:6} {von:02d}-{bis:02d} Uhr, es ist {stunde:02d}:30 "
          f"-> Ruhezeit {ist}")
    assert ist == soll, (von, bis, stunde)
config.WACH_RUHE_VON, config.WACH_RUHE_BIS = _von, _bis

print("\n=== Die Bremsen ===")
print("  1. Schweigt er, wenn niemand da ist?")
echt = zeit.leerlauf_sekunden
zeit.leerlauf_sekunden = lambda: config.WACH_ANWESEND + 60
config.WACH_RAM_PROZENT = 1                        # wuerde sonst ausloesen
gesagt.clear()
hund._runde()
print(f"     gesagt: {gesagt or '(nichts - richtig)'}")
assert not gesagt

print("  2. Und wenn jemand da ist?")
# Die Nachtruhe muss hier ausgeschaltet werden, sonst prüft dieser Test die
# Uhrzeit statt den Wachhund: nachts unterdrückt er alles, was nicht dringend
# ist - zu Recht. Ohne das bestand der Test nur tagsüber und schlug um 23:47
# fehl, obwohl nichts kaputt war.
ruhe_von, ruhe_bis = config.WACH_RUHE_VON, config.WACH_RUHE_BIS
jetzt = dt.datetime.now().hour
config.WACH_RUHE_VON = (jetzt + 2) % 24            # Fenster ohne "jetzt"
config.WACH_RUHE_BIS = (jetzt + 3) % 24
zeit.leerlauf_sekunden = lambda: 5
hund._runde()
print(f"     gesagt: {gesagt[0][:70] if gesagt else '(nichts)'}")
assert gesagt, "Ausserhalb der Nachtruhe muss er sich melden"

print("  2b. Und waehrend der Nachtruhe?")
# Umgekehrt: im Ruhefenster darf nur Dringendes durch. Das war der Fall, der
# den Test vorhin auffliegen liess - also wird er jetzt ausdruecklich geprueft.
config.WACH_RUHE_VON = jetzt
config.WACH_RUHE_BIS = (jetzt + 2) % 24
hund.zuletzt_gesprochen = 0                        # Pause zuruecksetzen
for regel in hund.regeln:
    regel.zuletzt = 0
gesagt.clear()
hund._runde()
leise = [s for s in gesagt if "Arbeitsspeicher" in s]
print(f"     gesagt: {gesagt or '(nichts - richtig)'}")
assert not leise, "In der Nachtruhe darf der Speicherhinweis nicht kommen"
config.WACH_RUHE_VON, config.WACH_RUHE_BIS = ruhe_von, ruhe_bis

print("  2c. Danach wieder ansprechbar")
config.WACH_RUHE_VON = (jetzt + 2) % 24
config.WACH_RUHE_BIS = (jetzt + 3) % 24
hund.zuletzt_gesprochen = 0
for regel in hund.regeln:
    regel.zuletzt = 0
gesagt.clear()
hund._runde()
print(f"     gesagt: {gesagt[0][:70] if gesagt else '(nichts)'}")
assert gesagt
# Zurückstellen, sonst erbt der spätere Nachtruhe-Abschnitt dieses Fenster
config.WACH_RUHE_VON, config.WACH_RUHE_BIS = ruhe_von, ruhe_bis

print("  3. Wiederholt er sich sofort?")
vorher = len(gesagt)
hund._runde()
hund._runde()
print(f"     weitere Meldungen: {len(gesagt) - vorher} (muss 0 sein)")
assert len(gesagt) == vorher

print(f"  4. Sperrzeit fuer den Speicher: "
      f"{config.WACH_RAM_SPERRE/60:.0f} Minuten")
speicher = [r for r in hund.regeln if r.name == "speicher"][0]
print(f"     naechste Meldung fruehestens in "
      f"{(speicher.sperrzeit - (time.monotonic() - speicher.zuletzt))/60:.0f} min")
assert speicher.sperrzeit >= 1800

print("\n=== Nachtruhe ===")
import datetime as dt
from unittest import mock
for stunde, erwartet in ((14, False), (23, True), (2, True), (7, False)):
    # Den Zeitpunkt VOR dem Ersetzen bauen - sonst ruft die Attrappe sich
    # selbst auf und liefert wieder eine Attrappe
    fest = dt.datetime(2026, 9, 13, stunde)
    with mock.patch.object(wachhund.dt, "datetime",
                           mock.Mock(now=lambda f=fest: f)):
        ist = hund._nachtruhe()
    print(f"  {stunde:>2} Uhr -> Nachtruhe {ist}")
    assert ist == erwartet, (stunde, ist)

zeit.leerlauf_sekunden = echt
config.WACH_RAM_PROZENT = alt
print("\nFertig.")
