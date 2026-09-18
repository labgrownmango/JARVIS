"""Prüft Rechner, Zeitzonen und Kartenauskunft.

Der Rechner ist der wichtigste Teil davon. Sprachmodelle rechnen schlecht -
gemessen in dieser Sitzung: "66.490.00 Euro" als Preis, erfundene Namen in
einer Zusammenfassung, "vierhundertsechs" für 456. Bei Zahlen ist das kein
Schönheitsfehler: eine falsche Summe sieht genauso souverän aus wie eine
richtige. Deshalb wird hier wirklich gerechnet - und deshalb muss der Rechner
stimmen.
"""
import time

from jarvis import tools
from jarvis.rechner import RechenFehler, formatiere, rechne

fehler = 0


def pruefe(bedingung: bool, text: str, zusatz: str = "") -> None:
    global fehler
    fehler += not bedingung
    print(f"  {'ok    ' if bedingung else 'FEHLER'} {text}")
    if not bedingung and zusatz:
        print(f"         {zusatz}")


print("=== Rechnen ===")
AUFGABEN = [
    ("17*23", 391),
    ("2+3*4", 14),
    ("(2+3)*4", 20),
    ("2 hoch 10", 1024),
    ("wurzel(144)", 12),
    ("fakultaet(10)", 3628800),
    ("log(1000)", 3),
    ("max(3,9,2)", 9),
    ("min(5,2)", 2),
    ("summe(1,2,3,4)", 10),
    # So schreiben Menschen, nicht wie Python liest
    ("15 mal 4 minus 7", 53),
    ("5 geteilt durch 2", 2.5),
    ("20% von 80", 16),
    # Deutsche Zahlen: Punkt trennt Tausender, Komma ist das Dezimalzeichen
    ("3,5 * 2", 7),
    ("1.234,56 + 1000", 2234.56),
    ("1.000 * 3", 3000),
    ("1.234.567 + 1", 1234568),
    ("123 456 789 * 2", 246913578),
    # Aber englische Dezimalzahlen dürfen nicht kaputtgehen
    ("3.14 * 2", 6.28),
    ("0.5 + 0.25", 0.75),
]
for aufgabe, soll in AUFGABEN:
    try:
        ergebnis, gelesen = rechne(aufgabe)
        stimmt = abs(ergebnis - soll) < 1e-9
        pruefe(stimmt, f"{aufgabe:22} = {formatiere(ergebnis):>16}",
               f"erwartet {soll}, gelesen als [{gelesen}]")
    except RechenFehler as exc:
        pruefe(False, f"{aufgabe:22}", str(exc))

print("\n=== Was der Rechner NICHT tun darf ===")
# Der Ausdruck kommt vom Modell, also mittelbar aus dem Netz. Ein eval()
# hätte Zugriff auf alles, was Python kann - deshalb wird zerlegt statt
# ausgeführt.
GEFAEHRLICH = [
    '__import__("os").system("dir")',
    'open("geheim.txt").read()',
    'exec("x=1")',
    "[].__class__.__mro__",
    "globals()",
    "9**9**9",            # würde minutenlang rechnen
    "fakultaet(99999)",   # ebenso
]
for ausdruck in GEFAEHRLICH:
    try:
        ergebnis, _ = rechne(ausdruck)
        pruefe(False, f"DURCHGELASSEN: {ausdruck[:40]}", f"ergab {ergebnis}")
    except RechenFehler as exc:
        pruefe(True, f"abgewiesen: {ausdruck[:36]:38} {str(exc)[:34]}")

print("\n=== Deutsche Schreibweise der Ergebnisse ===")
for zahl, soll in ((391, "391"), (3628800, "3.628.800"), (2234.56, "2.234,56"),
                   (0.75, "0,75"), (2.5, "2,5"), (1000000, "1.000.000")):
    pruefe(formatiere(zahl) == soll, f"{zahl} -> {formatiere(zahl)}",
           f"erwartet {soll}")

print("\n=== Das Werkzeug selbst ===")
antwort = tools.rechnen("17*23")
pruefe("391" in antwort, f"rechnen('17*23'): {antwort[:60]}")
pruefe("rechnen" in tools.REGISTRY, "rechnen ist eingetragen")
pruefe("Was soll ich rechnen" in tools.rechnen(""), "leere Aufgabe abgefangen")

print("\n=== Preise: das richtige Wort, nicht die richtige Silbe ===")
# Gemessen: get_price("Solarpanel") antwortete mit dem Kurs von Solana, weil
# in "SOLarpanel" das Kürzel "sol" steckt. Eine Frage nach Solarmodulen mit
# einem Kryptokurs zu beantworten ist genau die Art Fehler, die niemand
# bemerkt - die Antwort sieht ja aus wie eine Antwort.
KEINE_QUELLE = ["Solarpanel", "ein Solar panel pro Einheit", "Solaranlage",
                "Etherpapier", "eine SSD", "Bratpfanne", "Adapterkabel",
                "Sonnenschirm", "Eurokiste", "Yenta"]
for frage in KEINE_QUELLE:
    antwort = tools.get_price(frage)
    daneben = "CoinGecko" in antwort or "EZB" in antwort
    pruefe(not daneben, f"kein Kurs für {frage!r}", antwort[:80])
    if not daneben:
        pruefe("search_web" in antwort,
               f"verweist auf die Suche: {frage[:22]}")

ECHTE = [("Bitcoin", "CoinGecko"), ("was kostet sol", "Solana"),
         ("Ethereum", "CoinGecko"), ("Dollar", "USD"),
         ("Schweizer Franken", "CHF"), ("Strom gerade", "Cent")]
for frage, muss in ECHTE:
    antwort = tools.get_price(frage)
    pruefe(muss in antwort, f"{frage[:22]:24} -> {antwort[:56]}")

pruefe("Wonach genau" in tools.get_price(""), "leere Frage wird abgefangen")
pruefe("Erfinde keinen Preis" in tools.get_price("Bratpfanne"),
       "das Erfinden wird ausdrücklich untersagt")

print("\n=== Zeitzonen ===")
# Kein eigenes Werkzeug und kein Netzdienst: die Zonen bringt Python mit.
hier = tools.get_time()
pruefe("Uhr" in hier, f"hier: {hier}")
for ort in ("New York", "Tokio", "London", "Sydney", "Kalifornien"):
    antwort = tools.get_time(ort=ort)
    pruefe("Uhr" in antwort and "gegenueber hier" in antwort,
           f"{ort:14} {antwort[:72]}")
pruefe("1 Stunde " in tools.get_time(ort="London"),
       "Einzahl bei einer Stunde", tools.get_time(ort="London"))
pruefe("kenne ich nicht" in tools.get_time(ort="Qwxzyfjklstadt"),
       "unbekannter Ort wird gemeldet")

print("\n=== Karte (OpenStreetMap) ===")
start = time.perf_counter()
ort = tools.ort_info(ort="Köln")
pruefe("50.9" in ort and "6.9" in ort, f"Köln: {ort[:80]}")

weit = tools.ort_info(von="Köln", nach="München")
# Luftlinie Köln-München sind rund 456 km - ein grober Fehler fiele hier auf
zahlen = [int(t) for t in weit.split() if t.isdigit()]
pruefe(any(440 <= z <= 470 for z in zahlen), f"Entfernung: {weit[:90]}")

fern = tools.ort_info(von="Berlin", nach="New York")
zahlen = [int(t) for t in fern.split() if t.isdigit()]
pruefe(any(6200 <= z <= 6500 for z in zahlen), f"Berlin-New York: {fern[:80]}")

pruefe("Köln" in tools.ort_info(breite=50.94, laenge=6.96),
       "Koordinaten -> Ort")
pruefe("finde ich nicht" in tools.ort_info(ort="Qwxzyfjklstadt"),
       "unbekannter Ort wird gemeldet")
pruefe("Welcher Ort" in tools.ort_info(), "leere Anfrage abgefangen")
print(f"         {time.perf_counter() - start:.0f}s (je Anfrage 1 s Pause - "
      f"so verlangt es OpenStreetMap)")

print("\n=== Zusammengelegte Werkzeuge ===")
# Neun Einträge im Schema wurden zu dreien. Der Preis: das Modell muss die
# Aktion mitwählen. Dass die Aktionen greifen, wird hier geprüft.
pruefe("Keine Erinnerungen" in tools.erinnerung_werkzeug("auflisten")
       or "Erinnerung" in tools.erinnerung_werkzeug("auflisten"),
       "erinnerung: auflisten")
pruefe("kenne ich nicht" in tools.erinnerung_werkzeug("quatsch"),
       "erinnerung: unbekannte Aktion wird gemeldet")
pruefe("kenne ich nicht" in tools.gedaechtnis_werkzeug("quatsch"),
       "gedaechtnis: unbekannte Aktion wird gemeldet")
pruefe("Was genau" in tools.gedaechtnis_werkzeug("vergessen", ""),
       "gedaechtnis: vergessen ohne Angabe löscht nicht alles")
prozesse = tools.system_info("prozesse")
pruefe("MB" in prozesse, f"system_info('prozesse'): {prozesse[:60]}")
for alt in ("list_processes", "remember", "set_reminder"):
    pruefe(alt not in tools.REGISTRY, f"{alt} ist nicht mehr im Schema")

print(f"\n  {fehler} Fehler")
raise SystemExit(1 if fehler else 0)
