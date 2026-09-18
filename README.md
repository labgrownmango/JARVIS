# JARVIS

Ein Sprachassistent im Stil von Iron Man – laeuft lokal auf Windows,
denkt mit **Kimi K3** ueber die **NVIDIA-NIM-API** (Dev-Key gratis).

## Schnellstart

Doppelklick auf **`Jarvis starten.bat`** – legt beim ersten Mal die virtuelle
Umgebung an, installiert alles und oeffnet die `.env` zum Eintragen des Keys.

## Einrichtung von Hand

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Dann Key holen auf <https://build.nvidia.com/moonshotai/kimi-k3> → *Get API Key*
(`nvapi-...`) und in die `.env` bei `JARVIS_API_KEY` eintragen.

### Stimmen herunterladen

Jarvis spricht mit **Piper** – einer neuronalen Offline-Stimme. Die Modelldateien
liegen in `voices/` und muessen einmal heruntergeladen werden:

```powershell
.\.venv\Scripts\python.exe -m piper.download_voices de_DE-thorsten-medium --data-dir voices
.\.venv\Scripts\python.exe -m piper.download_voices en_GB-alan-medium --data-dir voices
```

`de_DE-thorsten-medium` ist die deutsche Standardstimme, `en_GB-alan-medium` wird
fuer englische Stellen benutzt. Ohne diese Dateien faellt Jarvis auf die
Windows-Stimme (SAPI) zurueck.

### Datenordner

Der Ordner `data/` wird beim ersten Start **automatisch angelegt** – dort speichert
Jarvis Gespraechsverlauf, Gedaechtnis und Erinnerungen. Er muss nicht von Hand
erstellt werden.

### Wikipedia (optional)

Jarvis kann in einer lokalen Kopie der deutschen Wikipedia nachschlagen – offline,
in Millisekunden. Die Datei ist **ca. 4 GB** gross und **nicht zwingend noetig**;
ohne sie antwortet Jarvis mit „Die Wikipedia-Datei fehlt" und nutzt stattdessen
die Web-Suche.

Wer sie haben will:

1. Herunterladen von <https://download.kiwix.org> – nach `wikipedia_de_all_mini`
   suchen (ZIM-Format)
2. Ablegen als `data/wikipedia_de_all_mini.zim`

## Starten

```powershell
python -m jarvis.main            # tippen
python -m jarvis.main --voice    # reden (Enter druecken, dann sprechen)
python -m jarvis.main --stumm    # ohne Sprachausgabe
```

## Befehle

Alles mit `/` laeuft **direkt auf dem Rechner** – ohne Umweg ueber das Modell,
also sofort und kostenlos. Alles ohne `/` geht als Frage an Jarvis.

Waehrend du tippst, erscheinen die passenden Befehle darunter:

```
DU: /st
   /standort  /status  /stimme  /stumm
```

**Tab** vervollstaendigt (bei einem einzigen Treffer ganz, sonst bis zum
gemeinsamen Anfang), **Escape** leert die Zeile. Eindeutige Abkuerzungen
genuegen: `/zei` reicht fuer `/zeit`.

| Befehl | Wirkung |
|---|---|
| `/hilfe [befehl]` | alle Befehle, oder nur die passenden zu `[befehl]` |
| `/ende` | beendet Jarvis |
| `/reset` | loescht den Gespraechsverlauf |
| `/leeren` | leert den Bildschirm |
| `/modell` | zeigt Modell, Endpunkt und Laenge des Verlaufs |
| `/stumm` | Sprachausgabe an/aus |
| `/stimme [name]` | listet die Stimmen in `voices/` oder wechselt |
| `/lauter` `/leiser` | Systemlautstaerke |
| `/zeit` `/status` `/standort` | Uhrzeit, Auslastung, Standort |
| `/wetter [ort] [tage]` | Wetter hier oder anderswo, bis 7 Tage |
| `/nachrichten [thema]` | Schlagzeilen, optional zu einem Thema |
| `/code [sprache:] <aufgabe>` | schreibt ein Programm nach `werkstatt/` |
| `/werkstatt` | öffnet den Ordner mit dem geschriebenen Code |
| `/oeffne <name>` | startet ein freigegebenes Programm |
| `/merken <text>` `/gedaechtnis [suche]` | Langzeitgedaechtnis |

`/hilfe` ohne Argument zeigt die ganze Liste, `/hilfe /st` nur die mit `/st`.

Neuen Befehl anlegen – in `jarvis/commands.py` reicht eine Funktion:

```python
@befehl("/akku", "Ladestand des Akkus")
def _akku(ctx, arg):
    return "Akku bei 80 Prozent."
```

Vorschlagsliste und `/hilfe` nehmen ihn automatisch auf.

## Was er kann

| Werkzeug | Beispielsatz |
|---|---|
| `get_time` | „Welcher Tag ist heute?" |
| `system_status` | „Wie geht's dem Rechner?" |
| `open_app` | „Oeffne den Rechner." |
| `set_volume` | „Mach lauter." / „Stumm." |
| `remember` / `recall` | „Merk dir: WLAN-Passwort liegt im Safe." |
| `get_location` | „Wo bin ich eigentlich?" |
| `get_weather` | „Brauche ich morgen einen Schirm?" / „Wie ist es in Hamburg?" |
| `get_news` | „Was gibt's Neues?" / „Nachrichten zum Bundestag." |
| `look_at_screen` | „Guck dir mal meinen Bildschirm an." / „Schau in 10 Sekunden auf den Monitor." / „Was ist das für ein Fehler?" |

Standort, Wetter und Nachrichten laufen ueber kostenlose Dienste ohne Schluessel:
`ip-api.com`, `open-meteo.com`, `tagesschau.de`. Der Standort kommt aus der
IP-Adresse – das ist stadtgenau, nicht hausgenau, und **ip-api.com sieht dabei
die IP dieses Rechners**. Wer das nicht will, loescht `get_location`,
`get_weather` und `get_news` aus `REGISTRY` und `SCHEMA` in `jarvis/tools.py`.

## Aufbau

| Datei | Aufgabe |
|---|---|
| `jarvis/config.py` | `.env`, Systemprompt, Persoenlichkeit |
| `jarvis/brain.py` | Gespraechsverlauf + LLM-Aufrufe + Tool-Schleife |
| `jarvis/tools.py` | die Faehigkeiten (Whitelist, kein freies `exec`) |
| `jarvis/voice.py` | TTS via Piper (SAPI als Notnagel), STT via faster-whisper – offline |
| `jarvis/commands.py` | die Slash-Befehle |
| `jarvis/prompt.py` | Eingabezeile mit Live-Vorschlaegen und Tab |
| `jarvis/main.py` | Hauptschleife |

## Erweitern

Neue Faehigkeit in `jarvis/tools.py`:

1. Funktion schreiben, die einen kurzen String zurueckgibt
2. Eintrag in `REGISTRY`
3. Eintrag in `SCHEMA` (beschreibt dem Modell, wann es die Funktion nutzt)

## Modell wechseln

Nur die `.env` anfassen – die API ist ueberall OpenAI-kompatibel:

| Anbieter | `JARVIS_BASE_URL` | `JARVIS_MODEL` |
|---|---|---|
| NVIDIA NIM (gratis) | `https://integrate.api.nvidia.com/v1` | `moonshotai/kimi-k3` |
| Moonshot direkt | `https://api.moonshot.ai/v1` | `kimi-k3` |
| OpenRouter | `https://openrouter.ai/api/v1` | `moonshotai/kimi-k3` |

## Stimme

Standard ist **Piper** – eine neuronale Offline-Stimme, die deutlich natuerlicher
klingt als die Windows-Stimmen. Das Modell liegt in `voices/`.

Andere Stimme ausprobieren:

```powershell
.\.venv\Scripts\python.exe -m piper.download_voices de_DE-thorsten-high --data-dir voices
```

Dann in der `.env` `JARVIS_PIPER_VOICE=de_DE-thorsten-high` setzen. Auswahl:

| Stimme | Charakter |
|---|---|
| `de_DE-thorsten-medium` | maennlich, ruhig – Standard |
| `de_DE-thorsten-high` | gleiche Stimme, feiner, braucht mehr Rechenzeit |
| `de_DE-karlsson-low` | maennlich, schnell und sparsam |
| `de_DE-eva_k-x_low` | weiblich |

`JARVIS_TTS_LENGTH_SCALE` steuert das Tempo (groesser = langsamer),
`JARVIS_TTS_BACKEND=sapi` erzwingt die Windows-Stimme.

### Welche Stimme?

Es gibt zwei Wege, und der Unterschied ist größer als erwartet. Gemessen an
einem Satz von sechs Sekunden Länge:

| Stimme | Erzeugen | Tempo | Speicher |
|---|---|---|---|
| Piper `thorsten-medium` | 3,30 s | 1,8× | 205 MB |
| Piper `thorsten-high` | 4,87 s | 1,2× | 223 MB |
| **Windows Stefan** | **0,05 s** | **196×** | **6 MB** |
| **Windows Katja** | **0,08 s** | **110×** | **~0 MB** |

**Piper** sind eigene neuronale Modelle in `voices/`. Sie klingen wärmer, aber
`thorsten-high` erzeugt nur 1,2× schneller als gesprochen wird – auf einem
schwachen Rechner ist das die Schmerzgrenze.

**Windows** bringt eigene Stimmen mit (Stefan, Katja, Hedda). Nicht die alte
SAPI-Hedda, sondern neuere aus einer anderen Schnittstelle. Sie sind rund
hundertmal schneller und brauchen praktisch keinen Speicher, weil Windows sie
ohnehin geladen hat.

```
/stimme                    zeigt beide Listen
/stimme Katja              wechselt auf die Windows-Stimme
/stimme thorsten-medium    wechselt zurück auf Piper
```

Der Wechsel gilt auch für die Weboberfläche: dort sank das Erzeugen von
8,27 s auf 0,52 s.

Noch bessere Windows-Stimmen gibt es als „Natural"-Fassungen
(*Einstellungen → Barrierefreiheit → Sprachausgabe → Stimmen hinzufügen*).
Auf diesem Rechner sind sie nicht installiert, also ungetestet.

### Zwei Sprachen, zwei Stimmen

Englische Stellen werden mit englischer Stimme gesprochen (`en_GB-alan-medium`,
britisch – passt zu Jarvis), der Rest mit der deutschen. Erkannt wird das auf
zwei Wegen:

1. **Das Modell markiert.** Es setzt `<en>…</en>` um englische Stellen:

   ```
   Antwort des Modells:  Unter dem Menü <en>File</en> finden Sie <en>Save As</en>, Sir.
   auf dem Bildschirm:   Unter dem Menü File finden Sie Save As, Sir.
   ```

   Die Markierung steuert nur die Stimme und ist nie zu sehen. Das ist
   wortgenau – eine Heuristik könnte das nicht.

2. **Wortlisten fangen es auf.** Vergisst das Modell die Markierung, entscheidet
   `jarvis/sprache.py` satzweise anhand häufiger Funktionswörter. Kein
   Sprachmodell, rund **6 Mikrosekunden pro Satz**.

Gemischte Sätze werden **am Stück** erzeugt und abgespielt, nicht in Häppchen –
sonst klaffte vor „Save As" eine hörbare Pause.

Abschalten mit `JARVIS_SPRACHWECHSEL=0`, andere englische Stimme über
`JARVIS_PIPER_VOICE_EN`.

**Kostet das Tempo?** Nein. Die Sprachausgabe läuft in einem eigenen Thread und
beginnt erst, wenn ein Satz fertig ist – das Modell streamt derweil weiter. Die
englische Stimme wird beim Start nebenher geladen, nicht vorher.

### Aussprache englischer Woerter

Die Stimme liest deutsch – „Sir" wuerde als „Zirr" herauskommen. Die Tabelle
`AUSSPRACHE` in `jarvis/config.py` faengt das ab:

```python
AUSSPRACHE = {
    "Sir": "Sör",
    "CPU": "Zeh-Peh-Uh",
    ...
}
```

Links steht, was auf dem Bildschirm erscheint, rechts, was die Stimme daraus
macht. **Nur die Sprachausgabe ist betroffen**, der angezeigte Text bleibt
unveraendert. Neue Eintraege einfach ergaenzen.

## Der Hangar: Agenten für längere Aufgaben

Jarvis kann Arbeit an Hintergrundagenten abgeben – benannt wie Tony Starks
Anzüge, **Mk 1, Mk 2, Mk 3**. Sie laufen in eigenen Threads, **Jarvis bleibt
währenddessen ansprechbar**:

```
DU: /agent Sammle das Wetter fuer Berlin, Hamburg und Muenchen
Mk 1 ist unterwegs.

DU: Wie spät ist es?
JARVIS: Es ist 12:33 Uhr, Sir.          ← Mk 1 arbeitet weiter

  [Mk 1 meldet sich nach 18s - fertig]
  Berlin 19°C, Hamburg 18°C, München 20°C. München ist die wärmste Stadt.
```

Die Nummer wird nie wiederverwendet: nach Mk 3 kommt Mk 4, auch wenn die
ersten drei längst eingemottet sind.

| Befehl | Wirkung |
|---|---|
| `/agent <aufgabe>` | schickt einen Anzug los |
| `/hangar` | wer arbeitet, wie lange, wie viel Speicher |
| `/bericht [Mk 2]` | Bericht abholen und Speicher freigeben |
| `/stoppen [Mk 2]` | anhalten – ohne Namen alle |

Jarvis wählt das auch selbst, wenn eine Aufgabe danach klingt („kümmer dich
mal um…", „recherchier in Ruhe…").

### Wie viele gleichzeitig

Ein Drittel der logischen Prozessoren, höchstens vier – auf diesem Rechner
also **4 von 12**. Agenten warten überwiegend auf die API statt zu rechnen, ein
Kern pro Agent wäre Verschwendung; und mehr als eine Handvoll läuft ohnehin ins
Anfragelimit des Anbieters. Feste Zahl: `JARVIS_MAX_AGENTEN`.

### Vier Reißleinen

Ein Agent, der sich festfrisst, wird von einer Wache abgebrochen, die alle zwei
Sekunden nachsieht:

| Grenze | Standard | wogegen |
|---|---|---|
| Werkzeug-Runden | 12 | Endlosschleife aus Werkzeugaufrufen |
| Zeit | 300 s | hängende Aufgabe |
| Verlauf | 80 000 Zeichen | Agent, der sich selbst vollschreibt |
| Arbeitsspeicher | 1200 MB Prozess, 400 MB frei nötig | vollaufender RAM |

Der Abbruchgrund steht im Bericht, statt dass der Agent still verschwindet.

### Aufräumen

Sobald ein Bericht abgeholt ist, fliegen Gehirn und Gesprächsverlauf des
Agenten weg; zurück bleibt nur der Bericht als Text. Ein Test prüft per
`weakref`, dass das Objekt danach wirklich weg ist – **hier steckte ein echter
Fehler**: die Wache hielt die Agentenliste über ihren Schlaf hinweg fest und
verhinderte damit die Freigabe.

Was der Prozess an Arbeitsspeicher einmal vom Betriebssystem geholt hat, gibt
Python nicht sofort zurück (68 → 109 MB im Test, und dabei bleibt es). Die
Objekte sind frei, die Zahl in der Anzeige sinkt trotzdem nicht.

## Code schreiben

> „Schreib mir ein Python-Skript, das den Downloads-Ordner nach Dateityp sortiert."

Der Code erscheint auf dem Bildschirm und landet in `werkstatt/`. Jarvis sagt
dazu **einen Satz** – vorgelesen wird er nicht.

Direkt, ohne Umweg über das Gespräch:

```
/code ein Skript, das alte Logdateien loescht
/code powershell: zeigt die groessten Ordner
/werkstatt
```

### Warum ein eigenes Werkzeug

Das Token-Limit hochzusetzen allein hätte nichts gebracht: Jarvis' Systemprompt
verbietet Code-Blöcke und verlangt ein bis drei Sätze – weil alles vorgelesen
wird. Also bekommt Code einen **eigenen Prompt ohne Persönlichkeit**, ein
**eigenes Limit** (`JARVIS_CODE_TOKENS`, Standard 6000 statt 1024) und einen
eigenen Weg auf den Bildschirm.

Ein hohes Limit kostet auf NVIDIA NIM **kein Geld** – dort wird nichts
abgerechnet, es gibt nur das Limit von 40 Anfragen pro Minute. Es kostet
**Zeit**: Token entstehen nacheinander, eine doppelt so lange Antwort dauert
also etwa doppelt so lange. Deshalb bleibt das Gespräch bei 1024 – gesprochene
Antworten sollen kurz sein – und nur Code bekommt viel Platz, weil man ihn
liest statt hört.

`JARVIS_CODE_MODELL` leer lassen, dann schreibt das gerade laufende Modell.
Markdown-Zäune (```) werden entfernt, bevor die Datei geschrieben wird.

## Der Blick auf den Bildschirm

Jarvis kann sich ansehen, was gerade auf dem Monitor steht. Gesagt wird das
frei heraus – das Modell erkennt die Absicht selbst:

> „Guck dir mal meinen Bildschirm an."
> „Schau mal in 10 Sekunden auf meinen Monitor."
> „Was ist das da für eine Fehlermeldung?"

Bei einer Verzögerung zählt die Statuszeile herunter:

```
  Jarvis sieht in 8 s auf den Bildschirm ...   2.4s   [Esc bricht ab]
```

### Wie es funktioniert

Das Hauptmodell muss dafür **keine Bilder können**. Das Werkzeug macht den
Screenshot, schickt ihn an ein Bildmodell und gibt die Beschreibung als Text
zurück – das Gespräch führt weiter, wer es vorher geführt hat.

Aufgenommen wird in der **nativen Auflösung des Monitors**, nicht in einer
festen Breite. Bei 1920×1080 sind das 149 KB und rund 0,1 Sekunden. Erst
oberhalb von 4 Megapixeln wird proportional verkleinert (4K also, 1440p nicht);
`JARVIS_BILD_MAX_PIXEL=0` hebt auch das auf.

### Einstellungen

| Schlüssel | Bedeutung |
|---|---|
| `JARVIS_BILDSCHIRM=0` | schaltet die Fähigkeit ganz ab |
| `JARVIS_BILD_MODELL` | muss **vision** im Namen haben |
| `JARVIS_BILD_SKALIERUNG` | 1.0 = nativ, 0.5 = halbe Kantenlänge |

**Ein Textmodell als Bildmodell einzutragen fällt nicht von selbst auf**: es
antwortet mit Status 200 und leerem Text, ohne Fehlermeldung. Jarvis fängt das
ab und sagt es dir – der Test dazu steht in `bildtest.py`.

Jede Aufnahme meldet sich sichtbar:

```
  [Bildschirmfoto geht an meta/llama-3.2-11b-vision-instruct]
```

Denn dabei verlässt ein Bild deines Bildschirms den Rechner.

## Escape – die Notbremse

Waehrend Jarvis denkt oder antwortet, bricht **Escape** sofort alles ab:
die offene Verbindung wird geschlossen, die Stimme verstummt mitten im Wort,
und der angefangene Austausch wird aus dem Verlauf entfernt – damit kein halber
Werkzeug-Aufruf zurueckbleibt, der den naechsten Aufruf scheitern laesst.

Gedacht fuer den Fall, dass ein Modell haengt oder sich im Kreis dreht. Ohne
Escape wartet Jarvis bis zum Zeitlimit (`JARVIS_TIMEOUT`, Standard 120 s).

In der leeren Eingabezeile leert Escape wie gewohnt nur die Zeile.

## Modellwahl beim Start

Jarvis pingt beim Start **alle Kandidaten gleichzeitig** an – je ein Aufruf
über ein einziges Token – und zeigt das Ergebnis:

```
    moonshotai/kimi-k3                       -  belegt
  > openai/gpt-oss-20b                   13.7s  frei
    meta/llama-3.2-11b-vision-instruct    1.0s  frei
    (bestes verfügbares zuerst)
```

Das `>` markiert das gewählte Modell. Gleichzeitig gepingt, damit der Start
nicht so lange dauert wie alle Zeitlimits zusammen.

### Welches gewinnt

Die Reihenfolge in `JARVIS_MODELS` ist deine Wunschliste, bestes zuerst.
Genommen wird das **erste, das antwortet** – belegte werden übersprungen.

```
JARVIS_MODELS=moonshotai/kimi-k3,openai/gpt-oss-20b,meta/llama-3.2-11b-vision-instruct
JARVIS_MODELL_WAHL=reihenfolge
```

`JARVIS_MODELL_WAHL=schnellste` kürt stattdessen die kürzeste Antwortzeit.
**Meist keine gute Idee:** im Test war `llama-3.2` mit 1,0 s dreizehnmal
schneller als `gpt-oss` – lieferte auf Deutsch aber leeren Text. Schnell heisst
hier nicht gut. Die Zeiten siehst du in beiden Fällen.

Wird das laufende Modell mitten im Gespräch belegt, rückt automatisch das
nächste der Rangliste nach.

### Befehle

| Befehl | Wirkung |
|---|---|
| `/modell` | aktuelles Modell und die letzte Messung |
| `/modell pingen` | misst neu und wählt neu – etwa wenn K3 wieder frei ist |
| `/modell <name>` | wechselt von Hand; Teilwort genügt (`/modell llama`) |

Das Anpingen abschalten: `JARVIS_STARTUP_CHECK=0`. Dann startet Jarvis sofort
und nimmt das erste Modell aus `JARVIS_MODELS` – merkt ein belegtes Modell aber
erst bei der ersten Frage.

## Während des Wartens

Jarvis zeigt an, woran er gerade ist – „Jarvis denkt", „Jarvis prüft das System" –
und beginnt zu sprechen, sobald der erste Satz fertig ist, nicht erst am Ende
der ganzen Antwort.

## Diagnose

```powershell
.\.venv\Scripts\python.exe selbsttest.py   # Installation, Stimmen, Mikrofon (ohne API)
.\.venv\Scripts\python.exe stimmtest.py    # spricht vier Saetze - prueft die Stimme
.\.venv\Scripts\python.exe demotest.py     # Trockenlauf der Oberflaeche ohne API
.\.venv\Scripts\python.exe befehlstest.py  # Slash-Befehle und Vorschlaege
.\.venv\Scripts\python.exe apitest.py      # Standort, Wetter, Nachrichten
.\.venv\Scripts\python.exe keytest.py      # prueft den Key gegen NVIDIA NIM
```

Zeigt die Eingabezeile Zeichensalat statt Vorschlaegen, setz
`JARVIS_SIMPLE_INPUT=1` in der `.env` – dann laeuft sie ohne Vorschlaege,
aber in jeder Konsole.

`keytest.py` gibt den Key nie aus, nur Laenge und Statuscodes.
Kommt bei `/models` eine 200, beim Chat aber eine 403, ist der Key gueltig,
das Konto aber noch nicht fuer Inferenz freigeschaltet.

## Hinweise

- `.env` niemals committen – sie enthaelt deinen Key.
- Deutsche Stimme fehlt? Windows-Einstellungen → Zeit und Sprache → Sprache →
  deutsches Sprachpaket mit Sprachausgabe installieren.
- Erster Start mit `--voice` laedt das Whisper-Modell herunter (einige hundert MB),
  danach laeuft die Erkennung offline.
