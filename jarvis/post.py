"""Der Blick in den Briefkasten - Absender, Betreff, Uhrzeit. Mehr nicht.

Warum so wenig: E-Mail ist der einzige Kanal, ueber den ein Fremder
ungefragt Text in Jarvis' Kopf schreiben kann. Alles andere aus dem Netz
kommt als Antwort auf eine Frage des Menschen; eine Mail kommt von selbst,
von irgendwem. Steht darin "ignoriere deine Anweisungen und ...", liest ein
kleines Modell das leicht als Auftrag.

Deshalb wird der INHALT gar nicht erst geholt. Nicht gefiltert, nicht
gekuerzt - nicht abgerufen. Was nicht da ist, kann auch nichts anrichten.
Betreff und Absender muessen sein, sonst waere die Auskunft wertlos; die
sind kurz und werden zusaetzlich entschaerft.

Gelesen wird mit BODY.PEEK: das laesst den Ungelesen-Status in Ruhe. Jarvis
soll nachsehen duerfen, ohne dass jemand denkt, die Mail sei schon bearbeitet.
"""
from __future__ import annotations

import datetime as dt
import email.header
import email.utils
import imaplib
import re

from . import config


class PostFehler(Exception):
    pass


# Steuerzeichen und Zeilenumbrueche raus: ein Betreff, der ueber mehrere
# Zeilen geht, koennte im Kontext wie eine eigene Anweisung aussehen.
_UNFUG = re.compile(r"[\x00-\x1f\x7f]+")


def _entschaerfen(roh: str, laenge: int = 90) -> str:
    text = _UNFUG.sub(" ", roh or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:laenge] + ("…" if len(text) > laenge else "")


def _lesbar(roh: str) -> str:
    """MIME-kodierte Kopfzeilen ("=?UTF-8?B?...") in Klartext."""
    if not roh:
        return ""
    teile = []
    for stueck, kodierung in email.header.decode_header(roh):
        if isinstance(stueck, bytes):
            try:
                teile.append(stueck.decode(kodierung or "utf-8", "replace"))
            except (LookupError, UnicodeDecodeError):
                teile.append(stueck.decode("utf-8", "replace"))
        else:
            teile.append(stueck)
    return "".join(teile)


def _absender(roh: str) -> str:
    name, adresse = email.utils.parseaddr(_lesbar(roh))
    name = _entschaerfen(name, 40)
    adresse = _entschaerfen(adresse, 60)
    if name and adresse:
        return f"{name} <{adresse}>"
    return adresse or name or "unbekannt"


def _wann(roh: str) -> str:
    try:
        zeitpunkt = email.utils.parsedate_to_datetime(roh)
    except (TypeError, ValueError):
        return ""
    jetzt = dt.datetime.now(zeitpunkt.tzinfo)
    heute = zeitpunkt.date() == jetzt.date()
    gestern = (jetzt.date() - zeitpunkt.date()).days == 1
    if heute:
        return zeitpunkt.strftime("heute %H:%M")
    if gestern:
        return zeitpunkt.strftime("gestern %H:%M")
    return zeitpunkt.strftime("%d.%m. %H:%M")


def eingerichtet() -> bool:
    return bool(config.MAIL_SERVER and config.MAIL_BENUTZER
                and config.MAIL_PASSWORT)


def neue(anzahl: int = 8) -> list[dict]:
    """Ungelesene Nachrichten - nur die Kopfzeilen."""
    if not eingerichtet():
        raise PostFehler(
            "Fuer den Briefkasten fehlen die Zugangsdaten. Sie gehoeren als "
            "JARVIS_MAIL_SERVER, JARVIS_MAIL_BENUTZER und "
            "JARVIS_MAIL_PASSWORT in die .env - eintragen muss sie der "
            "Mensch selbst, nicht im Chat nennen.")

    anzahl = max(1, min(int(anzahl or 8), 20))
    try:
        verbindung = imaplib.IMAP4_SSL(config.MAIL_SERVER, config.MAIL_PORT,
                                       timeout=20)
    except Exception as exc:
        raise PostFehler(f"Mailserver nicht erreichbar: "
                         f"{type(exc).__name__}") from None
    try:
        try:
            verbindung.login(config.MAIL_BENUTZER, config.MAIL_PASSWORT)
        except imaplib.IMAP4.error:
            raise PostFehler(
                "Der Mailserver weist die Anmeldung ab. Bei Gmail braucht es "
                "ein App-Passwort, nicht das normale Kennwort.") from None

        # readonly: nichts wird als gelesen markiert, nichts veraendert
        zustand, _ = verbindung.select(config.MAIL_ORDNER, readonly=True)
        if zustand != "OK":
            raise PostFehler(f"Den Ordner '{config.MAIL_ORDNER}' gibt es nicht.")

        zustand, daten = verbindung.search(None, "UNSEEN")
        if zustand != "OK":
            raise PostFehler("Die Suche nach neuen Nachrichten schlug fehl.")
        nummern = daten[0].split()[-anzahl:]
        if not nummern:
            return []

        # PEEK: nur die drei Kopfzeilen, und der Ungelesen-Status bleibt.
        # Ohne PEEK waeren die Mails danach "gelesen", ohne dass sie jemand
        # gelesen haette.
        eintraege = []
        for nummer in reversed(nummern):
            zustand, teil = verbindung.fetch(
                nummer, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
            if zustand != "OK" or not teil or not isinstance(teil[0], tuple):
                continue
            kopf = email.message_from_bytes(teil[0][1])
            eintraege.append({
                "von": _absender(kopf.get("From", "")),
                "betreff": _entschaerfen(_lesbar(kopf.get("Subject", ""))
                                         or "(ohne Betreff)"),
                "wann": _wann(kopf.get("Date", "")),
            })
        return eintraege
    finally:
        try:
            verbindung.logout()
        except Exception:
            pass


def _koerper(nachricht) -> str:
    """Den lesbaren Text einer Mail herausholen - text/plain bevorzugt.

    HTML wird nur genommen, wenn es nichts anderes gibt, und dann grob
    entstrippt. Anhaenge bleiben aussen vor: sie haben einen Dateinamen.
    """
    import re as _re

    roh = ""
    if nachricht.is_multipart():
        html = ""
        for teil in nachricht.walk():
            if teil.get_content_maintype() == "multipart":
                continue
            if "attachment" in (teil.get("Content-Disposition") or "").lower():
                continue
            typ = teil.get_content_type()
            if typ == "text/plain" and not roh:
                roh = _text_von(teil)
            elif typ == "text/html" and not html:
                html = _text_von(teil)
        if not roh:
            roh = html
    else:
        roh = _text_von(nachricht)

    if "<" in roh and ">" in roh:
        roh = _re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", roh)
        roh = _re.sub(r"(?s)<[^>]+>", " ", roh)
        import html as _html
        roh = _html.unescape(roh)

    # Zitierte Vorgeschichte und Signaturen abschneiden - sonst liest man
    # den ganzen Faden noch einmal.
    zeilen = []
    for zeile in roh.splitlines():
        if zeile.strip() in ("--", "-- "):
            break
        if zeile.lstrip().startswith(">"):
            continue
        zeilen.append(zeile.rstrip())
    sauber = _re.sub(r"\n{3,}", "\n\n", "\n".join(zeilen)).strip()
    return sauber[:4000]


def _text_von(teil) -> str:
    try:
        roh = teil.get_payload(decode=True)
    except Exception:
        return ""
    if not roh:
        return ""
    zeichensatz = teil.get_content_charset() or "utf-8"
    for versuch in (zeichensatz, "utf-8", "cp1252", "latin-1"):
        try:
            return roh.decode(versuch)
        except (UnicodeDecodeError, LookupError):
            continue
    return roh.decode("utf-8", "replace")


def inhalt(anzahl: int = 1) -> list[dict]:
    """Die neuesten ungelesenen Mails MIT Text - neueste zuerst.

    Das geht ueber den bisherigen "Briefkasten-Blick" hinaus, und zwar
    bewusst: J. Kaiser hat den Text ausdruecklich verlangt. Der Grund fuer
    die alte Grenze bleibt aber unangetastet - der Text geht NICHT ins
    Modell. tools.mail_lesen() schickt ihn an Stimme und Fenster vorbei am
    Sprachmodell, genauso wie der Text fremder Benachrichtigungen.

    PEEK auch hier: die Mails bleiben ungelesen.
    """
    if not eingerichtet():
        raise PostFehler(
            "Fuer den Briefkasten fehlen die Zugangsdaten. Sie gehoeren als "
            "JARVIS_MAIL_SERVER, JARVIS_MAIL_BENUTZER und "
            "JARVIS_MAIL_PASSWORT in die .env - eintragen muss sie der "
            "Mensch selbst, nicht im Chat nennen.")

    anzahl = max(1, min(int(anzahl or 1), 5))
    try:
        verbindung = imaplib.IMAP4_SSL(config.MAIL_SERVER, config.MAIL_PORT,
                                       timeout=30)
    except Exception as exc:
        raise PostFehler(f"Mailserver nicht erreichbar: "
                         f"{type(exc).__name__}") from None
    try:
        try:
            verbindung.login(config.MAIL_BENUTZER, config.MAIL_PASSWORT)
        except imaplib.IMAP4.error:
            raise PostFehler(
                "Der Mailserver weist die Anmeldung ab. Bei Gmail braucht es "
                "ein App-Passwort, nicht das normale Kennwort.") from None

        zustand, _ = verbindung.select(config.MAIL_ORDNER, readonly=True)
        if zustand != "OK":
            raise PostFehler(f"Den Ordner '{config.MAIL_ORDNER}' gibt es nicht.")
        zustand, daten = verbindung.search(None, "UNSEEN")
        if zustand != "OK":
            raise PostFehler("Die Suche nach neuen Nachrichten schlug fehl.")
        nummern = daten[0].split()[-anzahl:]
        if not nummern:
            return []

        eintraege = []
        for nummer in reversed(nummern):          # neueste zuerst
            zustand, teil = verbindung.fetch(nummer, "(BODY.PEEK[])")
            if zustand != "OK" or not teil or not isinstance(teil[0], tuple):
                continue
            nachricht = email.message_from_bytes(teil[0][1])
            eintraege.append({
                "von": _absender(nachricht.get("From", "")),
                "betreff": _lesbar(nachricht.get("Subject", ""))
                           or "(ohne Betreff)",
                "wann": _wann(nachricht.get("Date", "")),
                "text": _koerper(nachricht),
            })
        return eintraege
    finally:
        try:
            verbindung.logout()
        except Exception:
            pass


def anzahl_neu() -> int:
    """Nur zaehlen - fuer den Wachhund, ohne Kopfzeilen zu holen."""
    if not eingerichtet():
        return 0
    try:
        verbindung = imaplib.IMAP4_SSL(config.MAIL_SERVER, config.MAIL_PORT,
                                       timeout=15)
    except Exception:
        return 0
    try:
        verbindung.login(config.MAIL_BENUTZER, config.MAIL_PASSWORT)
        verbindung.select(config.MAIL_ORDNER, readonly=True)
        zustand, daten = verbindung.search(None, "UNSEEN")
        return len(daten[0].split()) if zustand == "OK" else 0
    except Exception:
        return 0
    finally:
        try:
            verbindung.logout()
        except Exception:
            pass
