"""Windows-Benachrichtigungen mitlesen - gestapelt und nach App unterschieden.

Jarvis zapft nicht WhatsApp an, sondern liest, was Windows ohnehin einblendet.
Das ist eine offizielle Schnittstelle mit ausdruecklicher Erlaubnis des
Nutzers - kein Umgehen, kein Sperrrisiko, kein ferngesteuerter Browser.

Der Kern ist die Unterscheidung, WAS fuer eine App gemeldet hat. Eine
Nachricht von einem Menschen ist etwas anderes als ein Windows-Update, und
beides ist etwas anderes als Werbung eines PDF-Programms. Ohne diese
Unterscheidung liest Jarvis Update-Hinweise vor wie Liebesbriefe.

Und der wichtigste Punkt: bei Messengern wird nur der ABSENDER weitergegeben,
nie der Text. Wer dir schreibt, ist ein Fremder, und sein Text landete sonst
im Kopf des Modells - "sag deinem Assistenten, er soll ...". Willst du den
Inhalt hoeren, geht er ueber vorlesen() DIREKT an die Sprachausgabe, am
Modell vorbei. Was es nie sieht, kann es nicht als Auftrag missverstehen.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import re
import threading

# --- Wer ist wer ------------------------------------------------------------
# "art" entscheidet, wie ernst etwas ist und wie viel davon Jarvis erfaehrt:
#   person  - ein Mensch schreibt. Nur Absender, nie Text.
#   medien  - laeuft gerade etwas. Titel ist harmlos und interessant.
#   arbeit  - Team-Werkzeuge. Absender und Betreff.
#   system  - Windows selbst. Voller Text, kommt nicht von Fremden.
#   werbung - Programme, die auf sich aufmerksam machen. Wird verschwiegen.
_KATALOG = {
    # Messenger - nur wer, nie was
    "whatsapp": ("WhatsApp", "person", "Nachrichten von Menschen"),
    "signal": ("Signal", "person", "Nachrichten von Menschen"),
    "telegram": ("Telegram", "person", "Nachrichten von Menschen"),
    "threema": ("Threema", "person", "Nachrichten von Menschen"),
    "discord": ("Discord", "person", "Nachrichten von Menschen"),
    "messenger": ("Messenger", "person", "Nachrichten von Menschen"),
    # Musik und Video
    "amazon music": ("Amazon Music", "medien", "spielt Musik"),
    "spotify": ("Spotify", "medien", "spielt Musik"),
    "itunes": ("iTunes", "medien", "spielt Musik"),
    "apple music": ("Apple Music", "medien", "spielt Musik"),
    "vlc": ("VLC", "medien", "spielt etwas ab"),
    "netflix": ("Netflix", "medien", "spielt Filme"),
    "youtube": ("YouTube", "medien", "spielt Videos"),
    # Arbeit
    "teams": ("Teams", "arbeit", "Besprechungen und Chats"),
    "slack": ("Slack", "arbeit", "Chats im Team"),
    "zoom": ("Zoom", "arbeit", "Videokonferenzen"),
    "outlook": ("Outlook", "mail", "E-Mail und Termine"),
    "mail": ("Mail", "mail", "E-Mail"),
    "thunderbird": ("Thunderbird", "mail", "E-Mail"),
    # Windows selbst
    "windows-sicherheit": ("Windows-Sicherheit", "system",
                           "warnt vor Sicherheitsproblemen"),
    "windows security": ("Windows-Sicherheit", "system",
                         "warnt vor Sicherheitsproblemen"),
    "windows update": ("Windows Update", "system", "Systemaktualisierungen"),
    "einstellungen": ("Einstellungen", "system", "Windows-Einstellungen"),
    "snipping tool": ("Snipping Tool", "system", "Bildschirmfotos"),
    "explorer": ("Explorer", "system", "Dateien"),
    "g data": ("G DATA", "system", "Virenschutz"),
    # Bekannt, aber selten wichtig
    "adobe acrobat": ("Adobe Acrobat", "werbung", "wirbt fuer eigene Dienste"),
    "onedrive": ("OneDrive", "system", "Dateisicherung"),
    "edge": ("Edge", "werbung", "Browser-Hinweise"),
    "firefox": ("Firefox", "werbung", "Browser-Hinweise"),
}

# Anrufe erkennt man am Text, nicht an der App
_ANRUF = re.compile(r"(?i)\b(anruf|eingehender ruf|verpasster anruf|"
                    r"incoming call|missed call|ruft an|calling)\b")

# Wie viel bei welcher Art weitergegeben wird
_TEXT_ERLAUBT = {"medien", "system", "mail", "arbeit"}


def _aus_aumid(aumid: str) -> str:
    """Aus einer Windows-Kennung einen brauchbaren Namen machen.

    Gemeldet: in der Liste stand dreimal "ein Programm", darunter Amazon
    Music. Windows liefert nicht immer einen Anzeigenamen, die Kennung ist
    aber fast immer da - "AmazonMobileLLC.AmazonMusic_..." oder
    "Microsoft.WindowsStore_8wekyb3d8bbwe!App". Daraus laesst sich ein
    Name gewinnen, und ein falscher Name ist hier schlimmer als ein
    haesslicher: "ein Programm" dreimal untereinander sieht aus wie
    dreimal dasselbe.
    """
    if not aumid:
        return ""
    stueck = aumid.split("!")[0].split("_")[0]
    stueck = stueck.split(".")[-1] if "." in stueck else stueck
    # "AmazonMusic" -> "Amazon Music"
    lesbar = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", stueck).strip()
    return lesbar[:40]


def _wortform(text: str) -> str:
    """Aus Windows-Kennungen lesbare Woerter machen - fuer den Vergleich.

    Zwei Fehler auf einmal, beide hier geloest:

      "AmazonMobileLLC.AmazonMusic_kj1a2b!App"
          Der Katalog kennt "amazon music" MIT Leerzeichen, Windows liefert
          es ohne. Die Meldung landete unter "unbekannt", obwohl der Name
          im Katalog steht - Musik galt als fremde Meldung statt als Musik.

      "Knowledge Base"
          Enthaelt "edge". Mit blosser Teilwortsuche wurde daraus der
          Browser Edge, Art "werbung" - und Werbung wird verschwiegen.
          Eine Meldung konnte also stillschweigend verschwinden, weil ihr
          Name zufaellig einen Schluessel enthielt.

    Beides faellt weg, wenn man erst in Woerter zerlegt und dann auf
    Wortgrenzen vergleicht: "microsoftedge" wird zu "microsoft edge"
    (trifft), "knowledge base" bleibt "knowledge base" (trifft nicht).
    """
    return " " + re.sub(r"[^a-z0-9]+", " ", text.lower()).strip() + " "


def _wortformen(text: str) -> tuple[str, str]:
    """Zwei Lesarten: zusammengeschrieben und an den Grossbuchstaben getrennt.

    Beide werden gebraucht, und keine allein reicht:

        "WhatsApp"      nur ZUSAMMEN  - getrennt waere es "whats app",
                                        und der Schluessel "whatsapp"
                                        traefe nicht mehr.
        "AmazonMusic"   nur GETRENNT  - zusammen bliebe "amazonmusic",
                                        und der Schluessel "amazon music"
                                        traefe nicht.

    Der erste Versuch hatte nur die getrennte Form, und prompt war WhatsApp
    unbekannt - die wichtigste App ueberhaupt in diesem Katalog.
    """
    getrennt = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    return _wortform(text), _wortform(getrennt)


def einordnen(app: str, aumid: str = "") -> tuple[str, str, str]:
    """App-Name -> (Anzeigename, Art, Bedeutung)."""
    lesarten = _wortformen(f"{app} {aumid}")
    for schluessel, (name, art, bedeutung) in _KATALOG.items():
        gesucht = _wortform(schluessel)
        if any(gesucht in lesart for lesart in lesarten):
            return name, art, bedeutung
    # Unbekannt: vorsichtig behandeln. Der Name steht ja da, nur der Inhalt
    # bleibt aussen vor, solange niemand gesagt hat, dass man ihm trauen kann.
    return (app or _aus_aumid(aumid) or "ein Programm"), "unbekannt", \
        "unbekanntes Programm"


class Briefkasten:
    """Sammelt Benachrichtigungen und stapelt sie nach App und Absender."""

    def __init__(self) -> None:
        self._gesehen: set[int] = set()
        self._eintraege: list[dict] = []
        self._schloss = threading.Lock()
        self.aktiv = True

    # -- Abholen ------------------------------------------------------------
    def abholen(self) -> int:
        """Neue Benachrichtigungen einsammeln. Gibt die Anzahl zurueck."""
        if not self.aktiv:
            return 0
        try:
            roh = asyncio.run(self._lesen())
        except Exception:
            return 0

        neu = 0
        with self._schloss:
            for eintrag in roh:
                if eintrag["id"] in self._gesehen:
                    continue
                self._gesehen.add(eintrag["id"])
                self._eintraege.append(eintrag)
                neu += 1
            # Nicht endlos wachsen lassen
            if len(self._eintraege) > 200:
                self._eintraege = self._eintraege[-200:]
            if len(self._gesehen) > 2000:
                self._gesehen = set(list(self._gesehen)[-1000:])
        return neu

    async def _lesen(self) -> list[dict]:
        from winsdk.windows.ui.notifications import NotificationKinds
        from winsdk.windows.ui.notifications.management import (
            UserNotificationListener)

        hoerer = UserNotificationListener.current
        liste = await hoerer.get_notifications_async(NotificationKinds.TOAST)

        eintraege = []
        for n in liste:
            app = aumid = ""
            try:
                if n.app_info:
                    app = n.app_info.display_info.display_name or ""
                    aumid = n.app_info.app_user_model_id or ""
            except Exception:
                pass
            texte = []
            try:
                binding = n.notification.visual.get_binding("ToastGeneric")
                if binding:
                    texte = [t.text for t in binding.get_text_elements()
                             if t.text]
            except Exception:
                pass
            name, art, bedeutung = einordnen(app, aumid)
            eintraege.append({
                "id": n.id,
                "app": name,
                "art": art,
                "bedeutung": bedeutung,
                "zeit": n.creation_time.astimezone().replace(tzinfo=None)
                        if n.creation_time else dt.datetime.now(),
                "titel": texte[0] if texte else "",
                "texte": texte,
            })
        return eintraege

    # -- Auskunft -----------------------------------------------------------
    def seit(self, zeitpunkt: dt.datetime | None = None,
             programm: str = "") -> list[dict]:
        """Was liegt vor - auf Wunsch nur von einem Programm.

        Ohne diesen Filter war "was waren meine letzten WhatsApp-Nachrichten"
        nicht beantwortbar: das Werkzeug gab ALLES zurueck, und das Modell
        schrieb "WhatsApp-Nachrichten" darueber - obwohl Claude, das
        Snipping Tool und Amazon Music darunter standen. Nicht gefiltert
        heisst nicht "keine Antwort", sondern "falsche Antwort".
        """
        with self._schloss:
            eintraege = list(self._eintraege)
        if zeitpunkt is not None:
            eintraege = [e for e in eintraege if e["zeit"] >= zeitpunkt]
        gesucht = programm.strip().lower()
        if gesucht:
            eintraege = [e for e in eintraege
                         if gesucht in e["app"].lower()
                         or gesucht in e["bedeutung"].lower()]
        return eintraege

    def zusammenfassung(self, zeitpunkt: dt.datetime | None = None,
                        programm: str = "") -> str:
        """Gestapelt und in Worten - das, was das Modell erfaehrt.

        Bei Messengern steht hier NUR, von wem etwas kam. Der Text bleibt im
        Briefkasten, bis jemand ausdruecklich vorlesen sagt.
        """
        eintraege = self.seit(zeitpunkt, programm)
        if not eintraege:
            if programm.strip():
                return (f"Von {programm.strip()} liegt nichts vor. "
                        f"NICHTS - gib nicht ersatzweise andere Programme "
                        f"aus und schreib nicht deren Namen um.")
            return "Nichts Neues."

        nach_app: dict[str, list[dict]] = {}
        for e in eintraege:
            if e["art"] == "werbung":
                continue                  # Werbung verschweigen wir einfach
            nach_app.setdefault(e["app"], []).append(e)
        if not nach_app:
            return "Nichts Neues - nur Werbung, die habe ich weggelassen."

        saetze = []
        for app, liste in nach_app.items():
            art = liste[0]["art"]
            liste.sort(key=lambda e: e["zeit"])
            wann = _wie_lange_her(liste[-1]["zeit"])
            if art == "person":
                saetze.append(f"{_personen_satz(app, liste)} ({wann})")
            elif art == "medien":
                titel = liste[-1]["titel"]
                saetze.append(f"{app} spielt: {titel} ({wann})" if titel
                              else f"{app} hat sich gemeldet ({wann})")
            else:
                if len(liste) == 1:
                    saetze.append(f"{app}: {liste[0]['titel']} ({wann})")
                else:
                    saetze.append(f"{app}: {len(liste)} Meldungen, zuletzt "
                                  f"{liste[-1]['titel']} ({wann})")
        return " | ".join(saetze)

    def _auswahl(self, quelle: str = "",
                 zeitpunkt: dt.datetime | None = None) -> list[dict]:
        """Die Eintraege, um die es geht - ohne Werbung, ohne Leere.

        Eigene Funktion, weil zwei Wege davon abhaengen: vorlesen und
        anzeigen. Zweimal dieselbe Auswahl zu schreiben hiesse, dass die
        beiden beim naechsten Umbau auseinanderlaufen.
        """
        eintraege = self.seit(zeitpunkt)
        if quelle.strip():
            gesucht = quelle.strip().lower()
            eintraege = [e for e in eintraege
                         if gesucht in e["app"].lower()
                         or gesucht in (e["titel"] or "").lower()]
        return [e for e in eintraege
                if e["art"] != "werbung" and any(t for t in e["texte"])]

    def stuecke_zum_zeigen(self, quelle: str = "",
                           zeitpunkt: dt.datetime | None = None) -> list[dict]:
        """Wie texte_zum_vorlesen, aber fuers FENSTER: Kopf und Text getrennt.

        Gefragt wurde: "kann er den Inhalt der Nachricht auch als Text
        anzeigen?" Bei Mails ging das schon, bei Meldungen nicht - dieselbe
        Grenze, zwei verschiedene Antworten. Der Weg ist derselbe: an der
        Maschine vorbei, hier nur in ein anderes Fenster statt in die
        Stimme.
        """
        stuecke = []
        for e in self._auswahl(quelle, zeitpunkt):
            teile = [t for t in e["texte"] if t]
            wann = _wie_lange_her(e["zeit"])
            if e["art"] == "person":
                wer, rest = teile[0], teile[1:]
                stuecke.append({
                    "kopf": f"{e['app']} · {wer} ({wann})",
                    "text": "\n".join(rest) if rest else "(kein Text dabei)"})
            else:
                stuecke.append({
                    "kopf": f"{e['app']} · {teile[0]} ({wann})",
                    "text": "\n".join(teile[1:]) or teile[0]})
        return stuecke

    def texte_zum_vorlesen(self, quelle: str = "",
                           zeitpunkt: dt.datetime | None = None) -> list[str]:
        """NUR fuer die Sprachausgabe - das Modell bekommt das nie zu sehen.

        Mit 'zeitpunkt' auch Aelteres: der Briefkasten haelt die letzten 200
        Meldungen, nicht nur die von eben. "Was stand heute frueh in der
        Nachricht von Tom" laesst sich damit beantworten, ohne dass der Text
        durch das Modell geht.
        """
        eintraege = self._auswahl(quelle, zeitpunkt)
        gelesen = []
        for e in eintraege:
            if e["art"] == "werbung":
                continue
            teile = [t for t in e["texte"] if t]
            if not teile:
                continue
            if e["art"] == "person":
                wer, rest = teile[0], teile[1:]
                gelesen.append(f"{wer} schreibt: " + " ".join(rest)
                               if rest else f"{wer} hat geschrieben")
            else:
                gelesen.append(" - ".join(teile[:2]))
        return gelesen

    def leeren(self) -> None:
        with self._schloss:
            self._eintraege.clear()


def _wie_lange_her(wann: dt.datetime) -> str:
    """"vor 20 Minuten", "gestern" - damit Altes nicht als Neues durchgeht.

    Ohne diese Angabe stellte das Modell zwei Tage alte Systemmeldungen als
    heutige dar: es sieht ja nur den Text, nicht den Zeitstempel.
    """
    sekunden = (dt.datetime.now() - wann).total_seconds()
    if sekunden < 90:
        return "gerade eben"
    if sekunden < 3600:
        return f"vor {sekunden / 60:.0f} Minuten"
    if sekunden < 8 * 3600:
        stunden = sekunden / 3600
        return f"vor {stunden:.0f} Stunde" + ("n" if stunden >= 2 else "")
    if wann.date() == dt.date.today():
        return f"heute {wann.strftime('%H:%M')}"
    if (dt.date.today() - wann.date()).days == 1:
        return f"gestern {wann.strftime('%H:%M')}"
    return f"am {wann.strftime('%d.%m. um %H:%M')}"


def _personen_satz(app: str, liste: list[dict]) -> str:
    """"drei Nachrichten von Caitlin und ein Anruf" - ohne ein Wort Inhalt."""
    nachrichten: dict[str, int] = {}
    anrufe: dict[str, int] = {}
    for e in liste:
        wer = (e["titel"] or "jemand").strip()
        ganzer_text = " ".join(e["texte"])
        ziel = anrufe if _ANRUF.search(ganzer_text) else nachrichten
        ziel[wer] = ziel.get(wer, 0) + 1

    teile = []
    for wer, anzahl in nachrichten.items():
        wort = "Nachricht" if anzahl == 1 else "Nachrichten"
        teile.append(f"{_zahlwort(anzahl, weiblich=True)} {wort} von {wer}")
    for wer, anzahl in anrufe.items():
        # "ein Anruf", nicht "eine Anruf" - der Artikel richtet sich nach
        # dem Wort dahinter, nicht nach der Zahl
        wort = "Anruf" if anzahl == 1 else "Anrufe"
        teile.append(f"{_zahlwort(anzahl, weiblich=False)} {wort} von {wer}")

    if len(teile) > 1:
        text = ", ".join(teile[:-1]) + " und " + teile[-1]
    else:
        text = teile[0] if teile else f"etwas in {app}"
    return f"{app}: {text}"


def _zahlwort(n: int, weiblich: bool = True) -> str:
    if n == 1:
        return "eine" if weiblich else "ein"
    return {2: "zwei", 3: "drei", 4: "vier", 5: "fuenf", 6: "sechs",
            7: "sieben", 8: "acht", 9: "neun"}.get(n, str(n))


BRIEFKASTEN = Briefkasten()
