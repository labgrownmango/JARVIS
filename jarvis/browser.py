"""Ein ferngesteuerter Browser - so eng gefasst, dass er kein Einfallstor ist.

Warum es ihn ueberhaupt gibt: manche Seiten sind ohne JavaScript leer. Nicht
nur Shops - auch Nachrichtenseiten, Dokumentationen, Fahrplaene. read_page
bekommt dort ein Geruest ohne Inhalt.

Warum er trotzdem zum JavaScript-Verbot passt: das Verbot sollte verhindern,
dass ueber Jarvis etwas auf den Rechner kommt. Fremdes JavaScript laeuft hier
NICHT in Jarvis' Python-Prozess, sondern in der Renderer-Sandbox des
Browsers - derselben, in der jeder Mensch taeglich fremde Seiten oeffnet.

Die Zusicherungen, jede einzeln pruefbar in browsertest.py:

1. KEINE DOWNLOADS. Der Browser bekommt kein Download-Verzeichnis, jede
   Download-Anfrage wird abgebrochen, und Antworten, die nicht Text sind,
   werden schon auf Netzebene verworfen. Nicht "verboten" - nicht vorhanden.
2. NUR ERLAUBTE ADRESSEN. Was nicht auf der Liste steht, wird gar nicht erst
   geladen. Das gilt auch fuer Weiterleitungen und fuer alles, was die Seite
   selbst nachladen will.
3. NICHTS NACH INNEN. localhost, 127.0.0.1, das Heimnetz, das Tailnet - alles
   gesperrt, auch wenn ein Name auf der Erlaubnisliste dorthin zeigt.
   Geprueft wird die aufgeloeste Adresse, nicht nur der Name.
4. NUR HTTP UND HTTPS. file:, blob:, data:, ftp: werden abgebrochen.
5. KEIN JAVASCRIPT, ausser es wird ausdruecklich eingeschaltet
   (JARVIS_BROWSER_JS=1). Ohne JavaScript ist eine Seite ein Textdokument
   und kann von sich aus gar nichts.
6. WEGWERF-PROFIL. Jede Anfrage bekommt einen frischen Kontext, danach ist er
   weg. Keine Cookies, kein Speicher, keine Service Worker, die etwas
   ueberleben.
7. NICHTS ALS TEXT KOMMT ZURUECK. Keine Datei, kein Bild, kein Binaerinhalt.
8. KEINE ZWEITEN FENSTER. Was window.open oder ein Klick oeffnet, wird
   sofort geschlossen.
9. AUF ZURUF, NICHT AUF DAUER. Gestartet wenn gebraucht, danach beendet.
   Zeitlimit haart.
10. KEINE GERAETE. Kamera, Mikrofon, Standort, Benachrichtigungen,
   Zwischenablage - alles abgelehnt.

Was das NICHT abdeckt, offen gesagt: eine unbekannte Luecke im Browser selbst,
mit der jemand aus der Renderer-Sandbox ausbricht. Dagegen hilft hier nichts -
nur ein aktueller Browser und der Virenschutz. Die Sandbox bleibt deshalb
unangetastet: kein --no-sandbox, keine Lockerung der Seitentrennung. Heute ist
dieses Risiko null, weil der Browser abgeschaltet ist; danach ist es klein,
aber nicht null.
"""
from __future__ import annotations

import asyncio
import re
import threading
from pathlib import Path

from . import config

# Was gar nicht erst angefragt werden darf. Video und Ton braucht ein
# Textleser nie; WebSocket und EventSource waeren eine offene Leitung nach
# draussen, die sich der Kontrolle entzieht.
_NIE = ("media", "font", "websocket", "eventsource", "manifest")

_SCHRIFT = re.compile(r"(?is)<(script|style|noscript|nav|header|footer)[^>]*>"
                      r".*?</\1>")
_TAG = re.compile(r"""(?s)<(?:[^>"']|"[^"]*"|'[^']*')*>""")


class BrowserFehler(Exception):
    pass


def _ist_lokal(wirt: str) -> bool:
    """Zeigt der Name auf diesen Rechner oder ins eigene Netz?

    Das ist die gefaehrlichste Richtung und die am leichtesten uebersehene:
    Jarvis' eigener Server lauscht auf Port 80, der Router auf 192.168.x.1,
    das Tailnet auf 100.64.0.0/10. Eine fremde Seite, die den Browser dazu
    bringt, dort anzuklopfen, redet mit Diensten, die niemand aus dem
    Internet erreichen koennen soll - und die keinen Grund haben,
    misstrauisch zu sein, weil die Anfrage von diesem Rechner kommt.

    Geprueft wird der Name UND die Adresse, auf die er zeigt: ein Eintrag auf
    der Erlaubnisliste, dessen DNS plotzlich 127.0.0.1 liefert, kaeme sonst
    durch.
    """
    import ipaddress
    import socket

    wirt = wirt.strip().rstrip(".").lower()
    if not wirt:
        return True
    if wirt in ("localhost", "localhost.localdomain") or wirt.endswith(
            (".localhost", ".local", ".internal", ".home", ".lan")):
        return True

    adressen = []
    try:                                    # schon eine IP hingeschrieben?
        adressen.append(ipaddress.ip_address(wirt.strip("[]")))
    except ValueError:
        try:
            for eintrag in socket.getaddrinfo(wirt, None):
                try:
                    adressen.append(ipaddress.ip_address(eintrag[4][0]))
                except ValueError:
                    continue
        except OSError:
            # Nicht aufloesbar - dann kommt ohnehin keine Verbindung
            # zustande. Nicht als lokal werten, sonst blockiert ein
            # DNS-Aussetzer eine erlaubte Seite.
            return False

    if not adressen:
        return False
    for adr in adressen:
        if (adr.is_private or adr.is_loopback or adr.is_link_local
                or adr.is_reserved or adr.is_multicast or adr.is_unspecified):
            return True
        # Tailscale: 100.64.0.0/10 gilt als "shared address space" und wird
        # von is_private nicht erfasst.
        if adr.version == 4 and adr in ipaddress.ip_network("100.64.0.0/10"):
            return True
        if adr.version == 6 and adr in ipaddress.ip_network("fd7a:115c:a1e0::/48"):
            return True
    return False


def erlaubt(url: str) -> bool:
    """Steht die Adresse auf der Liste - und zeigt sie nach draussen?"""
    from .tools import _domain

    if not url.lower().startswith(("http://", "https://")):
        return False
    wirt = _domain(url).lower()
    if wirt.startswith("www."):
        wirt = wirt[4:]
    treffer = False
    for eintrag in config.BROWSER_ERLAUBT:
        e = eintrag.strip().lower().lstrip(".")
        if not e:
            continue
        if wirt == e or wirt.endswith("." + e):
            treffer = True
            break
    if not treffer:
        return False
    return not _ist_lokal(wirt)


def _text_aus(html: str, grenze: int) -> str:
    import html as _html

    ohne = _SCHRIFT.sub(" ", html)
    text = _html.unescape(_TAG.sub(" ", ohne))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:grenze]


async def _holen(url: str, grenze: int, wartezeit: float) -> str:
    from playwright.async_api import async_playwright

    gefangen: list[str] = []          # abgewehrte Versuche, fuer den Bericht

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            channel=config.BROWSER_KANAL,
            headless=True,
            args=[
                "--disable-extensions",
                "--disable-plugins",
                "--disable-background-networking",
                "--disable-sync",
                "--no-first-run",
                "--disable-features=WebRTC,MediaRouter,Translate",
                "--mute-audio",
            ],
        )
        try:
            # accept_downloads=False: Playwright bricht jeden Download ab.
            # Dazu ein Wegwerf-Kontext - nichts ueberlebt diese Anfrage.
            kontext = await browser.new_context(
                accept_downloads=False,
                java_script_enabled=config.BROWSER_JS,
                permissions=[],                 # nichts erlaubt
                service_workers="block",
                bypass_csp=False,
                user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/131.0 Safari/537.36"),
                locale="de-DE",
            )

            async def wache(route, anfrage):
                """Jede einzelne Anfrage der Seite geht hier durch."""
                ziel = anfrage.url
                # Nur http und https. file:, blob:, data:, ftp: und was es
                # sonst noch gibt haben hier nichts verloren - eine Seite,
                # die nach file:///C:/Users/... greift, will nichts Gutes.
                if not ziel.lower().startswith(("http://", "https://")):
                    gefangen.append(ziel[:90])
                    await route.abort()
                    return
                if anfrage.resource_type in _NIE:
                    await route.abort()
                    return
                if not erlaubt(ziel):
                    gefangen.append(ziel[:90])
                    await route.abort()
                    return
                await route.continue_()

            await kontext.route("**/*", wache)

            seite = await kontext.new_page()
            seite.on("download", lambda d: asyncio.ensure_future(d.cancel()))
            seite.on("dialog", lambda d: asyncio.ensure_future(d.dismiss()))

            def neues_fenster(andere) -> None:
                """Ein Klick oder window.open soll ins Leere laufen.

                Wichtig: kontext.on("page") feuert AUCH fuer die Seite, die
                wir selbst gerade angelegt haben. Der frühere Code schloss
                deshalb sein eigenes Fenster, sobald es entstand - der
                Browser war damit vollstaendig funktionsunfaehig, und es
                fiel nicht auf, weil er standardmaessig abgeschaltet ist
                und der Test nur die Wachen prueft.
                """
                if andere is seite:
                    return
                andere.on("download", lambda d: asyncio.ensure_future(d.cancel()))
                asyncio.ensure_future(andere.close())

            kontext.on("page", neues_fenster)

            try:
                antwort = await seite.goto(url, timeout=int(wartezeit * 1000),
                                           wait_until="domcontentloaded")
            except Exception as fehler:
                # Zeigt die Adresse auf eine Datei, will Chromium sie
                # herunterladen. Der Download wird abgebrochen, und die
                # Navigation scheitert mit einem nichtssagenden "Error".
                # Genau das ist der gewuenschte Ausgang - nur die Meldung
                # muss verstaendlich sein.
                wortlaut = str(fehler).lower()
                if any(w in wortlaut for w in ("download", "aborted",
                                               "net::err_aborted")):
                    raise BrowserFehler(
                        "Das ist keine Textseite, sondern eine Datei - "
                        "heruntergeladen wird nichts.") from None
                raise
            if antwort is None:
                raise BrowserFehler("Die Seite hat nicht geantwortet.")
            if antwort.status >= 400:
                raise BrowserFehler(f"Die Seite antwortete mit "
                                    f"{antwort.status}.")
            typ = (antwort.headers.get("content-type") or "").lower()
            if not typ.startswith(("text/html", "application/xhtml",
                                   "text/plain")):
                raise BrowserFehler(f"Das ist keine Textseite, sondern "
                                    f"{typ.split(';')[0] or 'unbekannt'}.")

            # Kurz warten, damit nachgeladener Inhalt da ist - aber nur kurz.
            try:
                await seite.wait_for_load_state("networkidle",
                                                timeout=min(4000, int(wartezeit * 500)))
            except Exception:
                pass
            html = await seite.content()
            return _text_aus(html, grenze)
        finally:
            await browser.close()


def lesen(url: str, zeichen: int = 3000) -> str:
    """Eine Seite MIT JavaScript lesen. Gibt Text zurueck, sonst nichts."""
    if not config.BROWSER_AN:
        return ("Der Browser ist abgeschaltet. Einschalten mit "
                "JARVIS_BROWSER=1 in der .env - und nur, wenn du weisst, "
                "warum du ihn brauchst.")
    if not erlaubt(url):
        from .tools import _domain

        return (f"{_domain(url)} steht nicht auf der Liste der erlaubten "
                f"Seiten. Eintragen laesst sie sich in der .env unter "
                f"JARVIS_BROWSER_ERLAUBT.")

    grenze = max(200, min(int(zeichen or 3000), 8000))
    ergebnis: dict = {}

    def arbeiten() -> None:
        try:
            ergebnis["text"] = asyncio.run(
                _holen(url, grenze, config.BROWSER_ZEITLIMIT))
        except BrowserFehler as fehler:
            ergebnis["fehler"] = str(fehler)
        except Exception as fehler:
            ergebnis["fehler"] = (f"Der Browser kam nicht durch: "
                                  f"{type(fehler).__name__}")

    # In einem eigenen Thread, damit ein haengender Browser den Rest nicht
    # mitreisst - und mit hartem Zeitlimit darueber.
    faden = threading.Thread(target=arbeiten, daemon=True)
    faden.start()
    faden.join(timeout=config.BROWSER_ZEITLIMIT + 8)
    if faden.is_alive():
        return ("Der Browser hat zu lange gebraucht und wurde abgebrochen.")
    if "fehler" in ergebnis:
        return ergebnis["fehler"]
    text = ergebnis.get("text", "").strip()
    if not text:
        return "Die Seite enthaelt keinen lesbaren Text."
    return text


def verfuegbar() -> bool:
    """Ist Playwright da und ein Browser installiert?"""
    try:
        import playwright  # noqa: F401
    except ImportError:
        return False
    return bool(_browserdatei())


def _browserdatei() -> Path | None:
    for pfad in (
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    ):
        if pfad.exists():
            return pfad
    return None
