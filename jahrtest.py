"""Jahreszahlen und Ortsnamen fuer die Stimme.

Anlass: Jarvis antwortete, das MIT sei 1861 gegruendet worden, und die Stimme
las "eintausendachthunderteinundsechzig". Auf Deutsch heisst das
"achtzehnhunderteinundsechzig" - ein Jahr wird anders gelesen als eine Menge.
Und "Massachusetts" kam als Kauderwelsch heraus.

Wichtig ist die Gegenprobe: eine Menge darf NICHT als Jahr gelesen werden.
"1500 Euro" bleibt "1500 Euro".
"""
from jarvis.voice import jahreszahlen, lautschrift

fehler = 0


def pruefe(ist: str, soll: str, was: str = "") -> None:
    global fehler
    ok = ist == soll
    fehler += not ok
    print(f"  {'ok    ' if ok else 'FEHLER'} {was or soll}")
    if not ok:
        print(f"         bekam: {ist!r}")
        print(f"         wollte: {soll!r}")


print("=== Jahreszahlen werden wie Jahre gelesen ===")
for zahl, soll in (
        ("1861", "achtzehnhunderteinundsechzig"),
        ("1900", "neunzehnhundert"),
        ("1999", "neunzehnhundertneunundneunzig"),
        ("1801", "achtzehnhundertein"),
        ("1110", "elfhundertzehn"),
        ("1815", "achtzehnhundertfuenfzehn"),
        ("2000", "zweitausend"),
        ("2006", "zweitausendsechs"),
        ("2026", "zweitausendsechsundzwanzig"),
):
    pruefe(jahreszahlen(zahl), soll, f"{zahl} -> {soll}")

print("\n=== Im Satz ===")
pruefe(jahreszahlen("Das MIT wurde 1861 gegruendet."),
       "Das MIT wurde achtzehnhunderteinundsechzig gegruendet.",
       "mitten im Satz")
pruefe(jahreszahlen("Von 1914 bis 1918."),
       "Von neunzehnhundertvierzehn bis neunzehnhundertachtzehn.",
       "zwei Jahreszahlen in einem Satz")

print("\n=== Mengen bleiben Mengen ===")
# Das ist die eigentliche Gefahr: alles Vierstellige umzuschreiben waere
# schlimmer als das Problem.
for satz in ("Das kostet 1500 Euro.",
             "Noch 1200 Meter.",
             "Die Datei hat 1800 Zeichen.",
             "1999 Personen waren da."):
    pruefe(jahreszahlen(satz), satz, f"unveraendert: {satz}")

print("\n=== Was gar keine Jahreszahl sein kann ===")
for satz in ("Version 10.1861 ist neu.",
             "Um 18:15 Uhr.",
             "Die Nummer 18611 gibt es nicht.",
             "Das Jahr 1050 war frueher.",     # unter 1100 - bleibt wie es ist
             "Er hat 153000 Alumni."):
    pruefe(jahreszahlen(satz), satz, f"unveraendert: {satz}")

print("\n=== Ortsnamen ===")
gesprochen = lautschrift("Das MIT liegt in Cambridge, Massachusetts.")
ok = "Massachusetts" not in gesprochen and "Cambridge" not in gesprochen
fehler += not ok
print(f"  {'ok    ' if ok else 'FEHLER'} Ortsnamen werden umgeschrieben")
if not ok:
    print(f"         {gesprochen!r}")
print(f"         {gesprochen}")

print("\n=== Beides zusammen, wie es wirklich vorkam ===")
echt = lautschrift("Das MIT in Cambridge, Massachusetts, wurde 1861 "
                   "gegruendet, Sir.")
for muss in ("achtzehnhunderteinundsechzig", "Mässa-tschuhssets", "Sör"):
    ok = muss in echt
    fehler += not ok
    print(f"  {'ok    ' if ok else 'FEHLER'} enthaelt {muss!r}")
print(f"         {echt}")

print(f"\n  {fehler} Fehler")
raise SystemExit(1 if fehler else 0)
