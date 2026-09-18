"""Prüft die Schutzgrenzen für Lautstärke und Helligkeit."""
import threading
import time

from jarvis import config, regler, rueckfrage, tools

anfang, war_stumm = regler.lautstaerke_lesen()


def antworten(wie: str, verzoegerung: float = 0.4):
    """Beantwortet die naechste Rueckfrage automatisch."""
    def warten():
        time.sleep(verzoegerung)
        for _ in range(40):
            offen = rueckfrage.offene()
            if offen:
                print(f"    [Rückfrage: {offen[0].text}]")
                print(f"    [Folgen: {offen[0].auswirkungen[:70]}...]")
                rueckfrage.beantworten(offen[0].id, wie)
                return
            time.sleep(0.2)
    threading.Thread(target=warten, daemon=True).start()


print(f"Grenzen: Lautstärke bis {config.LAUTSTAERKE_MAX_FREI:.0f} Prozent, "
      f"Helligkeit bis {config.HELLIGKEIT_MIN_FREI} Prozent frei\n")

print("=== Lautstärke unterhalb der Grenze: keine Nachfrage ===")
start = time.perf_counter()
print(" ", tools.set_volume(prozent=60))
print(f"  ({time.perf_counter()-start:.1f}s - ohne Rückfrage)")
assert time.perf_counter() - start < 2

print("\n=== Lautstärke darüber: Freigabe erteilt ===")
antworten("Einmal erlauben")
print(" ", tools.set_volume(prozent=95))
print(f"  tatsächlich: {regler.lautstaerke_lesen()[0]} Prozent")
assert regler.lautstaerke_lesen()[0] == 95

print("\n=== Lautstärke darüber: abgelehnt ===")
regler.lautstaerke_setzen(60)
antworten("Ablehnen")
print(" ", tools.set_volume(prozent=95))
print(f"  tatsächlich: {regler.lautstaerke_lesen()[0]} Prozent (begrenzt)")
assert regler.lautstaerke_lesen()[0] == 80

print("\n=== Auch schrittweise wird gebremst ===")
regler.lautstaerke_setzen(78)
antworten("Ablehnen")
print(" ", tools.set_volume(direction="lauter", steps=15))
print(f"  tatsächlich: {regler.lautstaerke_lesen()[0]} Prozent")

regler.lautstaerke_setzen(anfang)
regler.stumm_setzen(war_stumm)
print(f"  wiederhergestellt: {regler.lautstaerke_lesen()[0]} Prozent")

print("\n=== Helligkeit bis 50: keine Nachfrage ===")
for wert in (90, 70, 50):
    start = time.perf_counter()
    tools.set_brightness(prozent=wert)
    print(f"  auf {wert} gewünscht -> {regler._gamma_stand} Prozent "
          f"({time.perf_counter()-start:.1f}s, ohne Rückfrage)")
    assert time.perf_counter() - start < 3, "hier darf nichts fragen"

print("\n=== Darunter greift Windows' eigene Grenze ===")
tools.set_brightness(prozent=100)
antworten("Ablehnen")
antwort = tools.set_brightness(prozent=30)
print(f"  auf 30 gewünscht: {antwort[:100]}")
print(f"  tatsächlich: {regler._gamma_stand} Prozent")
assert regler._gamma_stand >= 50

tools.set_brightness(richtung="zurueck")
print(f"\nEndstand: {regler.lautstaerke_lesen()[0]} Prozent Lautstärke, "
      f"Helligkeit {regler._gamma_stand} Prozent")
print("Fertig.")
