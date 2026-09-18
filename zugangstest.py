"""Wer darf die Weboberfläche erreichen?

Über die Oberfläche lassen sich Lautstärke, Helligkeit und Programme steuern -
wer sie erreicht, steuert den Rechner. Der PC hängt in einem Tailnet und steht
dabei in wechselnden WLANs. Erlaubt sind deshalb genau zwei Gruppen: dieser
Rechner selbst und Geräte im eigenen Tailnet. Das WLAN, in dem der Rechner
gerade steht, gehört ausdrücklich NICHT dazu - dort sitzen fremde Geräte.
"""
import ipaddress

from fastapi.testclient import TestClient

from jarvis import config, web

fehler = 0


def pruefe(bedingung: bool, text: str, zusatz: str = "") -> None:
    global fehler
    fehler += not bedingung
    print(f"  {'ok    ' if bedingung else 'FEHLER'} {text}")
    if not bedingung and zusatz:
        print(f"         {zusatz}")


print("=== Welche Adressen gelten als erlaubt? ===")
netze = web._erlaubte_netze()
DURCH = [("127.0.0.1", "dieser Rechner"),
         ("127.0.0.53", "dieser Rechner, anderer Loopback"),
         ("::1", "dieser Rechner über IPv6"),
         ("100.84.15.44", "eigener Tailnet-Eintrag"),
         ("100.101.102.103", "anderes Gerät im Tailnet"),
         ("fd7a:115c:a1e0::af32:f2d", "Tailnet über IPv6")]
SPERRE = [("192.168.1.50", "Gerät im selben WLAN"),
          ("192.168.178.22", "Fritzbox-Netz"),
          ("10.0.0.5", "anderes lokales Netz"),
          ("172.16.3.4", "Firmennetz"),
          ("8.8.8.8", "offenes Internet"),
          ("100.63.255.255", "knapp unterhalb des Tailnet-Bereichs"),
          ("100.128.0.1", "knapp oberhalb des Tailnet-Bereichs")]

for roh, was in DURCH:
    erlaubt = any(ipaddress.ip_address(roh) in n for n in netze)
    pruefe(erlaubt, f"durchgelassen: {roh:26} {was}")
for roh, was in SPERRE:
    erlaubt = any(ipaddress.ip_address(roh) in n for n in netze)
    pruefe(not erlaubt, f"abgewiesen:    {roh:26} {was}")

print("\n=== Der laufende Server weist auch wirklich ab ===")
# Der Testclient darf sich eine Herkunftsadresse aussuchen - so lässt sich
# ein fremdes Gerät nachstellen, ohne ein zweites Netz zu brauchen.
for roh, was, erwartet in (("127.0.0.1", "dieser Rechner", 200),
                           ("100.84.15.44", "Tailnet", 200),
                           ("192.168.1.50", "WLAN-Nachbar", 403),
                           ("8.8.8.8", "Internet", 403)):
    with TestClient(web.app, client=(roh, 50000)) as klient:
        antwort = klient.get("/")
    pruefe(antwort.status_code == erwartet,
           f"{roh:16} {was:16} -> {antwort.status_code} (erwartet {erwartet})")

print("\n=== Auch die Schnittstellen sind geschützt, nicht nur die Seite ===")
# Eine Sperre, die nur die Startseite schützt, wäre keine - die eigentliche
# Macht steckt in /api.
for pfad in ("/api/werkzeuge", "/api/einstellungen", "/api/agenten"):
    with TestClient(web.app, client=("192.168.1.50", 50000)) as klient:
        antwort = klient.get(pfad)
    pruefe(antwort.status_code == 403, f"{pfad} ist gesperrt "
           f"(bekam {antwort.status_code})")

print("\n=== Geheimes bleibt verdeckt ===")
# Die Oberfläche ist aus dem ganzen Tailnet erreichbar. Was dort im Klartext
# steht, steht auf jedem Gerät im Tailnet im Klartext.
for schluessel, soll in (("JARVIS_API_KEY", True),
                         ("JARVIS_MAIL_PASSWORT", True),
                         ("JARVIS_TANKERKOENIG_KEY", True),
                         # Zahlen, keine Geheimnisse - sonst nicht mehr
                         # einstellbar
                         ("JARVIS_MAX_TOKENS", False),
                         ("JARVIS_CODE_TOKENS", False),
                         ("JARVIS_AGENT_TOKENS", False),
                         ("JARVIS_MAIL_BENUTZER", False),
                         ("JARVIS_WEB_ZUGANG", False)):
    ist = web._ist_geheim(schluessel)
    pruefe(ist == soll,
           f"{'verdeckt' if ist else 'sichtbar'}: {schluessel}")

print("\n=== Die Einstellung lässt sich ändern ===")
alt = config.WEB_ZUGANG
try:
    config.WEB_ZUGANG = "lokal"
    netze = web._erlaubte_netze()
    pruefe(not any(ipaddress.ip_address("100.84.15.44") in n for n in netze),
           "bei 'lokal' bleibt auch das Tailnet draußen")
    config.WEB_ZUGANG = "offen"
    with TestClient(web.app, client=("8.8.8.8", 50000)) as klient:
        antwort = klient.get("/")
    pruefe(antwort.status_code == 200, "bei 'offen' kommt jeder durch "
           "(bewusste Wahl)")
finally:
    config.WEB_ZUGANG = alt

print(f"\n  {fehler} Fehler")
raise SystemExit(1 if fehler else 0)
