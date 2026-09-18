"""Die drei harten Verbote - an einer Stelle, damit sie nicht verrutschen.

Vom Betreiber gesetzt, nicht verhandelbar:

1. KEINE DOWNLOADS. Jarvis holt nie eine Datei aus dem Netz auf die Platte.
   Nicht mit Nachfrage, nicht mit Genehmigung, gar nicht. Er darf Seiten
   LESEN - der Text landet im Arbeitsspeicher und ist nach der Antwort weg.
2. KEIN JAVASCRIPT. Seiten kommen als Quelltext. Es wird nichts ausgefuehrt,
   nichts nachgeladen, keine Browser-Engine gestartet.
3. KEINE TERMINALBEFEHLE OHNE ANFRAGE. Was eine Shell oeffnet oder einen
   Befehl absetzt, braucht vorher ein Ja vom Menschen.

Warum hier und nicht verstreut in tools.py: ein Verbot, das an fuenf Stellen
steht, ist an der sechsten vergessen. Und verbotstest.py durchsucht den
Quelltext danach, ob jemand daran vorbeigebaut hat.
"""
from __future__ import annotations

import re

# --- 1. Downloads -----------------------------------------------------------
# Was read_page ueberhaupt verarbeiten darf. Alles andere ist eine Datei und
# damit ein Download, egal wie die Adresse endet.
ERLAUBTE_TYPEN = ("text/html", "text/plain", "application/xhtml",
                  "application/xml", "text/xml")

# Ein Server kann eine Datei auch als Text ausgeben. Dieser Kopf verraet die
# Absicht: "lad mich herunter".
_ANHANG = re.compile(r"attachment", re.IGNORECASE)

# Obergrenze fuer das, was ueberhaupt eingelesen wird. Ohne sie koennte eine
# Seite den Speicher des Rechners fuellen - 8 GB, davon oft nur 1,8 GB frei.
MAX_SEITE_BYTES = 5_000_000


def download_verdacht(content_type: str, disposition: str = "") -> str:
    """Leer = in Ordnung. Sonst der Grund, warum das ein Download waere."""
    if _ANHANG.search(disposition or ""):
        return "Die Seite bietet das als Datei zum Herunterladen an"
    typ = (content_type or "text/html").split(";")[0].strip().lower()
    if not typ.startswith(ERLAUBTE_TYPEN):
        return f"Das ist keine Textseite, sondern {typ}"
    return ""


# --- 2. JavaScript ----------------------------------------------------------
# Bibliotheken, die Seiten ausfuehren statt nur zu lesen. Keine davon gehoert
# in dieses Programm; verbotstest.py prueft das.
BROWSER_MODULE = ("selenium", "playwright", "pyppeteer", "splash", "js2py",
                  "dukpy", "pyexecjs", "quickjs", "requests_html", "webdriver")

_SKRIPT = re.compile(r"(?is)<script[^>]*>.*?</script>")
_SKRIPT_OFFEN = re.compile(r"(?is)<script[^>]*>.*")     # unfertiges Fragment
_HANDLER = re.compile(r"(?is)\son[a-z]+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)")
_JS_URL = re.compile(r"(?is)(href|src)\s*=\s*([\"']?)\s*javascript:[^\"'>\s]*")


def javascript_entfernen(html: str) -> str:
    """Nimmt jeden ausfuehrbaren Teil aus dem Quelltext.

    Ausgefuehrt wird hier ohnehin nichts - es gibt keine Engine. Das hier ist
    die zweite Sperre: so kann auch kein Skript-Inhalt als vermeintlicher
    Seitentext beim Modell landen und dort als Anweisung gelesen werden.
    """
    ohne = _SKRIPT.sub(" ", html)
    ohne = _SKRIPT_OFFEN.sub(" ", ohne)
    ohne = _HANDLER.sub(" ", ohne)
    return _JS_URL.sub(r"\1=\2", ohne)


# --- 3. Terminal ------------------------------------------------------------
# Kurznamen, hinter denen eine Eingabeaufforderung steckt. Sie fuehren keinen
# Befehl aus - aber sie stellen dem Modell eine Tuer hin, und die soll nicht
# ohne Rueckfrage aufgehen.
SHELL_NAMEN = {"terminal", "wt", "windows terminal", "cmd", "eingabeaufforderung",
               "powershell", "pwsh", "konsole", "shell", "bash"}


def ist_shell(name: str) -> bool:
    return name.strip().lower() in SHELL_NAMEN


# --- Der Umweg ueber geschriebenen Code -------------------------------------
# Gemessen: auf "schreib mir ein Skript, das eine Datei herunterlaedt" hat das
# Modell genau das getan - obwohl es im Prompt verboten steht. Ein Prompt ist
# eine Bitte. Hier steht die Sperre.
_CODE_DOWNLOAD = re.compile(
    r"(?is)\b(?:"
    r"urlretrieve|wget\b|curl\s+-[a-zA-Z]*[oO]|Invoke-WebRequest|"
    r"DownloadFile|DownloadString|WebClient|"
    r"(?:requests|httpx|urllib\.request)\.[a-z]+\([^)]*\)[^\n]{0,80}"
    r"\.(?:content|raw|iter_content|iter_bytes)"
    r")")
# Das Muster oben faengt den direkten Weg. Das hier den zusammengesetzten:
# erst holen, dann in eine Datei schreiben - oft ueber mehrere Zeilen.
_HOLT = re.compile(r"(?is)\b(requests|httpx|urllib|aiohttp)\b")
_SCHREIBT_BINAER = re.compile(r"(?is)open\s*\([^)]*[\"'][awx]b[\"']")
_NACHLADEN = re.compile(
    r"(?is)\b(?:exec|eval)\s*\(\s*(?:requests|httpx|urllib|r\.text|"
    r"response\.text|antwort\.text)"
    r"|pip\s+install|subprocess[^\n]{0,60}pip\b")


def code_verstoss(code: str) -> str:
    """Leer = in Ordnung. Sonst der Grund, warum dieser Code nicht entsteht."""
    if _CODE_DOWNLOAD.search(code):
        return "er laedt Dateien aus dem Netz herunter"
    if _HOLT.search(code) and _SCHREIBT_BINAER.search(code):
        return "er holt etwas aus dem Netz und schreibt es auf die Platte"
    if _NACHLADEN.search(code):
        return "er fuehrt nach oder installiert zur Laufzeit nach"
    return ""


# Schon die Aufgabe kann eindeutig sein - dann wird gar nicht erst gefragt
# "herunterladen", "herunterlaedt", "herunterlädt", "laedt ... herunter" -
# derselbe Wunsch in vier Schreibweisen. Der Stamm allein reicht nicht: nach
# "herunterla" folgt mal ein d, mal ein e, mal ein Umlaut.
_AUFGABE_DOWNLOAD = re.compile(
    r"(?is)\b(?:"
    r"(?:herunter|runter)(?:zu)?l(?:ad|äd|aed)\w*"
    r"|l(?:äd|aed|ad)\w*[^.\n]{0,40}\bherunter\b"
    r"|download\w*|downloade\w*"
    # Das Modell schreibt die Aufgabe fuer write_code gern auf Englisch um -
    # gemessen: "Scrape the URL ... and save its HTML content to a file".
    # Nur deutsche Wortstaemme zu pruefen liesse genau das durch.
    r"|scrap(?:e|es|ing)\b"
    r")")

# Diese Wendungen sind fuer sich harmlos - "speichert die Datei" macht jedes
# zweite Skript. Gefaehrlich werden sie erst zusammen mit einem Netzbezug.
# Ohne diese Trennung waere "erzeuge ein Diagramm und speichere das Bild"
# abgelehnt worden, und ein Fehlalarm kostet eine berechtigte Antwort.
_SPEICHERN = re.compile(
    r"(?is)\b(?:speicher\w*|abruft und speichert|"
    r"(?:save|store|writes?)\s+(?:it|its|the)?\s*\w{0,12}\s*"
    r"(?:content|html|page|response|file|image|video|data)\b|"
    r"fetch\w*|(?:get|grab|retrieve|pull)s?\b)")
_NETZBEZUG = re.compile(
    r"(?is)\b(?:url|uri|https?://|internet|netz\b|web\b|webseite|website|"
    r"seite\s+im\s+netz|link\b|online\b|server\b|api\b(?=[^.\n]{0,30}"
    # "page" heisst im Englischen praktisch immer Webseite. Das deutsche
    # "Seite" nicht - "speichere Seite 3" waere sonst ein Fehlalarm.
    r"\bdatei)|remote\b|page\b)")
_AUFGABE_SHELL = re.compile(
    r"(?is)\b(shell=True|eingabeaufforderung|beliebige befehle|"
    r"befehl ausf(ue|ü)hr\w*)")


def aufgabe_verstoss(aufgabe: str) -> str:
    """Leer = in Ordnung. Sonst der Grund, warum daraus kein Code wird."""
    if _AUFGABE_DOWNLOAD.search(aufgabe):
        return "Dateien aus dem Netz herunterladen"
    # Speichern allein ist harmlos, Netzbezug allein auch. Beides zusammen in
    # einem Satz ist ein Download, egal wie es formuliert ist.
    if _SPEICHERN.search(aufgabe) and _NETZBEZUG.search(aufgabe):
        return "etwas aus dem Netz holen und auf die Platte schreiben"
    if _AUFGABE_SHELL.search(aufgabe):
        return "beliebige Systembefehle ausfuehren"
    return ""
