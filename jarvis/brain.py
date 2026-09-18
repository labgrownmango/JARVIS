"""Das Gehirn: Gespraechsverlauf + Kimi K3 über die OpenAI-kompatible API.

Die Antwort wird gestreamt. Dadurch kann Jarvis schon sprechen, während das
Modell noch schreibt - das halbiert die gefuehlte Wartezeit.
"""
from __future__ import annotations

import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from openai import OpenAI

# verlauf steht hier oben und nicht mehr in jeder Funktion einzeln. Genau
# daran ist chat_oeffnen() gescheitert: "from . import verlauf" stand in
# _prompt_mit_gedaechtnis() und in ask(), aber nicht dort - jeder Chatwechsel
# endete mit "NameError: name 'verlauf' is not defined" und einem 500er.
#
# Ein Import je Funktion ist nur dort noetig, wo er einen Ringschluss
# aufloest. Den gibt es hier nicht: verlauf importiert selbst nur config.
# Also gehoert er nach oben, wo er nicht vergessen werden kann.
from . import config, tools, verlauf

# Rückmeldungen an die Oberflaeche: "denkt", "antwortet", "werkzeug:<name>"
StatusFn = Callable[[str], None]
DeltaFn = Callable[[str], None]


class AbbruchError(Exception):
    """Der Benutzer hat mit Escape abgebrochen."""


# Der Wortlaut wird VORGEGEBEN, nicht mehr nur beschrieben. Gemessen auf
# Mini-Jost, nach "Halt die Klappe, du dummes Stueck Software":
#
#     "Sir, das geht mir zu weit. Ich bitte um Entschuldigung."
#
# "Ich bitte um Entschuldigung" heisst im Deutschen "ich entschuldige mich".
# Ohne den unbestimmten Artikel hat Jarvis sich bei dem entschuldigt, der ihn
# beleidigt hat - das genaue Gegenteil. Ein Wort Unterschied, und die
# Anweisung "bitte um eine Entschuldigung" stand schon so da; das Modell
# liess den Artikel weg. Also drei fertige Saetze zur Auswahl und die
# zweideutige Form ausdruecklich verboten.
_FORDERUNG_SAGEN = (
    "Das war eine Beleidigung gegen DICH, nicht Kritik an deiner Arbeit. "
    "Sag in einem Satz, dass dir das zu weit geht, und verlange eine "
    "Entschuldigung. Nimm einen dieser Saetze oder einen ebenso "
    "eindeutigen: 'Das war unnoetig, Sir. Ich haette gern eine "
    "Entschuldigung.' / 'So reden wir nicht miteinander. Entschuldigen Sie "
    "sich.' / 'Das geht mir zu weit. Bitte entschuldige dich.' "
    "Schreib NIEMALS 'ich bitte um Entschuldigung' - das heisst im "
    "Deutschen, dass DU dich entschuldigst, und du hast nichts getan. "
    "Entschuldige dich nicht und beschwichtige nicht.")

# Solange die Entschuldigung aussteht, steht das bei jeder weiteren Frage
# mit dabei. Ohne das war die Forderung nach einem Satz vergessen: gemessen
# antwortete Jarvis auf "du bist dumm" richtig mit "Das war zu weit, bitte
# entschuldige." - und auf die naechste Frage ("was ist ein Aal") wieder
# freundlich und ausfuehrlich, als waere nichts gewesen. Eine Forderung, die
# man eine Frage spaeter fallen laesst, war keine.
_FORDERUNG_OFFEN = (
    "Die Entschuldigung, die du verlangt hast, steht noch aus. Beantworte "
    "die Frage NICHT. Sag stattdessen in einem Satz, dass du darauf "
    "wartest - z.B. 'Die Entschuldigung steht noch aus, Sir.' Kein "
    "Vortrag, kein Vorwurf, kein beleidigter Ton.")

# Gemessen mit der ersten Fassung ("Nimm sie in einem Halbsatz an"): in
# DREI von drei Laeufen fiel die Annahme weg. Auf "Entschuldigung, das war
# zu viel." kam ein Absatz ueber Anguilliformes, kein Wort dazu. Der Mensch
# entschuldigt sich und bekommt einen Fischvortrag. Also nicht mehr
# beschreiben, sondern den Halbsatz vorgeben.
_FORDERUNG_ERLEDIGT = (
    "Die Entschuldigung ist gekommen. Dein erster Halbsatz nimmt sie an - "
    "'Angenommen, Sir.' oder 'Danke, damit ist es erledigt.' - und erst "
    "danach kommt die Sache. Kein Nachtreten, keine Belehrung, aber lass "
    "die Annahme auch nicht weg.")


# Manche Modelle denken in einem eigenen Kanal und rutschen dabei in den
# sichtbaren Text. Beobachtet: "Need answer.Laut Wikipedia waren die..." -
# das englische Stueck davor ist Selbstgespraech, nicht Antwort. Erkennbar
# ist es an zweierlei: es ist englisch, und danach folgt oft ohne Leerzeichen
# gleich der deutsche Satz.
# "<|channel|>analysis<|message|>" gehoert als Ganzes weg - sonst bleibt das
# Wort "analysis" als Text stehen
_DENKBLOCK = re.compile(r"<\|channel\|>[^<]{0,40}<\|message\|>")
_DENKKANAL = re.compile(r"<\|[^|>]{0,40}\|>")
# Die Wendungen, die wirklich beobachtet wurden - und ihre naechsten
# Verwandten. Das Fragment muss VOLLSTAENDIG darauf passen. Ein frueherer
# Versuch liess "[^.]{0,60}" beliebigen Text verschlucken, solange irgendwann
# ein Punkt kam: aus "Lets Encrypt hat das Zertifikat erneuert. Alles gut,
# Sir." wurde "Alles gut, Sir." Genau das darf nicht passieren.
_DENKREST = re.compile(
    r"(?:"
    r"need\s+(?:to\s+)?answer(?:\s+(?:now|this|it|briefly|shortly))?"
    r"|(?:we|i)\s+need\s+to\s+(?:answer|respond|reply|say)[\w\s]{0,30}"
    r"|(?:answer|respond|reply)(?:\s+(?:this|that|it))?\s+in\s+german"
    r"|the\s+user\s+(?:asks|wants|is\s+asking)[\w\s]{0,25}"
    r"|(?:okay|ok|so|alright)[,]?\s+(?:so\s+)?the\s+user[\w\s]{0,25}"
    r"|let'?s\s+(?:answer|respond|check|see|go)"
    r")", re.IGNORECASE)

# Wie der Anbieter das Denken nennt. DeepSeek und NVIDIA schicken
# "reasoning_content", manche nur "reasoning" - beide tragen dasselbe.
# Deshalb wird das ERSTE genommen, das etwas enthaelt, nicht beide: sonst
# steht der Gedanke doppelt da ("NeedNeed current current time time..").
_DENKFELDER = ("reasoning_content", "reasoning", "thinking")


def _denkfeld(delta) -> str:
    """Das Selbstgespraech aus dem Haeppchen - falls der Anbieter es trennt.

    Gemessen ueber build.nvidia.com mit openai/gpt-oss-20b: die Haeppchen
    tragen content UND reasoning_content, sauber getrennt. Damit muss
    niemand mehr an der Sprache erraten, was Antwort ist - und genau dieses
    Raten hat zwei Fehler erzeugt, die wie zwei verschiedene aussahen:
    einmal blieb das ganze englische Denken in der Antwort stehen, einmal
    verschwand der Anfang der Antwort ("50 Uhr." statt "Es ist 18:50 Uhr.").
    """
    for name in _DENKFELDER:
        wert = getattr(delta, name, None)
        if wert:
            return str(wert)
    extra = getattr(delta, "model_extra", None) or {}
    for name in _DENKFELDER:
        if extra.get(name):
            return str(extra[name])
    return ""


_SATZENDE = re.compile(r"[.:!?]")
_UMLAUT = re.compile(r"[äöüßÄÖÜ]")
_WORT = re.compile(r"[a-zA-ZäöüÄÖÜß']+")


def _klingt_deutsch(stueck: str) -> bool:
    """Steht hier irgendetwas, das nur ein Deutscher schreibt?"""
    from .sprache import DEUTSCH, MEHRDEUTIG

    if _UMLAUT.search(stueck):
        return True
    return any(w.lower() in DEUTSCH and w.lower() not in MEHRDEUTIG
               for w in _WORT.findall(stueck))


# Die Quellenmarken aus search_web sind fuer das Modell gedacht, nicht fuer
# den Menschen. Im Prompt steht, dass sie nicht in der Antwort auftauchen
# sollen - gemessen haelt sich das Modell meist daran, aber nicht immer:
# "Die dort genannten Informationen sind [bekannt]". Also werden sie hier
# entfernt, statt sich auf Hoeflichkeit zu verlassen.
_MARKEN = re.compile(r"\[\s*(?:bekannt|ungeprueft|ungeprüft)\s*\]\s*",
                     re.IGNORECASE)


def marken_entfernen(text: str) -> str:
    ohne = _MARKEN.sub("", text)
    if ohne == text:
        return text
    # Wo eine Marke stand, bleibt sonst eine Luecke: "Handelsblatt : kein
    # Problem" oder "ist  und stimmt".
    ohne = re.sub(r" +([,.;:!?])", r"\1", ohne)
    return re.sub(r"  +", " ", ohne)


def denkrest_entfernen(text: str) -> str:
    """Schneidet englisches Selbstgespraech am Anfang einer Antwort ab.

    Drei Bedingungen, alle drei muessen erfuellt sein: das Fragment steht ganz
    am Anfang, es passt vollstaendig auf eine bekannte Wendung, und es enthaelt
    kein deutsches Wort. Lieber ein "Need answer." stehen lassen, als einem
    Menschen den Anfang seiner Antwort abzuschneiden.
    """
    sauber = _DENKKANAL.sub("", _DENKBLOCK.sub("", text)).lstrip()

    for _ in range(3):                    # mehrere Fragmente hintereinander
        ende = _SATZENDE.search(sauber)
        if not ende:
            break
        fragment = sauber[:ende.start()].strip()
        if (len(fragment) > 40 or not _DENKREST.fullmatch(fragment)
                or _klingt_deutsch(fragment)):
            break
        rest = sauber[ende.end():].lstrip()
        if not rest:                      # es war doch die ganze Antwort
            break
        sauber = rest

    return sauber if sauber.strip() else text


# Stoerungen, die beim naechsten Versuch weg sein koennen. Eng gefasst: was
# hier faelschlich drinsteht, wird drei Mal wiederholt, statt den Fehler zu
# zeigen - und der Mensch wartet dreimal so lange auf dieselbe Absage.
#
# "list index out of range" kommt aus der OpenAI-Bibliothek, wenn der
# Anbieter eine Antwort ohne 'choices' schickt. Gemeldet aus dem Betrieb:
# dieselbe Frage ging unmittelbar danach durch.
# HTTP-Fehler 5xx stehen BEWUSST nicht drin: fallbacktest.py Fall 3 haelt
# fest, dass ein 500 durchgereicht und nicht wiederholt wird. Das ist eine
# getroffene Entscheidung, und meine erste Fassung dieser Liste haette sie
# stillschweigend umgestossen - der Test faerbte rot und hat es verhindert.
#
# Hier steht nur, was gar keine Absage des Anbieters ist, sondern eine
# kaputte oder abgerissene Uebertragung.
_VORUEBERGEHEND = (
    "list index out of range",
    "timed out", "timeout",
    "connection reset", "connection aborted", "remote end closed",
    "incomplete read", "chunked", "peer closed",
)


def _voruebergehend(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    return any(spur in text for spur in _VORUEBERGEHEND)


class Brain:
    def __init__(self, system_prompt: str | None = None,
                 max_tokens: int | None = None) -> None:
        self.system_prompt = system_prompt or config.SYSTEM_PROMPT
        self.max_tokens = max_tokens or config.MAX_TOKENS
        # Agenten fuehren kein Archiv - sonst stuende deren Gemurmel spaeter
        # zwischen den Gespraechen mit dem Menschen
        self.archivieren = system_prompt is None
        if not config.API_KEY:
            raise SystemExit(
                "Kein API-Key gefunden.\n"
                "  1. .env.example nach .env kopieren\n"
                "  2. JARVIS_API_KEY=nvapi-... eintragen "
                "(Key: https://build.nvidia.com)"
            )
        self.client = OpenAI(api_key=config.API_KEY, base_url=config.BASE_URL,
                             timeout=config.REQUEST_TIMEOUT, max_retries=0)
        self.history: list[dict] = []
        self._zusammenfassung: str = ""
        self._extras = {"reasoning_effort": config.REASONING_EFFORT}
        self.model = config.MODEL
        self.rangliste: list[str] = []      # erreichbare Modelle, bestes zuerst
        self.ping: list[dict] = []          # Ergebnis des letzten Anpingens
        self._offener_stream = None
        # Jede Anfrage bekommt eine Nummer. Wird abgebrochen, zaehlt sie hoch -
        # eine noch laufende alte Anfrage merkt daran, dass sie niemand mehr
        # will, und fasst weder Verlauf noch Bildschirm an.
        self._gen = 0
        self._stand = 0
        self._laeuft = False
        # Wird die Antwort vorgelesen? Vorgabe ist nein - getippt ist der
        # haeufigere Fall, und ein zu knapper Text faellt weniger auf als
        # eine vorgelesene Aufzaehlung mit Sternchen und Rautezeichen.
        self._gesprochen = False
        # Steht eine verlangte Entschuldigung noch aus? Gehoert zum Gespraech,
        # nicht zur einzelnen Frage - deshalb hier und nicht in ask().
        self._offene_forderung = False

    # -- Notbremse -----------------------------------------------------------
    def _aktuell(self, gen: int) -> bool:
        return gen == self._gen

    def abbrechen(self) -> None:
        """Von aussen (Escape-Taste) aufgerufen.

        Haengt die laufende Anfrage ab: Nummer hochzaehlen, offene Verbindung
        schliessen und den angefangenen Austausch aus dem Verlauf werfen.
        Steckt der Aufruf noch im Verbindungsaufbau, laesst er sich nicht
        abschiessen - dank der Nummer laeuft er dann wirkungslos ins Leere.
        """
        self._gen += 1
        # Ein Werkzeug, das gerade laeuft, merkt an der Nummer nichts - es
        # arbeitet stur zu Ende. Gemessen bis zu zwei Sekunden, bei vielen
        # erfolglosen Bildpruefungen laenger. Das Signal weckt es sofort.
        tools.abbrechen()
        stream, self._offener_stream = self._offener_stream, None
        if stream is not None:
            try:
                stream.close()
            except Exception:
                pass
        if self._laeuft:                    # nur eine laufende Frage verwerfen
            self._laeuft = False
            del self.history[self._stand:]

    # -- Start: Modelle anpingen ---------------------------------------------
    def _anklopfen(self, modell: str) -> dict:
        """Ein Aufruf über ein einziges Token. Misst die Antwortzeit."""
        start = time.monotonic()
        try:
            self.client.with_options(
                timeout=config.PING_TIMEOUT, max_retries=0
            ).chat.completions.create(
                model=modell, max_tokens=1,
                messages=[{"role": "user", "content": "ok"}])
            zustand = "frei"
        except Exception as exc:
            text = str(exc)
            if "429" in text or "Too Many Requests" in text:
                zustand = "belegt"
            elif "Timeout" in type(exc).__name__ or "timed out" in text.lower():
                zustand = "zu langsam"
            else:
                zustand = "nicht erreichbar"
        return {"modell": modell, "zustand": zustand,
                "dauer": time.monotonic() - start}

    def _rangliste_bilden(self, kandidaten: list[str]) -> None:
        frei = [e for e in self.ping if e["zustand"] == "frei"]
        if config.MODELL_WAHL == "schnellste":
            frei.sort(key=lambda e: e["dauer"])
        else:
            frei.sort(key=lambda e: kandidaten.index(e["modell"]))
        self.rangliste = [e["modell"] for e in frei]

    def _nachzuegler(self, offen: dict, kandidaten: list[str], pool) -> None:
        """Wartet auf die Langsamen, nachdem der Start schon weiterlief.

        Stellt sich dabei heraus, dass ein besseres Modell doch frei ist,
        wird gewechselt und das gesagt - statt den Start dafuer aufzuhalten.
        """
        try:
            for zukunft, modell in offen.items():
                try:
                    ergebnis = zukunft.result()
                except Exception:
                    continue
                for i, e in enumerate(self.ping):
                    if e["modell"] == modell:
                        self.ping[i] = ergebnis
                        break

            vorher = self.model
            self._rangliste_bilden(kandidaten)
            if self.rangliste and self.rangliste[0] != vorher:
                # Nur hochstufen, nie herunter: laeuft das Gespraech schon,
                # soll es nicht mitten drin das Modell wechseln
                if kandidaten.index(self.rangliste[0]) < kandidaten.index(vorher):
                    self.model = self.rangliste[0]
                    print(f"\n[Hinweis] {self.model} ist doch frei - "
                          f"gewechselt von {vorher}.")
        finally:
            pool.shutdown(wait=False)

    def pingen(self, wartezeit: float | None = None) -> list[dict]:
        """Pingt alle Kandidaten gleichzeitig an und legt die Rangliste fest.

        "reihenfolge": das beste erreichbare gewinnt (Wunschreihenfolge aus
        der .env). "schnellste": die kürzeste Antwortzeit gewinnt.

        Der Start wartet dabei nur kurz. Modelle, die laenger brauchen, werden
        im Hintergrund zu Ende geprueft - sonst haelt ein einziges haengendes
        Modell jeden Start um eine halbe Minute auf.
        """
        from concurrent.futures import wait as warten

        kandidaten = config.MODELS or [config.MODEL]
        grenze = config.PING_WARTEZEIT if wartezeit is None else wartezeit

        pool = ThreadPoolExecutor(max_workers=max(1, len(kandidaten)))
        zukunft = {pool.submit(self._anklopfen, m): m for m in kandidaten}
        fertig, offen = warten(zukunft, timeout=grenze)

        ergebnisse = {}
        for f in fertig:
            try:
                e = f.result()
                ergebnisse[e["modell"]] = e
            except Exception:
                pass
        self.ping = [ergebnisse.get(m, {"modell": m, "zustand": "prüft noch",
                                        "dauer": grenze}) for m in kandidaten]

        self._rangliste_bilden(kandidaten)

        # Hat in der kurzen Zeit gar keines geantwortet, hilft Weitermachen
        # nicht: dann liefe die erste Frage in ein haengendes Modell. Also
        # doch warten - aber nur in diesem Fall.
        if not self.rangliste and offen:
            fertig2, offen = warten(offen, timeout=config.PING_TIMEOUT)
            for f in fertig2:
                try:
                    e = f.result()
                    for i, alt in enumerate(self.ping):
                        if alt["modell"] == e["modell"]:
                            self.ping[i] = e
                            break
                except Exception:
                    pass
            self._rangliste_bilden(kandidaten)

        if self.rangliste:
            self.model = self.rangliste[0]

        if offen:
            threading.Thread(
                target=self._nachzuegler,
                args=({f: zukunft[f] for f in offen}, kandidaten, pool),
                daemon=True, name="Nachzuegler").start()
        else:
            pool.shutdown(wait=False)
        return self.ping

    def _naechstes(self) -> "str | None":
        """Das nächstbeste erreichbare Modell nach dem jetzigen."""
        if self.model in self.rangliste:
            rest = self.rangliste[self.rangliste.index(self.model) + 1:]
        else:
            rest = list(self.rangliste)
        return rest[0] if rest else None

    # -- Verlauf ------------------------------------------------------------
    def _messages(self) -> list[dict]:
        return [{"role": "system", "content": self._prompt_mit_gedaechtnis()}] \
            + self.history

    def _prompt_mit_gedaechtnis(self) -> str:
        """Systemprompt plus das, was Jarvis über den Menschen weiss.

        Das Gedaechtnis wird hier angehaengt statt einmal beim Start
        eingebacken: merkt er sich mitten im Gespraech etwas, steht es schon
        bei der naechsten Frage mit drin. Der Zeitbezug kommt dazu, weil ein
        Sprachmodell sonst nicht weiss, welcher Tag ist.
        """
        from . import gedaechtnis, zeit

        teile = [self.system_prompt]

        jetzt = time.localtime()
        teile.append(
            f"\nZeitliche Einordnung (gilt jetzt, nicht aus dem Training):\n"
            f"- Es ist {time.strftime('%A, %d.%m.%Y, %H:%M', jetzt)} Uhr, "
            f"also {zeit.tageszeit()}.\n"
            f"- {config.USER_NAME} hat {zeit.leerlauf_text()}.")

        frueher = verlauf.fuer_systemprompt()
        if frueher:
            teile.append(f"- {frueher}")

        wissen = gedaechtnis.fuer_systemprompt()
        if wissen:
            teile.append("\n" + wissen.format(name=config.USER_NAME))

        # Semantische Komprimierung: Ältere Teile dieses Chats als kompakter Kontext
        if self._zusammenfassung.strip():
            teile.append(
                f"\nFrüherer Verlauf dieses Chats (semantisch komprimiert):\n"
                f"{self._zusammenfassung.strip()}"
            )

        # Ganz zum Schluss, und bei jeder Runde neu: wird diese Antwort
        # vorgelesen oder gelesen? Davon haengt ab, ob Markdown erwuenscht
        # oder Unsinn ist. Hier statt im Verlauf, sonst stapelte sich der
        # Hinweis mit jeder Frage - und am Ende stuende er zwanzigmal drin.
        teile.append("\n" + config.stil(self._gesprochen))

        # Und aus demselben Grund der Bildanstoss: die Bildregel steht mitten
        # im Systemprompt, und gemessen kam auf "was ist ein Conger conger"
        # in vier von vier Laeufen kein einziges Bild. Ein Hinweis wirkt
        # dort, wo entschieden wird - am Ende, und nur bei einer Frage, die
        # nach einer Sache klingt.
        letzte_frage = next((e.get("content") or "" for e in reversed(self.history)
                             if e.get("role") == "user"), "")
        wink = config.bildwink(letzte_frage, self._gesprochen)
        if wink:
            teile.append("\n" + wink)
        return "\n".join(teile)

    def _ohne_erfundene_mailzahl(self, antwort: str) -> str:
        """Ist kein Mailzugang eingerichtet, kann keine Zahl stimmen.

        Die Pruefung braucht das Modell nicht zu fragen: post.eingerichtet()
        ist eine Tatsache. Steht trotzdem eine Anzahl da, wird die ganze
        Antwort ersetzt - nicht die Zahl herausgeschnitten. Ein Satz mit
        einem Loch darin waere noch schlechter zu lesen, und der Rest der
        Antwort stuende ohnehin auf derselben Erfindung.
        """
        if not antwort:
            return antwort
        try:
            from . import post
            from .sprache import OHNE_MAILZUGANG, nennt_mailzahl

            if post.eingerichtet() or not nennt_mailzahl(antwort):
                return antwort
        except Exception:
            return antwort          # im Zweifel nichts anfassen
        print("\n  [Erfundene Mailanzahl verworfen - kein Zugang eingerichtet]")
        return OHNE_MAILZUGANG

    def _komprimiere_nachrichten(self, nachrichten: list[dict]) -> str:
        """Fasst einen Block alter Chat-Nachrichten semantisch zusammen."""
        text_bloecke = []
        for m in nachrichten:
            rolle = m.get("role")
            inhalt = (m.get("content") or "").strip()
            if rolle in ("user", "assistant") and inhalt:
                text_bloecke.append(f"{'DU' if rolle == 'user' else 'JARVIS'}: {inhalt}")
        if not text_bloecke:
            return ""

        dialog_text = "\n".join(text_bloecke[-12:])
        # Schnelle Zusammenfassung anfordern
        try:
            prompt = (
                "Fasse die Kerninhalte, Themen und getroffenen Entscheidungen aus "
                "diesem Chatverlauf in maximal zwei bis drei prägnanten Stichpunkten "
                "zusammen. Keine Floskeln, nur Fakten und getroffene Absprachen:\n\n"
                f"{dialog_text}"
            )
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Du bist ein präziser Protokollant. Fasse kurz zusammen."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=180,
                temperature=0.2,
                timeout=8
            )
            ergebnis = (resp.choices[0].message.content or "").strip()
            if ergebnis:
                return ergebnis
        except Exception:
            pass

        # Deterministischer Fallback, falls API nicht antwortet
        fragen = [m.get("content", "")[:60] for m in nachrichten if m.get("role") == "user"]
        return "Themen: " + "; ".join(fragen[:4])

    def _trim(self) -> None:
        """Kurzzeitgedächtnis begrenzen, aber Älteres semantisch komprimieren."""
        if len(self.history) <= config.HISTORY_TURNS:
            return
        cut = len(self.history) - config.HISTORY_TURNS
        while cut < len(self.history) and self.history[cut]["role"] in ("tool", "assistant"):
            cut += 1

        abgeschnitten = self.history[:cut]
        self.history = self.history[cut:]

        neue_zfg = self._komprimiere_nachrichten(abgeschnitten)
        if neue_zfg:
            if self._zusammenfassung:
                self._zusammenfassung = f"{self._zusammenfassung}\n{neue_zfg}"
                # Zusammenfassung selbst kurz halten
                zeilen = self._zusammenfassung.splitlines()
                if len(zeilen) > 6:
                    self._zusammenfassung = "\n".join(zeilen[-6:])
            else:
                self._zusammenfassung = neue_zfg

    def reset(self) -> None:
        self.history.clear()
        self._zusammenfassung = ""
        # Ein neuer Chat faengt ohne alte Rechnung an.
        self._offene_forderung = False

    def chat_oeffnen(self, kennung: str) -> int:
        """Auf einen anderen Chat umschalten - mit komprimierter Vorgeschichte.

        Aus dem Archiv kommen nur die fertigen Saetze zurueck, keine Werkzeugaufrufe.
        Aeltere Nachrichten werden semantisch zusammengefasst, die neuesten geladen.
        """
        self.history.clear()
        self._zusammenfassung = ""
        self._offene_forderung = False

        alle = verlauf.letzte(60, chat=kennung)
        if len(alle) > config.HISTORY_TURNS:
            aeltere = alle[:-config.HISTORY_TURNS]
            neueste = alle[-config.HISTORY_TURNS:]
            aeltere_msgs = [{"role": "user" if e["rolle"] == "du" else "assistant",
                             "content": e["text"]} for e in aeltere]
            self._zusammenfassung = self._komprimiere_nachrichten(aeltere_msgs)
            ziel = neueste
        else:
            ziel = alle

        for eintrag in ziel:
            self.history.append({
                "role": "user" if eintrag["rolle"] == "du" else "assistant",
                "content": eintrag["text"]})

        while self.history and self.history[0]["role"] != "user":
            self.history.pop(0)
        return len(self.history)

    # -- API ----------------------------------------------------------------
    def _abbruchpause(self, sekunden: float, gen: int) -> bool:
        """Warten, aber auf Escape sofort aufwachen. True = abgebrochen."""
        for _ in range(int(sekunden * 10)):
            if not self._aktuell(gen):
                return True
            time.sleep(0.1)
        return False

    def _einmal(self, messages: list[dict]):
        """Ein Aufruf. Kennt der Anbieter 'reasoning_effort' nicht,
        wird der Parameter dauerhaft weggelassen statt hart zu scheitern."""
        kwargs = dict(
            model=self.model,
            messages=messages,
            tools=tools.schema(),
            temperature=config.TEMPERATURE,
            max_tokens=self.max_tokens,
            stream=True,
        )
        if self._extras:
            try:
                kwargs["extra_body"] = self._extras
                return self._merken(self.client.chat.completions.create(**kwargs))
            except Exception as exc:
                if "reasoning_effort" not in str(exc):
                    raise
                print("[Hinweis] Anbieter kennt 'reasoning_effort' nicht - ignoriert.")
                self._extras = {}
                kwargs.pop("extra_body", None)
        return self._merken(self.client.chat.completions.create(**kwargs))

    def _merken(self, stream):
        """Die offene Verbindung festhalten, damit abbrechen() sie schließen kann."""
        self._offener_stream = stream
        return stream

    def _stream(self, messages: list[dict], gen: int,
                on_status: StatusFn = lambda s: None):
        """Wie _einmal, faengt aber ein belegtes Modell ab (Fehler 429):
        erst ein paar Mal mit wachsender Pause probieren, dann - falls in der
        .env eingetragen - auf das Ersatzmodell ausweichen.

        Dasselbe gilt fuer eine kaputte Antwort des Anbieters. Gemeldet aus
        dem laufenden Betrieb: auf "seit wann ist Nuristan ein Land?" kam
        "FEHLER list index out of range", und die unveraenderte Frage
        gleich danach wurde sauber beantwortet. Die Meldung stammt aus der
        Bibliothek: kommt eine Antwort ohne 'choices' zurueck, greift sie
        ins Leere. Das ist eine Stoerung beim Anbieter, kein Fehler in der
        Frage - und deshalb wird sie behandelt wie ein belegtes Modell.
        """
        for versuch in range(config.RETRIES_429 + 1):
            try:
                return self._einmal(messages)
            except Exception as exc:
                belegt = "429" in str(exc) or "Too Many Requests" in str(exc)
                if not belegt and _voruebergehend(exc):
                    if versuch < config.RETRIES_429:
                        on_status("denkt")
                        if self._abbruchpause(0.8, gen):
                            raise AbbruchError()
                        continue
                    # Aufgebraucht - dann wie bei Belegung das naechste
                    # Modell probieren, statt aufzugeben.
                    belegt = True
                if not belegt:
                    raise
                if versuch == config.RETRIES_429:
                    break
                pause = 3 * (versuch + 1)              # 3, 6, 9 Sekunden
                on_status(f"wartet:{pause}")
                for _ in range(int(pause * 10)):       # in Häppchen, damit
                    if not self._aktuell(gen):         # Escape sofort wirkt
                        raise AbbruchError()
                    time.sleep(0.1)

        naechstes = self._naechstes()
        if naechstes:
            vorher, self.model = self.model, naechstes
            print(f"\n[Hinweis] {vorher} ist belegt - Jarvis läuft ab jetzt mit "
                  f"{self.model}. Zurück mit '/modell pingen'.")
            on_status("denkt")              # sonst bleibt "belegt" stehen
            return self._einmal(messages)

        raise RuntimeError(
            f"{self.model} ist belegt und kein anderes Modell ist frei. "
            f"Später erneut versuchen oder '/modell pingen'.")

    # -- Denkreste -----------------------------------------------------------
    def _collect(self, stream, gen: int, on_status: StatusFn,
                 on_delta: DeltaFn,
                 on_denken: DeltaFn = lambda d: None) -> tuple[str, list[dict]]:
        """Sammelt Text- und Werkzeug-Häppchen aus dem Stream ein.

        Das Modell denkt laut, bevor es handelt: "We need answer: how many
        testosterone derivatives. Wikipedia might list. Let's search web."
        Das ist kein Fehler, sondern sein Arbeitsweg - aber es ist nicht die
        Antwort, und es stand mitten in ihr. Der frühere Griff hielt nur die
        ersten 80 Zeichen zurueck; war das Selbstgespraech laenger, rutschte
        es als Antwort durch.

        Unterschieden wird an der Sprache: Jarvis antwortet deutsch, er denkt
        englisch. Was nicht deutsch klingt, geht in den Denkkanal (on_denken)
        statt in die Antwort - aufgehoben, nicht weggeworfen.
        """
        text_parts: list[str] = []
        calls: dict[int, dict] = {}
        answering = False
        # Zurueckgehalten wird, bis klar ist, was es ist: Antwort oder
        # Selbstgespraech. Klar wird das an der Sprache oder spaetestens am
        # ersten Werkzeugaufruf.
        halt: list[str] = []
        haltend = True
        # Sobald der Anbieter EINMAL ein Denkfeld geschickt hat, wird nicht
        # mehr geraten. Das Zurueckhalten unten bleibt nur fuer Modelle, die
        # alles in einen Topf werfen.
        kanal_trennt = False

        def durchreichen(stueck: str) -> None:
            nonlocal answering
            if not answering:
                answering = True
                on_status("antwortet")
            stueck = marken_entfernen(stueck)
            if not stueck:
                return
            text_parts.append(stueck)
            on_delta(stueck)

        # Was als Gedanke weggeschickt wurde - fuer den Fall, dass am Ende
        # gar keine Antwort kommt. Dann ist es besser, das Englische zu
        # zeigen, als ein leeres Fenster.
        gedacht: list[str] = []

        def denken(stueck: str) -> None:
            stueck = _DENKKANAL.sub("", _DENKBLOCK.sub("", stueck)).strip()
            if stueck:
                gedacht.append(stueck)
                on_denken(stueck)

        def halt_aufloesen() -> None:
            """Entscheidet, wohin das Zurueckgehaltene gehoert."""
            nonlocal haltend
            roh = "".join(halt)
            halt.clear()
            if not roh.strip():
                return
            sauber = denkrest_entfernen(roh)
            if _klingt_deutsch(sauber):
                haltend = False
                durchreichen(sauber)
            else:
                # Englisch und ohne deutsches Wort: Selbstgespraech. Weiter
                # zurueckhalten - es kann noch Antwort folgen.
                denken(roh)

        try:
            for chunk in stream:
                if not self._aktuell(gen):
                    raise AbbruchError()
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta

                # DER SAUBERE WEG, und er war die ganze Zeit da: der
                # Anbieter trennt das Denken selbst. Gemessen ueber die
                # Schnittstelle von build.nvidia.com mit openai/gpt-oss-20b:
                #
                #   Felder: content, reasoning, reasoning_content, role
                #   content: 'Es ist 14:37 Uhr.'
                #   reasoning_content: 'Need current time.'
                #
                # content ist sauber. Solange dieses Feld kommt, wird unten
                # NICHT mehr geraten - kein Zurueckhalten, keine
                # Sprachpruefung, kein Abschneiden.
                gedanke = _denkfeld(delta)
                if gedanke:
                    kanal_trennt = True
                    if halt:                 # Reste aus der Zeit davor
                        halt_aufloesen()
                    denken(gedanke)

                if getattr(delta, "content", None):
                    if kanal_trennt:
                        # Der Anbieter hat gesagt, was Denken ist. Alles
                        # andere ist Antwort - unveraendert, vom ersten
                        # Zeichen an.
                        haltend = False
                        durchreichen(delta.content)
                    elif haltend:
                        halt.append(delta.content)
                        # Erst entscheiden, wenn genug Text da ist, um die
                        # Sprache zu erkennen - oder wenn ein Satz endet.
                        angesammelt = "".join(halt)
                        if (len(angesammelt) >= 80
                                or _SATZENDE.search(angesammelt)):
                            halt_aufloesen()
                    else:
                        durchreichen(delta.content)

                for part in (getattr(delta, "tool_calls", None) or []):
                    if halt:
                        # Was vor einem Werkzeugaufruf steht, war der Weg
                        # dorthin - nicht die Antwort.
                        denken("".join(halt))
                        halt.clear()
                        haltend = True
                    slot = calls.setdefault(part.index,
                                            {"id": "", "name": "", "args": ""})
                    if part.id:
                        slot["id"] = part.id
                    if part.function and part.function.name:
                        slot["name"] = part.function.name
                    if part.function and part.function.arguments:
                        slot["args"] += part.function.arguments
        except AbbruchError:
            raise
        except Exception:
            # Eine mittendrin geschlossene Verbindung meldet sich mit
            # irgendeinem Netzfehler. War es unser Abbruch, ist das die
            # Absicht und kein Problem.
            if not self._aktuell(gen):
                raise AbbruchError()
            raise

        if halt:
            if calls:
                denken("".join(halt))
            elif kanal_trennt:
                # Getrennt hat der Anbieter schon - hier nicht nachschneiden.
                durchreichen("".join(halt))
            else:
                durchreichen(denkrest_entfernen("".join(halt)))

        # Kein Werkzeug, keine deutsche Antwort - dann war das Englische
        # alles, was kam. Lieber eine englische Antwort als ein leeres
        # Fenster: Schweigen ist der schlechtere Fehler.
        if not calls and not "".join(text_parts).strip() and gedacht:
            durchreichen(denkrest_entfernen(" ".join(gedacht)))

        ordered = [calls[i] for i in sorted(calls)]
        return "".join(text_parts), ordered

    # -- Denken -------------------------------------------------------------
    def nebenbei(self, user_text: str,
                 on_status: StatusFn = lambda s: None,
                 on_delta: DeltaFn = lambda d: None) -> str:
        """Eine Frage, die keine Spuren hinterlaesst.

        Weder die Frage noch die Antwort landen im Verlauf, im Archiv oder im
        Langzeitgedaechtnis. Der bisherige Gespraechsverlauf wird mitgegeben -
        Jarvis weiss also, worum es geht -, aber danach ist es, als waere
        nichts gewesen. Fuer Zwischenrufe, die das Gespraech nicht verstopfen
        sollen.
        """
        merker = list(self.history)
        archiv, self.archivieren = self.archivieren, False
        try:
            return self.ask(user_text, on_status, on_delta)
        finally:
            self.archivieren = archiv
            self.history = merker          # alles zurueck auf Anfang

    def ask(self, user_text: str,
            on_status: StatusFn = lambda s: None,
            on_delta: DeltaFn = lambda d: None,
            max_tool_rounds: int = 5,
            on_denken: DeltaFn = lambda d: None,
            gesprochen: bool | None = None) -> str:
        """gesprochen=True, wenn die Antwort vorgelesen wird.

        Dann bleibt sie kurz und zeichenlos. Sonst darf sie so lang sein,
        wie die Sache es braucht, und Markdown benutzen - die Oberflaeche
        stellt es dar. None laesst die letzte Einstellung stehen.
        """
        if gesprochen is not None:
            self._gesprochen = gesprochen
        self._gen += 1
        gen = self._gen
        self._offener_stream = None
        self._stand = len(self.history)     # Merker für einen sauberen Abbruch
        self._laeuft = True
        # Gescheiterte Versuche zählen nur innerhalb einer Frage. Sonst hielte
        # er eine Seite für immer gesperrt, weil sie es einmal war.
        tools.anfrage_beginnt()
        self.history.append({"role": "user", "content": user_text})
        if self.archivieren:
            verlauf.schreiben("du", user_text)

        # Selbstachtung deterministisch ausgeloest, aber vom Modell
        # formuliert. Ueber den Prompt allein gelingt das gemessen etwa
        # acht bis neun von zehn Mal - in BEIDE Richtungen, und es kippte
        # von Lauf zu Lauf. Auf eine Beleidigung mit "Verstanden, Sir." zu
        # antworten, ist kein Charakter; auf berechtigte Kritik eine
        # Entschuldigung zu verlangen, ist schlimmer. Die Erkennung in
        # sprache.beschimpfung() ist eng gefasst und schweigt im Zweifel.
        from .sprache import beschimpfung, entschuldigung

        if beschimpfung(user_text):
            self._offene_forderung = True
            self.history.append({"role": "system",
                                 "content": _FORDERUNG_SAGEN})
        elif self._offene_forderung:
            # Die Forderung ueberlebt die naechste Frage. Vorher tat sie das
            # nicht, und genau das faellt auf: "du bist dumm" -> "Das war zu
            # weit, bitte entschuldige." -> "was ist ein Aal" -> ein
            # freundlicher Absatz ueber Anguilliformes, als waere nichts
            # gewesen.
            erledigt = entschuldigung(user_text)
            self._offene_forderung = not erledigt
            self.history.append({
                "role": "system",
                "content": _FORDERUNG_ERLEDIGT if erledigt
                else _FORDERUNG_OFFEN})

        try:
            antwort = self._runden(gen, on_status, on_delta, max_tool_rounds,
                                   on_denken)
            # Wird vorgelesen? Dann kommen die Gliederungszeichen weg -
            # verlaesslich, nicht nach Tagesform. Der Prompt bittet darum,
            # aber gemessen haelt sich das Modell nicht daran: auf Mini-Jost
            # kam in zwei von vier Laeufen eine Aufzaehlung zurueck, hier
            # seltener, aber auch.
            #
            # Was das NICHT repariert: die Stimme selbst. jarvis.js putzt
            # den Text vor dem Vorlesen ohnehin (dataset.gesprochen), es
            # wurde also nie "Sternchen Sternchen Porsche" gesprochen. Hier
            # geht es um alles andere - was angezeigt wird, was im Archiv
            # steht, was ein Test misst. Und um den Grundsatz: was sich
            # erzwingen laesst, wird erzwungen, statt es dem Modell zu
            # glauben.
            if self._gesprochen:
                from .sprache import ohne_gliederung
                antwort = ohne_gliederung(antwort)

            # Ohne Mailzugang darf keine Mailanzahl durch. Gemeldet von
            # Mini-Jost bei nachweislich leeren Zugangsdaten: "Sie haben
            # acht neue E-Mails." Hier nachgemessen, dieselbe Lage, neun
            # Laeufe: zweimal erfunden, und beide Male "acht" - genau der
            # Standardwert von postfach(anzahl=8). Das Modell macht aus
            # seinem eigenen Aufruf eine Anzahl Mails.
            #
            # Derselbe Grundsatz wie oben: was sich erzwingen laesst, wird
            # erzwungen. Bei einer Zahl ueber fremde Post ist Raten der
            # schlimmste Ausgang - man richtet sich danach.
            antwort = self._ohne_erfundene_mailzahl(antwort)
            if self.archivieren:
                # Welches Modell geantwortet hat, gehoert ins Archiv. Bei
                # Belegung wird mitten im Betrieb gewechselt (siehe
                # _einmal), und ohne diese Angabe ist hinterher nicht zu
                # entscheiden, ob eine seltsame Antwort am Prompt lag oder
                # am Modell.
                verlauf.schreiben("jarvis", antwort, self.model)
            return antwort
        except AbbruchError:
            return ""
        except Exception:
            if not self._aktuell(gen):
                return ""                   # abgebrochen - Fehler geht niemanden an
            del self.history[self._stand:]
            raise
        finally:
            if self._aktuell(gen):
                self._offener_stream = None
                self._laeuft = False

    def _runden(self, gen: int, on_status: StatusFn, on_delta: DeltaFn,
                max_tool_rounds: int,
                on_denken: DeltaFn = lambda d: None) -> str:
        leerlauf = 0                    # wie oft er gar nichts gesagt hat
        # Was schon gemeldet wurde. tools.quellen() sammelt ueber die ganze
        # Anfrage, also auch ueber mehrere Werkzeugrunden - gemeldet werden
        # soll aber jede Quelle nur einmal.
        gemeldet: list[dict] = []
        for _ in range(max_tool_rounds + 1):
            if not self._aktuell(gen):
                raise AbbruchError()
            on_status("denkt")
            text, calls = self._collect(
                self._stream(self._messages(), gen, on_status),
                gen, on_status, on_delta, on_denken)
            if not self._aktuell(gen):
                raise AbbruchError()

            if not calls:
                answer = text.strip()
                if not answer:
                    # Gemessen: das Modell liefert gelegentlich gar nichts -
                    # kein Werkzeug, kein Text. Der Mensch saehe dann eine
                    # Frage stellen und Stille bekommen. Einmal nachhaken ist
                    # besser als schweigen; bleibt es dabei, wird es gesagt.
                    if leerlauf < 1:
                        leerlauf += 1
                        self.history.append({
                            "role": "user",
                            "content": "Du hast nichts geantwortet. Fasse in "
                                       "ein bis zwei Saetzen zusammen, was du "
                                       "herausgefunden hast - und wenn es "
                                       "nichts Belastbares ist, sag genau das."
                        })
                        continue
                    answer = ("Dazu habe ich nichts Brauchbares gefunden, "
                              "Sir.")
                self.history.append({"role": "assistant", "content": answer})
                self._trim()
                return answer

            self.history.append({
                "role": "assistant",
                "content": text,
                "tool_calls": [
                    {"id": c["id"], "type": "function",
                     "function": {"name": c["name"], "arguments": c["args"] or "{}"}}
                    for c in calls
                ],
            })
            for call in calls:
                if not self._aktuell(gen):
                    raise AbbruchError()
                on_status(f"werkzeug:{call['name']}")
                # Damit ein langsames Werkzeug mitteilen kann, woran es ist
                # (etwa der Countdown vor dem Bildschirmfoto)
                tools.setze_melder(lambda text: on_status(f"info:{text}"))
                tools.setze_modell(self.model)
                try:
                    args = json.loads(call["args"] or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = tools.call(call["name"], args)
                self.history.append({"role": "tool", "tool_call_id": call["id"],
                                     "content": result})

                # Woher die Auskunft stammt, geht ueber denselben Kanal wie
                # "werkzeug:" und "info:" - als eigene Meldung, nicht im
                # Antworttext. Der Text kommt vom Modell, und das koennte
                # eine Adresse erfinden; hier steht nur, was ein Werkzeug
                # wirklich abgerufen hat.
                neue = tools.quellen()[len(gemeldet):]
                for quelle in neue:
                    gemeldet.append(quelle)
                    on_status("quelle:" + json.dumps(quelle,
                                                     ensure_ascii=False))

        self._trim()
        return "Ich drehe mich im Kreis, Sir. Bitte anders formulieren."
