# Stand vom 13. September 2026

Geschrieben, weil der Rechner eine Woche ohne dich läuft. Hier steht, was
offen ist und woran du anknüpfst — ohne den ganzen Gesprächsverlauf.

## Das kannst du diese Woche benutzen

Jarvis läuft weiter und ist **aus dem Tailnet erreichbar**, also von deinem
Handy aus jedem WLAN:

```
https://empfang02pc.tailef282f.ts.net/
```

Das ist die Adresse mit Mikrofonfreigabe. Der alte Kurzname `http://jarvis/`
geht auch, aber dort sperrt der Browser das Mikrofon (kein HTTPS).

Nachgewiesen privat: `tailscale serve status` und `funnel status` sagen beide
"tailnet only", und `100.84.15.44` liegt im CGNAT-Bereich — aus dem Internet
nicht routbar. Selbst aus dem Heim-WLAN kommt man nicht dran (403).

## Das Einzige, was Handarbeit braucht

**Das Mikrofon am Trust-Headset liefert nichts.** Bewiesen über drei
voneinander unabhängige Wege:

| Weg | Ergebnis |
|---|---|
| Jarvis über PortAudio | 1,4 × 10⁻⁵ über 18 597 Blöcke unverändert |
| Browser über Chromium | "nichts verstanden" |
| Windows' eigener Pegelmesser | 0,00000 — in Stille wie bei Wiedergabe |

Was **funktioniert**: der Ton ZUM Headset. Die Testansage war zu hören. Also
ist die Funkstrecke in Ordnung, der Akku reicht, der Empfänger sitzt.

Daraus folgt: das Mikrofon ist am Headset selbst stummgeschaltet. Bei diesem
Modell am wahrscheinlichsten der **hochgeklappte Bügel** — viele Trust-GXT
schalten dann stumm, ohne jede Anzeige. Sonst eine Stummtaste an Muschel oder
USB-Empfänger.

**Wenn du wieder da bist:** Bügel runter, Seite öffnen, auf die Pegelzeile
unter den Modus-Knöpfen sehen und sprechen. Bewegt sich der linke Balken,
funktioniert „Hey Jarvis" sofort — alles andere steht schon.

Im Chat zeigt `/mikrofon` alle neun Eingabegeräte, welches benutzt wird und
was ankommt. Falls ein anderes Gerät läuft, sagt `/mikrofon <nummer>`, wie man
umstellt.

## Umzug auf Mini-Jost

`jarvis-umzug.zip` (212 MB) liegt im Projektordner. Enthält den Quellcode und
die Sprachstimmen — damit drüben nichts heruntergeladen werden muss.

**Nicht enthalten:** `.venv`, `data/`, die Wikipedia-Datei und die `.env`.
Die `.env` bewusst nicht: dort steht der API-Schlüssel im Klartext.

Sobald Mini-Jost online ist:

```
tailscale file cp jarvis-umzug.zip Mini-Jost:
```

Drüben: auspacken, `py -m venv .venv`, `pip install -r requirements.txt`,
`.env` von Hand hinkopieren.

## Was an diesem Tag entstanden ist

- **Mehrere Chats** statt eines endlosen Fadens. `/neu`, `/chats`, `/clear`.
  Löschen wandert in `data/geloescht.jsonl` statt ins Nichts.
- **Slash-Befehle in der Weboberfläche** — vorher gingen sie ans Modell, das
  sich daraufhin eine Befehlsliste ausdachte, die es nie gab.
- **Markdown** in den Antworten, selbst geschrieben, ohne fremde Bibliothek.
  Modelltext wird nie als HTML eingesetzt.
- **Der Gedankengang** wird abgetrennt und als „Jarvis hat gedacht"
  aufklappbar angezeigt, statt mitten in der Antwort zu stehen.
- **Bedeutungssuche** im Archiv über `nemotron-3-embed-1b`. „ging es mal um
  Preise" findet jetzt die RTX-Anfrage, die die Textsuche nie fand.
- **Arc-Reaktor** statt Statuszeile, mit echten Werkzeugnamen.
- **Jahreszahlen** werden vorgelesen wie Jahre: 1861 ist
  „achtzehnhunderteinundsechzig".
- **Der Browser** ist repariert (er schloss sein eigenes Fenster) und
  gehärtet: kein JavaScript ohne Schalter, nichts nach localhost, ins
  Heimnetz oder ins Tailnet, nur http und https.

- **Übersetzer** (`uebersetzen`) über `riva-translate-4b-instruct-v2`.
  Jarvis nimmt ihn von selbst. Die Zielsprache muss in der Nutzerzeile
  stehen — im Systemprompt wird sie ignoriert, dann kommt alles auf
  Englisch. Gemessene Grenze: Englisch, Französisch, Spanisch und
  Italienisch sauber; bei selteneren Sprachen bleiben Teile stehen.

**Testlauf: 40 von 40 grün** (13.09.2026, 844 Sekunden).

## Offen

- **Mikrofon** — siehe oben, braucht dich.
- **magpie-tts-zeroshot**: eigene Stimme aus einer Hörprobe. Braucht eine
  Aufnahme, also ein funktionierendes Mikrofon.
- **studiovoice / bnr**: Rauschunterdrückung vor der Spracherkennung.
- **Gmail**: `JARVIS_MAIL_BENUTZER` und `JARVIS_MAIL_PASSWORT` fehlen in der
  `.env` (App-Passwort, nicht das normale).
- **Der Ordner „Löschen"** auf dem Desktop enthält Patientendaten mit
  Klarnamen. Das ist keine Aufräumfrage, sondern eine für die Praxis — erst
  klären, dass die Originale dort liegen, dann sicher löschen.
  `Daten Domain etc.jpg` und die `.rdp`/`.rdg`-Dateien gehören unabhängig
  davon vernichtet.
- **Domäne**: der Rechner hängt noch in `kaiser.local`. Nicht austreten,
  bevor ein lokales Konto mit Administratorrechten funktioniert und du
  dessen Passwort kennst.
