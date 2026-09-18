"""Stimme und Ohren - alles offline, kein Key nötig.

Sprachausgabe, in dieser Reihenfolge:
  1. Piper  - neuronale Stimme, klingt natuerlich (Standard)
  2. SAPI   - die eingebauten Windows-Stimmen, direkt über COM angesteuert
Sprachaufnahme: faster-whisper, lokal.
"""
from __future__ import annotations

import queue
import re
import sys
import threading

from . import config
from .sprache import erkenne as sprache_von

# Satzende erkennen, damit während des Streamings schon gesprochen werden kann
_SENTENCE_END = re.compile(r"(?<=[.!?:;])\s+|\n+")

# Sprachmarkierungen des Modells - steuern die Stimme, werden nie angezeigt
_TAGS = ("<en>", "</en>", "<de>", "</de>")
_TAG = re.compile(r"</?(?:en|de)>", re.IGNORECASE)

# Lautschrift-Ersetzungen: laengste Eintraege zuerst, damit "Updates" nicht
# als "Update" + "s" zerfaellt.
_AUSSPRACHE_RE = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in
                      sorted(config.AUSSPRACHE, key=len, reverse=True)) + r")\b",
    re.IGNORECASE) if config.AUSSPRACHE else None
_AUSSPRACHE_MAP = {k.lower(): v for k, v in config.AUSSPRACHE.items()}


# --- Jahreszahlen -----------------------------------------------------------
# Deutsch liest Jahre anders als Mengen: 1861 ist "achtzehnhunderteinundsechzig"
# und nicht "eintausendachthunderteinundsechzig". Die Sprachausgabe kennt den
# Unterschied nicht - gemessen bei einer Antwort ueber das MIT, gegruendet 1861.
_EINER = ("null", "ein", "zwei", "drei", "vier", "fuenf", "sechs", "sieben",
          "acht", "neun", "zehn", "elf", "zwoelf", "dreizehn", "vierzehn",
          "fuenfzehn", "sechzehn", "siebzehn", "achtzehn", "neunzehn")
_ZEHNER = ("", "", "zwanzig", "dreissig", "vierzig", "fuenfzig", "sechzig",
           "siebzig", "achtzig", "neunzig")

# Was nach der Zahl steht und sie zu einer Menge macht, nicht zu einem Jahr.
_EINHEIT = re.compile(
    r"\s*(?:€|\$|%|°|euro|dollar|cent|meter|metern|km|kilometer|cm|mm|kg|"
    r"gramm|tonnen|liter|ml|mb|gb|tb|kb|byte|bytes|stueck|stück|mal|watt|w|"
    r"kwh|ps|grad|kalorien|schritte|punkte|zeichen|woerter|wörter|seiten|"
    r"personen|menschen|einwohner|teilnehmer|dollar)\b", re.IGNORECASE)

# Davor darf keine Ziffer und kein Trennzeichen stehen (sonst waere "10.1861"
# eine Versionsnummer). Danach darf keine Ziffer folgen - ein Satzpunkt aber
# sehr wohl: "gegruendet 1918." ist der Normalfall, und die erste Fassung
# liess genau den durchfallen.
_JAHR = re.compile(
    r"(?<![\d.,:/-])(1[1-9]\d{2}|20\d{2})(?!\d)(?![.,:/-]\d)")


def _zwei_stellen(zahl: int) -> str:
    if zahl < 20:
        return _EINER[zahl]
    zehner, einer = divmod(zahl, 10)
    if not einer:
        return _ZEHNER[zehner]
    return f"{_EINER[einer]}und{_ZEHNER[zehner]}"


def _jahr_in_worten(zahl: int) -> str:
    hundert, rest = divmod(zahl, 100)
    if zahl >= 2000:
        # 2006 heisst "zweitausendsechs", nicht "zwanzighundertsechs"
        kopf = "zweitausend"
        return kopf + (_zwei_stellen(rest) if rest else "")
    kopf = f"{_zwei_stellen(hundert)}hundert"
    return kopf + (_zwei_stellen(rest) if rest else "")


def jahreszahlen(text: str) -> str:
    """Schreibt Jahreszahlen aus - nur fuer die Stimme, nie fuer den Bildschirm."""
    def ersetzen(treffer: re.Match) -> str:
        if _EINHEIT.match(text, treffer.end()):
            return treffer.group(0)      # "1500 Euro" ist keine Jahreszahl
        return _jahr_in_worten(int(treffer.group(1)))

    return _JAHR.sub(ersetzen, text)


def lautschrift(text: str) -> str:
    """Ersetzt englische Wörter durch deutsche Lautschrift - nur für die
    Sprachausgabe. Der angezeigte Text bleibt davon unberührt."""
    text = jahreszahlen(text)
    if _AUSSPRACHE_RE is None:
        return text
    return _AUSSPRACHE_RE.sub(
        lambda m: _AUSSPRACHE_MAP[m.group(0).lower()], text)


class _SpeakerBase:
    """Sprechen laeuft in einem eigenen Thread, sonst blockiert die Eingabe."""

    def __init__(self) -> None:
        self.enabled = True
        # Eingereiht wird (Text, Sprache) - die Sprache steht schon fest,
        # damit der Sprech-Thread nichts mehr entscheiden muss
        self._q: queue.Queue[tuple[str, str] | None] = queue.Queue()
        self._idle = threading.Event()
        self._idle.set()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    # -- von den Backends zu fuellen ---------------------------------------
    def _setup(self) -> None: ...
    def _speak(self, text: str, sprache: str = "de") -> None: ...

    def _loop(self) -> None:
        try:
            self._setup()
        except Exception as exc:                  # pragma: no cover
            print(f"[TTS] Start fehlgeschlagen: {exc}", file=sys.stderr)
            self.enabled = False
            return
        while True:
            auftrag = self._q.get()
            if auftrag is None:
                break
            self._idle.clear()
            try:
                self._speak(auftrag)
            except Exception as exc:              # pragma: no cover
                print(f"[TTS] {exc}", file=sys.stderr)
            finally:
                if self._q.empty():
                    self._idle.set()

    # -- oeffentlich --------------------------------------------------------
    def say(self, text: str, sprache: str | None = None) -> None:
        """sprache=None: selbst erkennen. Sonst die vom Modell markierte."""
        self.say_teile([(text, sprache)])

    def say_teile(self, teile: list) -> None:
        """Ein Satz, moeglicherweise aus Stuecken in zwei Sprachen.

        Sie werden gemeinsam eingereiht und am Stueck abgespielt - sonst
        klaffte zwischen "Der Befehl heisst" und "save as" eine Pause.
        """
        fertig = []
        for text, sprache in teile:
            text = text.strip()
            if not text:
                continue
            if not config.SPRACHWECHSEL:
                sprache = "de"
            elif sprache is None:
                sprache = sprache_von(text)
            # Lautschrift nur fuer deutsche Stuecke: im englischen Satz
            # spricht die englische Stimme "Sir" ohnehin richtig aus
            fertig.append((lautschrift(text) if sprache == "de" else text,
                           sprache))
        if self.enabled and fertig:
            self._idle.clear()
            self._q.put(fertig)

    def wait(self, timeout: float = 120.0) -> None:
        """Wartet, bis alles Gesprochene wirklich raus ist."""
        if self.enabled:
            self._idle.wait(timeout)

    def verstummen(self) -> None:
        """Sofort still sein: Wartendes verwerfen, Laufendes abschneiden.
        Wird von der Escape-Notbremse benutzt."""
        while True:
            try:
                self._q.get_nowait()
            except queue.Empty:
                break
        self._abbrechen()
        self._idle.set()

    def _abbrechen(self) -> None:
        """Von den Backends überschrieben, falls sie laufenden Ton stoppen."""


class PiperSpeaker(_SpeakerBase):
    """Neuronale Stimme, eine pro Sprache.

    Die deutsche Stimme wird sofort geladen, die englische nebenher - sonst
    wuerde der Start eine Sekunde laenger dauern fuer etwas, das vielleicht
    nie gebraucht wird. Ist sie beim ersten englischen Satz noch nicht fertig,
    spricht ihn die deutsche Stimme; auffallen wuerde das nur einmal.
    """

    def _setup(self) -> None:
        import sounddevice as sd
        from piper import PiperVoice
        from piper.config import SynthesisConfig

        self._sd = sd
        self._PiperVoice = PiperVoice
        self._cfg = SynthesisConfig(length_scale=config.TTS_LENGTH_SCALE,
                                    volume=config.TTS_VOLUME)
        self._stimmen: dict[str, object] = {
            "de": PiperVoice.load(str(config.PIPER_MODEL))}

        if config.SPRACHWECHSEL and config.PIPER_MODEL_EN.exists():
            threading.Thread(target=self._englisch_nachladen,
                             daemon=True).start()

    def _englisch_nachladen(self) -> None:
        try:
            self._stimmen["en"] = self._PiperVoice.load(
                str(config.PIPER_MODEL_EN))
        except Exception as exc:                  # pragma: no cover
            print(f"[Stimme] Englisch nicht geladen: {exc}", file=sys.stderr)

    def _speak(self, teile: list) -> None:
        """Alle Stuecke eines Satzes erzeugen und am Stueck abspielen."""
        import numpy as np

        stuecke, rate = [], None
        for text, sprache in teile:
            stimme = self._stimmen.get(sprache) or self._stimmen["de"]
            if rate is None:
                rate = stimme.config.sample_rate
            elif rate != stimme.config.sample_rate:
                # Verschiedene Abtastraten lassen sich nicht aneinanderhaengen
                self._abspielen(stuecke, rate)
                stuecke, rate = [], stimme.config.sample_rate
            for chunk in stimme.synthesize(text, syn_config=self._cfg):
                stuecke.append(chunk.audio_int16_array)
        self._abspielen(stuecke, rate)

    def _abspielen(self, stuecke: list, rate) -> None:
        if not stuecke:
            return
        import numpy as np

        self._sd.play(np.concatenate(stuecke), rate)
        self._sd.wait()

    def _abbrechen(self) -> None:
        try:
            self._sd.stop()
        except Exception:
            pass


class WindowsSpeaker(_SpeakerBase):
    """Die Stimmen, die Windows selbst mitbringt - Stefan, Katja und Hedda.

    Nicht zu verwechseln mit der alten SAPI-Hedda: diese hier liegen in einer
    neueren Schnittstelle (WinRT) und klingen deutlich runder. Sie kosten fast
    nichts, weil Windows sie ohnehin geladen hat - kein eigenes Modell, kein
    eigener Speicher.

    Zweisprachig ist das auch: fuer englische Stellen wird eine englische
    Windows-Stimme genommen, falls eine da ist.
    """

    def _setup(self) -> None:
        import asyncio

        import sounddevice as sd
        import winsdk.windows.media.speechsynthesis as sprache

        self._sd = sd
        self._sprache = sprache
        self._schleife = asyncio.new_event_loop()
        self._stimmen = {}

        alle = list(sprache.SpeechSynthesizer.all_voices)
        for kuerzel, sprachcode in (("de", "de-"), ("en", "en-")):
            gewuenscht = (config.WIN_STIMME if kuerzel == "de"
                          else config.WIN_STIMME_EN).lower()
            passend = [v for v in alle if v.language.lower().startswith(sprachcode)]
            if not passend:
                continue
            treffer = ([v for v in passend if gewuenscht in v.display_name.lower()]
                       or passend)
            sprecher = sprache.SpeechSynthesizer()
            sprecher.voice = treffer[0]
            self._stimmen[kuerzel] = sprecher
        if "de" not in self._stimmen:
            raise RuntimeError("keine deutsche Windows-Stimme gefunden")

    def _erzeugen(self, text: str, sprache_kuerzel: str) -> bytes:
        import io
        import wave

        sprecher = self._stimmen.get(sprache_kuerzel) or self._stimmen["de"]
        strom = self._schleife.run_until_complete(
            sprecher.synthesize_text_to_stream_async(text))

        leser = self._sprache.__dict__  # nur damit der Import benutzt wirkt
        del leser
        from winsdk.windows.storage.streams import DataReader

        daten = DataReader(strom.get_input_stream_at(0))
        self._schleife.run_until_complete(daten.load_async(strom.size))
        roh = bytes(daten.read_buffer(strom.size))

        with wave.open(io.BytesIO(roh)) as datei:   # WAV kommt fertig zurueck
            return datei.readframes(datei.getnframes()), datei.getframerate()

    def _speak(self, teile: list) -> None:
        import numpy as np

        stuecke, rate = [], 22050
        for text, sprache_kuerzel in teile:
            roh, rate = self._erzeugen(text, sprache_kuerzel)
            stuecke.append(np.frombuffer(roh, dtype=np.int16))
        if stuecke:
            self._sd.play(np.concatenate(stuecke), rate)
            self._sd.wait()

    def _abbrechen(self) -> None:
        try:
            self._sd.stop()
        except Exception:
            pass


class SapiSpeaker(_SpeakerBase):
    """Windows-Bordmittel. Direkt über COM, weil pyttsx3 im Thread abbricht."""

    def _setup(self) -> None:
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        self._engine = win32com.client.Dispatch("SAPI.SpVoice")
        hint = config.TTS_VOICE_HINT.lower()
        for token in self._engine.GetVoices():
            if hint in token.GetDescription().lower():
                self._engine.Voice = token
                break
        # SAPI-Skala ist -10..10; 185 Wörter/Minute entsprechen etwa 0
        self._engine.Rate = max(-10, min(10, round((config.TTS_RATE - 185) / 25)))

    def _speak(self, teile: list) -> None:
        # SAPI-Notnagel: hier gibt es nur die eine eingestellte Stimme
        self._engine.Speak(" ".join(t for t, _ in teile))   # blockiert bis fertig


class NullSpeaker:
    """Wenn nichts geht: still, aber das Programm laeuft weiter."""
    enabled = False

    def say(self, text: str, sprache: str | None = None) -> None: ...
    def say_teile(self, teile: list) -> None: ...
    def wait(self, timeout: float = 0) -> None: ...
    def verstummen(self) -> None: ...


def make_speaker() -> "_SpeakerBase | NullSpeaker":
    if not config.TTS_ENABLED:
        return NullSpeaker()

    order = (["piper", "windows", "sapi"] if config.TTS_BACKEND == "auto"
             else [config.TTS_BACKEND])
    for backend in order:
        try:
            if backend == "piper":
                if not config.PIPER_MODEL.exists():
                    raise FileNotFoundError(
                        f"Stimmdatei fehlt: {config.PIPER_MODEL.name}")
                speaker = PiperSpeaker()
            elif backend == "windows":
                speaker = WindowsSpeaker()
            elif backend == "sapi":
                speaker = SapiSpeaker()
            else:
                continue
            speaker.wait(timeout=20)      # wartet das _setup() im Thread ab
            if speaker.enabled:
                print(f"[Stimme] {backend}")
                return speaker
        except Exception as exc:
            print(f"[Stimme] {backend} nicht verfügbar: {exc}", file=sys.stderr)
    print("[Stimme] keine verfügbar - Jarvis bleibt stumm.", file=sys.stderr)
    return NullSpeaker()


class SentenceSpeaker:
    """Nimmt Text-Häppchen aus dem Stream, spricht fertige Sätze und gibt
    zurück, was auf den Bildschirm soll.

    Das Modell markiert englische Stellen mit <en>...</en>. Diese Markierung
    wird hier ausgewertet und entfernt - sie steuert die Stimme, ist aber nie
    zu sehen. Beim Streamen kommt ein Tag oft zerstueckelt an ("<", "en", ">"),
    deshalb wird ein angefangenes Tag zurueckgehalten, bis es vollstaendig ist.

    Vergisst das Modell die Markierung, entscheidet die Wortliste in
    jarvis/sprache.py - so oder so wird die richtige Stimme gewaehlt.
    """

    def __init__(self, speaker) -> None:
        self.speaker = speaker
        self._roh = ""          # noch nicht ausgewerteter Rohtext
        self._satz = ""         # angefangenes Stueck des laufenden Satzes
        self._teile: list = []  # fertige Stuecke dieses Satzes, mit Sprache
        self._sprache = None    # None = keine Markierung, also Wortliste

    # -- Tags ---------------------------------------------------------------
    @staticmethod
    def _angefangenes_tag(text: str) -> int:
        """Position, ab der ein moeglicherweise unvollstaendiges Tag beginnt."""
        spitz = text.rfind("<")
        if spitz == -1:
            return len(text)
        rest = text[spitz:]
        if any(t.startswith(rest) for t in _TAGS):
            return spitz
        return len(text)

    def feed(self, delta: str) -> str:
        self._roh += delta
        sichtbar = []

        while True:
            treffer = _TAG.search(self._roh)
            if treffer:
                vor = self._roh[:treffer.start()]
                if vor:
                    sichtbar.append(vor)
                    self._sammeln(vor)
                # Sprachwechsel: das bisherige Stueck abschliessen, aber den
                # Satz nicht aussprechen - er geht in der neuen Sprache weiter
                self._stueck_abschliessen()
                marke = treffer.group(0).lower()
                self._sprache = "en" if marke == "<en>" else "de"
                self._roh = self._roh[treffer.end():]
                continue

            halt = self._angefangenes_tag(self._roh)
            fertig, self._roh = self._roh[:halt], self._roh[halt:]
            if fertig:
                sichtbar.append(fertig)
                self._sammeln(fertig)
            break

        return "".join(sichtbar)

    # -- Saetze -------------------------------------------------------------
    def _sammeln(self, text: str) -> None:
        self._satz += text
        while True:
            match = _SENTENCE_END.search(self._satz)
            if not match:
                break
            self._satz, rest = (self._satz[:match.start()],
                                self._satz[match.end():])
            self._stueck_abschliessen()
            self._satz_sprechen()
            self._satz = rest

    def _stueck_abschliessen(self) -> None:
        """Das angefangene Stueck in der jetzigen Sprache festhalten."""
        if self._satz.strip():
            self._teile.append((self._satz, self._sprache))
        self._satz = ""

    def _satz_sprechen(self) -> None:
        if self._teile:
            self.speaker.say_teile(self._teile)
            self._teile = []

    def flush(self) -> str:
        """Rest ausgeben - auch ein halb angefangenes Tag, falls das Modell
        mittendrin aufhoert."""
        rest, self._roh = self._roh, ""
        if rest:
            self._sammeln(rest)
        self._stueck_abschliessen()
        self._satz_sprechen()
        return rest


# --- Spracheingabe ----------------------------------------------------------
class Ears:
    SAMPLE_RATE = 16_000

    def __init__(self) -> None:
        import numpy as np
        import sounddevice as sd
        from faster_whisper import WhisperModel

        self.np, self.sd = np, sd
        print(f"[Ohren] lade '{config.STT_MODEL}' ...", flush=True)
        self.model = WhisperModel(config.STT_MODEL, device="auto",
                                  compute_type="int8")

    def stille_fuer(self, gesprochen_sekunden: float) -> float:
        """Wie lange Stille reicht, um das Ende zu erkennen?

        Frueher immer 1,2 Sekunden - egal ob "Hallo?" oder drei Saetze. Bei
        einem einzelnen Wort ist das laenger als das Wort selbst, und die
        Antwort fuehlt sich traege an, obwohl nichts langsam ist.

        Wer kurz spricht, ist meistens fertig. Wer lange spricht, macht
        mitten im Satz Pausen zum Nachdenken - da waere ein kurzes Fenster
        schlimmer, weil es einen mitten im Satz unterbricht. Also waechst
        das Fenster mit der Laenge des Gesagten.
        """
        kurz, lang = config.STT_STILLE_KURZ, config.STT_STILLE_LANG
        if gesprochen_sekunden <= 1.0:
            return kurz
        if gesprochen_sekunden >= 3.0:
            return lang
        anteil = (gesprochen_sekunden - 1.0) / 2.0
        return kurz + (lang - kurz) * anteil

    def record_until_silence(self, max_seconds: int = 20,
                             silence_seconds: float = 0.0,
                             threshold: float = 0.012):
        """Nimmt auf, bis es still ist - und zwar gerade so lange wie noetig."""
        np, sd = self.np, self.sd
        block = 1024
        pro_sekunde = self.SAMPLE_RATE / block
        chunks, silent_blocks, spoke = [], 0, False
        gesprochene_bloecke = 0
        max_blocks = int(max_seconds * pro_sekunde)
        # Wer gar nicht anfaengt, soll nicht bis zum Zeitlimit festgehalten
        # werden. Vorher lief das Mikrofon volle zwanzig Sekunden, wenn
        # niemand sprach - und danach kam "nichts verstanden".
        vorlauf_bloecke = int(config.STT_VORLAUF * pro_sekunde)

        with sd.InputStream(samplerate=self.SAMPLE_RATE, channels=1,
                            dtype="float32", blocksize=block) as stream:
            for nummer in range(max_blocks):
                data, _overflow = stream.read(block)
                chunks.append(data.copy())
                laut = float(np.sqrt(np.mean(data ** 2))) > threshold
                if laut:
                    spoke, silent_blocks = True, 0
                    gesprochene_bloecke += 1
                elif spoke:
                    silent_blocks += 1
                    noetig = silence_seconds or self.stille_fuer(
                        gesprochene_bloecke / pro_sekunde)
                    if silent_blocks >= int(noetig * pro_sekunde):
                        break
                elif nummer >= vorlauf_bloecke:
                    break                     # es kommt nichts, also gut
        if not spoke:
            return np.zeros(0, dtype="float32")
        return np.concatenate(chunks).flatten()

    def transcribe(self, audio) -> str:
        if len(audio) == 0:
            return ""
        segments, _info = self.model.transcribe(
            audio, language=config.STT_LANGUAGE, vad_filter=True)
        return " ".join(seg.text for seg in segments).strip()

    def listen(self) -> str:
        return self.transcribe(self.record_until_silence())


# --- Für die Weboberfläche --------------------------------------------------
# Dort wird der Ton im Browser abgespielt, nicht hier: nur so kann die
# Oberflaeche die Frequenzen messen und die Balken danach ausschlagen lassen.
_stimmen_web: dict = {}
_ohren_web: "Ears | None" = None
_web_schloss = threading.Lock()


def _stimme_holen(sprache: str):
    from piper import PiperVoice

    with _web_schloss:
        if sprache not in _stimmen_web:
            pfad = config.PIPER_MODEL_EN if sprache == "en" else config.PIPER_MODEL
            if not pfad.exists():
                pfad = config.PIPER_MODEL
            _stimmen_web[sprache] = PiperVoice.load(str(pfad))
        return _stimmen_web[sprache]


_win_web = None


def _windows_wav(text: str) -> bytes:
    """Dasselbe mit den Windows-Stimmen - hundertmal schneller als Piper
    und praktisch ohne Speicherbedarf."""
    import io
    import wave

    import numpy as np

    global _win_web
    with _web_schloss:
        if _win_web is None:
            _win_web = WindowsSpeaker.__new__(WindowsSpeaker)
            _win_web._setup()

    stuecke, rate = [], 22050
    for satz in [s for s in _SENTENCE_END.split(text) if s and s.strip()]:
        sprache = sprache_von(satz) if config.SPRACHWECHSEL else "de"
        gesprochen = lautschrift(satz) if sprache == "de" else satz
        roh, rate = _win_web._erzeugen(gesprochen, sprache)
        stuecke.append(np.frombuffer(roh, dtype=np.int16))

    if not stuecke:
        return b""
    puffer = io.BytesIO()
    with wave.open(puffer, "wb") as datei:
        datei.setnchannels(1)
        datei.setsampwidth(2)
        datei.setframerate(rate)
        datei.writeframes(np.concatenate(stuecke).tobytes())
    return puffer.getvalue()


def zu_wav(text: str) -> bytes:
    """Spricht den Text und gibt ihn als WAV zurück, statt ihn abzuspielen.

    Satzweise, damit deutsche und englische Stellen ihre eigene Stimme
    bekommen - wie bei der Terminalfassung auch.
    """
    import io
    import wave

    import numpy as np

    if config.TTS_BACKEND == "windows":
        return _windows_wav(text)

    from piper.config import SynthesisConfig

    einstellung = SynthesisConfig(length_scale=config.TTS_LENGTH_SCALE,
                                  volume=config.TTS_VOLUME)
    stuecke, rate = [], 22050
    for satz in [s for s in _SENTENCE_END.split(text) if s and s.strip()]:
        sprache = sprache_von(satz) if config.SPRACHWECHSEL else "de"
        stimme = _stimme_holen(sprache)
        rate = stimme.config.sample_rate
        gesprochen = lautschrift(satz) if sprache == "de" else satz
        for chunk in stimme.synthesize(gesprochen, syn_config=einstellung):
            stuecke.append(chunk.audio_int16_array)

    if not stuecke:
        return b""
    ton = np.concatenate(stuecke)

    puffer = io.BytesIO()
    with wave.open(puffer, "wb") as datei:
        datei.setnchannels(1)
        datei.setsampwidth(2)
        datei.setframerate(rate)
        datei.writeframes(ton.tobytes())
    return puffer.getvalue()


_letztes_hoeren = 0.0


def _ohren_entladen() -> None:
    """Gibt die Spracherkennung wieder frei, wenn länger niemand spricht.

    Sie belegt rund 700 MB - auf einem Rechner mit 8 GB ist das der
    Unterschied zwischen "läuft" und "der Server stirbt still". Beim nächsten
    Mal dauert der erste Satz dafür ein paar Sekunden länger.
    """
    import gc
    import time

    global _ohren_web
    while True:
        time.sleep(20)
        with _web_schloss:
            if _ohren_web is None:
                return
            if time.monotonic() - _letztes_hoeren < config.STT_LEERLAUF:
                continue
            _ohren_web = None
        gc.collect()
        print("[Ohren] entladen, Speicher freigegeben", flush=True)
        return


def verstehen(audio: bytes) -> str:
    """Nimmt eine Aufnahme aus dem Browser und macht Text daraus.

    Läuft mit faster-whisper auf diesem Rechner - kein Dienst, kein Schlüssel,
    keine Daten, die das Haus verlassen.
    """
    import io
    import time

    global _ohren_web, _letztes_hoeren
    with _web_schloss:
        neu = _ohren_web is None
        if neu:
            _ohren_web = Ears()
        ohren = _ohren_web
    if neu:
        threading.Thread(target=_ohren_entladen, daemon=True).start()

    _letztes_hoeren = time.monotonic()
    segmente, _ = ohren.model.transcribe(
        io.BytesIO(audio), language=config.STT_LANGUAGE, vad_filter=True)
    _letztes_hoeren = time.monotonic()
    return " ".join(s.text for s in segmente).strip()


def try_make_ears() -> "Ears | None":
    try:
        return Ears()
    except ImportError as exc:
        print(f"[Ohren] fehlendes Paket: {exc.name}", file=sys.stderr)
    except Exception as exc:                      # pragma: no cover
        print(f"[Ohren] Mikrofon/STT-Problem: {exc}", file=sys.stderr)
    return None
