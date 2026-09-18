"""Die Weboberfläche: ein kleiner Server, der neben dem Terminal läuft.

Er bedient dieselben Bausteine wie die Terminalfassung - dasselbe Gehirn,
dieselben Werkzeuge, denselben Hangar. Es ist also keine zweite Jarvis-Fassung,
sondern ein zweites Fenster auf dieselbe.

Starten:  .venv\\Scripts\\python.exe -m jarvis.web
"""
from __future__ import annotations

import asyncio
import json
import queue
import threading
import time

from fastapi import FastAPI, Request
from fastapi.responses import (FileResponse, JSONResponse, PlainTextResponse,
                               StreamingResponse)

from . import commands, config, protokoll, tools, werkzeugliste
from .agenten import HANGAR
from .brain import Brain
from .voice import NullSpeaker, SentenceSpeaker

app = FastAPI(title="JARVIS")
OBERFLAECHE = config.ROOT / "oberflaeche"

_brain: Brain | None = None
_speaker = None
_schloss = threading.Lock()


def gehirn() -> Brain:
    global _brain, _speaker
    with _schloss:
        if _brain is None:
            _brain = Brain()
            _brain.pingen()
            protokoll.schreibe("modell", f"Gestartet mit {_brain.model}")
            # Hier wird nicht gesprochen: den Ton macht der Browser, sonst
            # hoerte man alles doppelt. Der stumme Platzhalter dient nur
            # dazu, die <en>-Markierungen aus dem Text zu nehmen.
            _speaker = NullSpeaker()
            # Der Wachhund schreibt ins Protokoll; die Oberflaeche holt die
            # Meldungen dort ab und liest sie bei Bedarf vor.
            from . import wachhund
            wachhund.starten(lambda satz: protokoll.schreibe("jarvis", satz))
    return _brain


def _weckwort_starten() -> None:
    """Am Rechner auf "Hey Jarvis" hoeren - unabhaengig vom Browser.

    Das Mikrofon des Browsers taugt dafuer nicht: ueber http:// gibt es
    keines, und ueber HTTPS waere es das des Handys. Gehoert wird hier.
    """
    from . import ohr

    lief, grund = ohr.starten(gehirn)
    if not lief and grund:
        print(f"[Weckwort] {grund}")


# --- Oberflaeche ------------------------------------------------------------
# Der Browser darf diese vier Dateien behalten, muss aber jedes Mal
# nachfragen, ob sie noch aktuell sind. Ohne das behaelt er sie nach eigenem
# Gutduenken - und dann kam die neue Oberflaeche mit dem alten Stylesheet
# heraus: die Chatliste stand unformatiert und halb abgeschnitten in der
# Ecke. "Druecken Sie Strg+F5" ist keine Loesung, sondern eine Ausrede.
# FileResponse schickt ohnehin ein ETag mit, also kostet das Nachfragen
# nichts ausser einem 304.
_OHNE_CACHE = {"Cache-Control": "no-cache"}


@app.get("/")
async def startseite():
    return FileResponse(OBERFLAECHE / "index.html", headers=_OHNE_CACHE)


@app.get("/stil.css")
async def stil():
    return FileResponse(OBERFLAECHE / "stil.css", headers=_OHNE_CACHE)


@app.get("/jarvis.js")
async def skript():
    return FileResponse(OBERFLAECHE / "jarvis.js", headers=_OHNE_CACHE)


@app.get("/stimme.js")
async def stimmskript():
    return FileResponse(OBERFLAECHE / "stimme.js", headers=_OHNE_CACHE)


# --- Gespraech --------------------------------------------------------------
# Befehle, die ein Terminalfenster brauchen und im Browser nichts Sinnvolles
# tun koennen. Sie werden erklaert statt stillschweigend ignoriert.
_NUR_TERMINAL = {
    "/ende": "Das beendet Jarvis - das geht nur im Terminalfenster. "
             "Im Browser kannst du das Fenster einfach schliessen.",
}


def _befehl_ausfuehren(text: str, brain) -> dict:
    """Einen Slash-Befehl ausfuehren und die Antwort fuer den Browser packen.

    "leeren" sagt der Oberflaeche, dass sie den Bildschirm raeumen soll -
    os.system("cls") waere hier sinnlos, das leert die Konsole des Servers.
    """
    name = text.strip().split(" ")[0].lower()
    name = commands.ZWEITNAMEN.get(name, name)
    if name in _NUR_TERMINAL:
        antwort = _NUR_TERMINAL[name]
        protokoll.schreibe("system", antwort)
        return {"befehl": name, "text": antwort}

    ctx = commands.Kontext(brain, _speaker, sprachmodus=False)
    try:
        ergebnis = commands.ausfuehren(text, ctx)
    except Exception as exc:
        protokoll.schreibe("fehler", f"{name}: {type(exc).__name__}: {exc}")
        return {"befehl": name,
                "text": f"Der Befehl ist gescheitert: {type(exc).__name__}"}

    if ergebnis is commands.BEENDEN:
        return {"befehl": name, "text": _NUR_TERMINAL["/ende"]}

    antwort = (ergebnis or "").strip() if isinstance(ergebnis, str) else ""
    if antwort:
        protokoll.schreibe("system", antwort)
    return {"befehl": name, "text": antwort,
            # Die Oberflaeche muss danach etwas tun: Bildschirm raeumen und
            # die Chatliste neu holen.
            "leeren": name in ("/leeren", "/neu"),
            "chats_neu": name in ("/neu", "/chats")}


def _fehlersatz(exc: Exception) -> str:
    """Ein Satz, mit dem ein Mensch etwas anfangen kann.

    Gemeldet aus dem Betrieb: auf "seit wann ist Nuristan ein Land?" stand
    im Fenster "FEHLER list index out of range". Das ist der Wortlaut einer
    Python-Ausnahme aus der OpenAI-Bibliothek - fuer den Menschen davor
    voellig ohne Aussage, und es sieht aus, als waere seine Frage schuld.
    War sie nicht: dieselbe Frage ging gleich danach durch.
    Der technische Wortlaut bleibt im Protokoll, wo er hingehoert.
    """
    from .brain import _voruebergehend

    text = str(exc)
    if _voruebergehend(exc):
        return ("Der Anbieter hat gerade eine unbrauchbare Antwort "
                "geschickt. Das liegt nicht an deiner Frage - stell sie "
                "einfach noch einmal.")
    if "429" in text or "Too Many Requests" in text:
        return ("Alle Modelle sind gerade belegt. In ein paar Minuten "
                "noch einmal versuchen.")
    if "API_KEY" in text or "401" in text or "Unauthorized" in text:
        return ("Der Zugang wurde abgelehnt - vermutlich stimmt der "
                "Schluessel in der .env nicht mehr.")
    # Unbekannt: dann lieber den Wortlaut zeigen als etwas zu erfinden.
    return f"{type(exc).__name__}: {text}"


@app.post("/api/chat")
async def chat(request: Request):
    daten = await request.json()
    text = (daten.get("text") or "").strip()
    if not text:
        return JSONResponse({"fehler": "Keine Eingabe"}, status_code=400)

    # Die Oberflaeche sagt dazu, ob sie die Antwort gleich vorliest. Im
    # Textmodus tut sie das erst auf Knopfdruck - dann darf die Antwort so
    # lang sein, wie die Sache es braucht, und Markdown benutzen. Fehlt die
    # Angabe (alte Oberflaeche, fremder Aufruf), gilt "getippt": ein zu
    # knapper Text faellt weniger auf als eine vorgelesene Aufzaehlung.
    gesprochen = bool(daten.get("gesprochen"))

    brain = gehirn()
    protokoll.schreibe("du", text)

    # Slash-Befehle laufen hier genauso wie im Terminalfenster. Vorher gingen
    # sie im Browser ans Modell - und das erfand daraufhin eine komplette
    # Befehlsliste mit /time, /weather und /clear, die es nie gegeben hat.
    # Gemessen im echten Gebrauch: auf "/clear" antwortete es "Konversation
    # geloescht, Sir." und loeschte nichts.
    if commands.ist_befehl(text):
        return JSONResponse(_befehl_ausfuehren(text, brain))

    haeppchen: queue.Queue = queue.Queue()

    def arbeiten() -> None:
        saetze = SentenceSpeaker(_speaker)
        gesamt = []

        def status(was: str) -> None:
            haeppchen.put({"typ": "status", "wert": was})

        # vorlesen() schickt fremden Nachrichtentext hierhin - an der
        # Antwort vorbei, damit er nicht im Kontext des Modells landet. Im
        # Browser wird er gesprochen, im Verlauf steht er nicht.
        def vorlesen(satz: str) -> None:
            haeppchen.put({"typ": "sprich", "wert": satz})

        # Derselbe Weg, anderer Ausgang: fremder Text erscheint im Fenster,
        # ohne durch das Modell gegangen zu sein. "Als Text" war vorher eine
        # Absage - dabei ist Lesen gegen einen Einschleusversuch sogar
        # sicherer als Hoeren, weil man sieht, wo der fremde Text anfaengt
        # und wo er aufhoert.
        def zeigen(stueck: dict) -> None:
            haeppchen.put({"typ": "fremdtext",
                           "kopf": str(stueck.get("kopf", ""))[:200],
                           "wert": str(stueck.get("text", ""))[:4000]})

        tools.setze_sprecher(vorlesen)
        tools.setze_zeiger(zeigen)
        def delta(stueck: str) -> None:
            sichtbar = saetze.feed(stueck)
            if sichtbar:
                gesamt.append(sichtbar)
                haeppchen.put({"typ": "text", "wert": sichtbar})

        # Der Gedankengang geht einen eigenen Weg: er wird angezeigt, aber
        # nie gesprochen und nie ins Archiv geschrieben. Frueher landete er
        # mitten in der Antwort ("We need answer: how many testosterone
        # derivatives...").
        def denken(stueck: str) -> None:
            haeppchen.put({"typ": "denken", "wert": stueck})

        try:
            brain.ask(text, on_status=status, on_delta=delta,
                      on_denken=denken, gesprochen=gesprochen)
            saetze.flush()
            antwort = "".join(gesamt).strip()
            protokoll.schreibe("jarvis", antwort or "(nichts)")
            haeppchen.put({"typ": "fertig", "modell": brain.model})
        except Exception as exc:
            protokoll.schreibe("fehler", f"{type(exc).__name__}: {exc}")
            haeppchen.put({"typ": "fehler", "wert": _fehlersatz(exc)})
        finally:
            haeppchen.put(None)

    threading.Thread(target=arbeiten, daemon=True).start()

    async def strom():
        while True:
            try:
                stueck = haeppchen.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.03)
                continue
            if stueck is None:
                break
            yield f"data: {json.dumps(stueck, ensure_ascii=False)}\n\n"

    return StreamingResponse(strom(), media_type="text/event-stream")


@app.post("/api/abbruch")
async def abbruch():
    if _brain is not None:
        _brain.abbrechen()
    if _speaker is not None:
        _speaker.verstummen()
    protokoll.schreibe("system", "Abgebrochen")
    return {"ok": True}


@app.get("/api/verlauf")
async def verlauf_lesen(anzahl: int = 30, chat: str = ""):
    """Was zuletzt gesagt wurde - damit die Seite nicht leer startet.

    Jarvis erinnert sich ueber Neustarts hinweg; die Oberflaeche tat es
    nicht. Am Handy sah man ein leeres Fenster und bekam Antworten auf ein
    Gespraech, das man nicht sehen konnte.
    """
    from . import chats, verlauf

    aktive_kennung = chat or chats.aktiver(anlegen=False)
    eintraege = verlauf.letzte(anzahl, chat=aktive_kennung) if aktive_kennung else []
    return {"eintraege": eintraege, "chat": aktive_kennung}


@app.post("/api/reset")
async def reset():
    gehirn().reset()
    protokoll.schreibe("system", "Verlauf geleert")
    return {"ok": True}


@app.get("/api/sprache")
async def sprache_zustand():
    """Was geht hier gerade mit Sprache - und was nicht?

    Die Oberflaeche hat die Sprachmodi bisher angeboten, ohne zu wissen, ob
    sie ueberhaupt funktionieren koennen. Auf dem Handy ueber http:// koennen
    sie es nicht, und "Freies Sprechen" sah dann genauso aus wie "Stimme",
    weil beide nichts taten.
    """
    from . import ohr

    lage = ohr.zustand()
    return {
        "weckwort": lage,
        "mikrofone": ohr.mikrofone(),
        # Das Weckwort haengt am Mikrofon DIESES Rechners, der Browsermodus
        # am Mikrofon des Geraets, auf dem die Seite offen ist. Zwei
        # verschiedene Dinge, die im Fenster leicht durcheinandergehen.
        "hinweis": ("Das Weckwort hört am Rechner mit, auf dem Jarvis läuft - "
                    "unabhängig davon, wo diese Seite offen ist."),
    }


# --- Chats ------------------------------------------------------------------
async def _json(request: Request) -> dict:
    """Rumpf lesen, ohne an einem leeren Aufruf zu zerbrechen.

    "Neuer Chat" schickt keinen Inhalt mit - request.json() wirft dann, und
    der Knopf tut nichts, ohne dass irgendwo etwas stuende.
    """
    try:
        daten = await request.json()
    except Exception:
        return {}
    return daten if isinstance(daten, dict) else {}


@app.get("/api/chats")
async def chats_lesen():
    from . import chats

    return {"chats": chats.liste(), "aktiv": chats.aktiver(anlegen=False)}


@app.post("/api/chats")
async def chat_anlegen(request: Request):
    """Neuer Chat - leerer Bildschirm, leeres Gedaechtnis, altes bleibt."""
    from . import chats

    daten = await _json(request)
    kennung = chats.neu((daten.get("titel") or "").strip())
    gehirn().reset()
    protokoll.schreibe("system", f"Neuer Chat {kennung}")
    return {"ok": True, "id": kennung}


@app.post("/api/chats/wechseln")
async def chat_wechseln(request: Request):
    from . import chats

    daten = await _json(request)
    kennung = (daten.get("id") or "").strip()
    if not chats.wechseln(kennung):
        return JSONResponse({"fehler": "unbekannter Chat"}, status_code=404)
    anzahl = gehirn().chat_oeffnen(kennung)
    return {"ok": True, "id": kennung, "nachrichten": anzahl}


@app.post("/api/chats/umbenennen")
async def chat_umbenennen(request: Request):
    from . import chats

    daten = await _json(request)
    kennung = (daten.get("id") or "").strip()
    titel = (daten.get("titel") or "").strip()
    if not titel:
        return JSONResponse({"fehler": "kein Titel"}, status_code=400)
    if not chats.umbenennen(kennung, titel):
        return JSONResponse({"fehler": "unbekannter Chat"}, status_code=404)
    return {"ok": True}


@app.post("/api/chats/loeschen")
async def chat_loeschen(request: Request):
    """Weg heisst weg - Nachrichten inbegriffen.

    Das ist der Punkt, an dem "Verlauf loeschen" endlich das tut, was es
    sagt: vorher war nur Jarvis' Arbeitsgedaechtnis leer, und beim naechsten
    Laden stand alles wieder da.
    """
    from . import chats

    daten = await _json(request)
    kennung = (daten.get("id") or "").strip()
    war_aktiv = kennung == chats.aktiver(anlegen=False)
    weg = chats.loeschen(kennung)
    neuer_aktiver = chats.aktiver(anlegen=False)
    if war_aktiv:
        if neuer_aktiver:
            gehirn().chat_oeffnen(neuer_aktiver)
        else:
            gehirn().reset()
    protokoll.schreibe("system", f"Chat {kennung} geloescht ({weg} Nachrichten)")
    return {"ok": True, "geloescht": weg, "aktiv": neuer_aktiver}


# --- Stimme und Ohren fuer den Browser --------------------------------------
@app.post("/api/stimme")
async def stimme(request: Request):
    """Text als WAV. Der Browser spielt ihn ab und misst dabei die
    Frequenzen - daher kommen die Ausschlaege der drei Striche."""
    from .voice import zu_wav

    daten = await request.json()
    text = (daten.get("text") or "").strip()
    if not text:
        return JSONResponse({"fehler": "kein Text"}, status_code=400)
    try:
        ton = await asyncio.to_thread(zu_wav, text)
    except Exception as exc:
        protokoll.schreibe("fehler", f"Stimme: {exc}")
        return JSONResponse({"fehler": str(exc)}, status_code=500)
    if not ton:
        return JSONResponse({"fehler": "nichts zu sprechen"}, status_code=400)
    from fastapi.responses import Response
    return Response(content=ton, media_type="audio/wav")


@app.post("/api/hoeren")
async def hoeren(request: Request):
    """Eine Aufnahme aus dem Browser wird hier zu Text - lokal, ohne Dienst."""
    from .voice import verstehen

    audio = await request.body()
    if len(audio) < 1200:
        return {"text": ""}
    try:
        text = await asyncio.to_thread(verstehen, audio)
    except Exception as exc:
        protokoll.schreibe("fehler", f"Spracherkennung: {exc}")
        return JSONResponse({"fehler": str(exc)}, status_code=500)
    protokoll.schreibe("system", f"Gehört: {text[:60] or '(nichts)'}")
    return {"text": text}


@app.post("/api/bild")
async def bild(request: Request):
    """Ein eingefuegtes Bild wird beschrieben - wie ein Bildschirmfoto."""
    daten = await request.json()
    bild_uri = daten.get("bild") or ""
    frage = (daten.get("frage") or "").strip() or (
        "Beschreibe knapp, was auf diesem Bild zu sehen ist. "
        "Antworte auf Deutsch.")
    if not bild_uri.startswith("data:image/"):
        return JSONResponse({"fehler": "kein Bild"}, status_code=400)
    try:
        text = await asyncio.to_thread(tools._bild_befragen, bild_uri, frage)
    except Exception as exc:
        return JSONResponse({"fehler": str(exc)}, status_code=500)
    protokoll.schreibe("werkzeug", f"Bild angesehen: {text[:60]}")
    return {"beschreibung": text}


# --- Modelle ----------------------------------------------------------------
@app.get("/api/modelle")
async def modelle():
    brain = gehirn()
    return {"laeuft": brain.model, "ping": brain.ping,
            "rangliste": brain.rangliste, "wahl": config.MODELL_WAHL,
            "kandidaten": config.MODELS}


@app.post("/api/modelle/pingen")
async def modelle_pingen():
    brain = gehirn()
    brain.pingen()
    protokoll.schreibe("modell", f"Neu gepingt, laeuft mit {brain.model}")
    return {"laeuft": brain.model, "ping": brain.ping}


@app.post("/api/modelle/waehlen")
async def modell_waehlen(request: Request):
    daten = await request.json()
    name = (daten.get("name") or "").strip()
    brain = gehirn()
    brain.model = name
    if name not in brain.rangliste:
        brain.rangliste = [name] + brain.rangliste
    protokoll.schreibe("modell", f"Von Hand gewechselt auf {name}")
    return {"laeuft": brain.model}


# --- Agenten ----------------------------------------------------------------
@app.get("/api/agenten")
async def agenten():
    liste = [{
        "name": a.name, "aufgabe": a.aufgabe, "zustand": a.zustand,
        "dauer": round(a.dauer), "zeichen": a.verlauf_zeichen,
        "bericht": a.bericht, "grund": a.grund, "laeuft": a.laeuft,
    } for a in HANGAR.agenten.values()]
    return {"agenten": liste, "grenze": HANGAR.grenze,
            "laufend": len(HANGAR.laufende()),
            "prozess_mb": round(HANGAR._prozess_mb()),
            "zeitlimit": config.AGENT_ZEITLIMIT}


@app.post("/api/agenten")
async def agent_starten(request: Request):
    daten = await request.json()
    aufgabe = (daten.get("aufgabe") or "").strip()
    agent, meldung = HANGAR.starten(aufgabe)
    protokoll.schreibe("agent", meldung)
    return {"ok": agent is not None, "meldung": meldung}


@app.delete("/api/agenten/{name}")
async def agent_stoppen(name: str):
    agent = HANGAR.agenten.get(name)
    if agent is None:
        return JSONResponse({"fehler": "unbekannt"}, status_code=404)
    agent.stoppen()
    HANGAR.entfernen(name)
    protokoll.schreibe("agent", f"{name} angehalten")
    return {"ok": True}


@app.get("/api/agenten/{name}/bericht")
async def agent_bericht(name: str):
    bericht = HANGAR.abholen(name)
    protokoll.schreibe("agent", f"Bericht von {name} abgeholt")
    return {"bericht": bericht}


# --- Werkzeuge --------------------------------------------------------------
@app.get("/api/werkzeuge")
async def werkzeuge():
    return {"werkzeuge": werkzeugliste.uebersicht(tools.GRUNDSCHEMA),
            "aktiv": len(tools.schema()),
            "gesamt": len(tools.GRUNDSCHEMA)}


@app.put("/api/werkzeuge")
async def werkzeuge_speichern(request: Request):
    daten = await request.json()
    werkzeugliste.speichern(daten.get("aenderungen") or {})
    protokoll.schreibe("system", "Werkzeuge geändert")
    return {"ok": True, "aktiv": len(tools.schema())}


@app.post("/api/werkzeuge/zuruecksetzen")
async def werkzeuge_zuruecksetzen(request: Request):
    daten = await request.json()
    werkzeugliste.zuruecksetzen(daten.get("name", ""))
    return {"ok": True}


# --- Einstellungen ----------------------------------------------------------
def _ist_geheim(schluessel: str) -> bool:
    """Muss der Wert in der Oberflaeche verdeckt werden?

    Nur nach "KEY" zu suchen reichte nicht: JARVIS_MAIL_PASSWORT haette im
    Klartext dagestanden - und die Oberflaeche ist aus dem ganzen Tailnet
    erreichbar. Umgekehrt sind MAX_TOKENS und CODE_TOKENS blosse Zahlen und
    duerfen nicht verdeckt werden, sonst kann man sie nicht mehr einstellen.
    """
    gross = schluessel.upper()
    if gross.endswith("TOKENS"):          # Anzahl, kein Zugangsschluessel
        return False
    return any(w in gross for w in
               ("KEY", "PASSWORT", "PASSWORD", "TOKEN", "SECRET", "GEHEIM"))


def _env_lesen() -> list[dict]:
    """Die .env als Liste - Kommentare werden als Erklaerung mitgenommen."""
    pfad = config.ROOT / ".env"
    if not pfad.exists():
        return []
    eintraege, erklaerung = [], []
    for zeile in pfad.read_text(encoding="utf-8").splitlines():
        roh = zeile.strip()
        if roh.startswith("#"):
            text = roh.lstrip("#").strip()
            if text and not set(text) <= set("-= "):
                erklaerung.append(text)
            continue
        if not roh or "=" not in roh:
            erklaerung = []
            continue
        schluessel, _, wert = roh.partition("=")
        eintraege.append({
            "schluessel": schluessel.strip(),
            "wert": wert.strip(),
            "erklaerung": " ".join(erklaerung),
            "geheim": _ist_geheim(schluessel),
        })
        erklaerung = []
    return eintraege


@app.get("/api/einstellungen")
async def einstellungen():
    return {"eintraege": _env_lesen()}


@app.put("/api/einstellungen")
async def einstellungen_speichern(request: Request):
    daten = await request.json()
    neu = {e["schluessel"]: e["wert"] for e in (daten.get("eintraege") or [])}
    pfad = config.ROOT / ".env"
    zeilen = []
    for zeile in pfad.read_text(encoding="utf-8").splitlines():
        roh = zeile.strip()
        if roh and not roh.startswith("#") and "=" in roh:
            schluessel = roh.split("=", 1)[0].strip()
            if schluessel in neu:
                zeilen.append(f"{schluessel}={neu.pop(schluessel)}")
                continue
        zeilen.append(zeile)
    for schluessel, wert in neu.items():        # neu hinzugekommene
        zeilen.append(f"{schluessel}={wert}")
    pfad.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    protokoll.schreibe("system", "Einstellungen gespeichert - "
                                 "wirksam nach einem Neustart")
    return {"ok": True, "hinweis": "Die meisten Werte greifen erst nach einem "
                                   "Neustart von Jarvis."}


# --- Rückfragen -------------------------------------------------------------
@app.get("/api/rueckfragen")
async def rueckfragen():
    from . import rueckfrage

    return {"fragen": [f.als_dict() for f in rueckfrage.offene()]}


@app.post("/api/rueckfragen")
async def rueckfrage_beantworten(request: Request):
    from . import rueckfrage

    daten = await request.json()
    ok = rueckfrage.beantworten(daten.get("id", ""), daten.get("antwort", ""))
    if ok:
        protokoll.schreibe("du", f"Antwort: {daten.get('antwort')}")
    return {"ok": ok}


# --- Wachhund ---------------------------------------------------------------
@app.get("/api/wachhund")
async def wachhund_lesen():
    from . import wachhund

    hund = wachhund.WACHHUND
    if hund is None:
        gehirn()
        hund = wachhund.WACHHUND
    return {"regeln": hund.uebersicht() if hund else [],
            "an": config.WACH_AN,
            "werte": {
                "pause": config.WACH_PAUSE,
                "anwesend": config.WACH_ANWESEND,
                "ruhe_von": config.WACH_RUHE_VON,
                "ruhe_bis": config.WACH_RUHE_BIS,
                "ram_prozent": config.WACH_RAM_PROZENT,
                "platte_gb": config.WACH_PLATTE_GB,
                "last_dauer": config.WACH_LAST_DAUER,
                "laufzeit_tage": config.WACH_LAUFZEIT_TAGE,
            }}


@app.post("/api/wachhund")
async def wachhund_schalten(request: Request):
    from . import wachhund

    daten = await request.json()
    hund = wachhund.WACHHUND
    if hund is None:
        return JSONResponse({"fehler": "läuft nicht"}, status_code=400)
    if "name" in daten:
        hund.umschalten(daten["name"], bool(daten.get("aktiv")))
        if "sperrzeit" in daten:
            for r in hund.regeln:
                if r.name == daten["name"]:
                    r.sperrzeit = max(0.0, float(daten["sperrzeit"]))
        protokoll.schreibe("system",
                           f"Wachhund-Regel '{daten['name']}' "
                           f"{'an' if daten.get('aktiv') else 'aus'}")

    # Die allgemeinen Grenzen - sofort wirksam, ohne Neustart
    for schluessel, ziel in (("pause", "WACH_PAUSE"),
                             ("anwesend", "WACH_ANWESEND"),
                             ("ruhe_von", "WACH_RUHE_VON"),
                             ("ruhe_bis", "WACH_RUHE_BIS"),
                             ("ram_prozent", "WACH_RAM_PROZENT"),
                             ("platte_gb", "WACH_PLATTE_GB"),
                             ("last_dauer", "WACH_LAST_DAUER"),
                             ("laufzeit_tage", "WACH_LAUFZEIT_TAGE")):
        if schluessel in daten:
            typ = int if schluessel.startswith(("ruhe", "laufzeit")) else float
            setattr(config, ziel, typ(daten[schluessel]))
            protokoll.schreibe("system", f"{ziel} = {daten[schluessel]}")
    return {"regeln": hund.uebersicht()}


# --- Protokoll --------------------------------------------------------------
@app.get("/api/protokoll")
async def protokoll_lesen(ab: int = 0):
    return {"eintraege": protokoll.alle(ab), "letzte": protokoll.letzte_nummer()}


@app.delete("/api/protokoll")
async def protokoll_leeren():
    return {"geloescht": protokoll.leeren()}


# --- Zustand fuer die Kopfzeile ---------------------------------------------
@app.get("/api/zustand")
async def zustand():
    brain = _brain
    return {
        "modell": brain.model if brain else "-",
        "verlauf": len(brain.history) if brain else 0,
        "agenten": len(HANGAR.laufende()),
        "grenze": HANGAR.grenze,
        "werkzeuge": len(tools.schema()),
        "prozess_mb": round(HANGAR._prozess_mb()),
        "protokoll": protokoll.letzte_nummer(),
    }


def _kurzname_gesetzt() -> bool:
    """Steht "jarvis" in der hosts-Datei? Dann darf die schoene Adresse
    angezeigt werden."""
    import socket

    try:
        return socket.gethostbyname(config.WEB_NAME).startswith("127.")
    except OSError:
        return False


# --- Wer darf überhaupt anklopfen? ------------------------------------------
# Über diese Oberfläche lassen sich Lautstärke, Helligkeit und Programme
# steuern. Wer sie erreicht, steuert den Rechner - deshalb reicht es nicht,
# einfach auf allen Netzwerkkarten zu lauschen. Erlaubt sind dieser Rechner
# selbst und Geräte im eigenen Tailnet; das WLAN, in dem der Rechner gerade
# steht, ausdrücklich nicht.
def _erlaubte_netze() -> list:
    import ipaddress

    netze = [ipaddress.ip_network("127.0.0.0/8"),
             ipaddress.ip_network("::1/128")]
    if config.WEB_ZUGANG == "auto":
        netze += [ipaddress.ip_network(b) for b in config.TAILNET_BEREICHE]
    return netze


def tailnet_adresse() -> str:
    """Die eigene Tailscale-Adresse, oder leer wenn es keine gibt."""
    import ipaddress
    import socket

    bereiche = [ipaddress.ip_network(b) for b in config.TAILNET_BEREICHE]
    try:
        for eintrag in socket.getaddrinfo(socket.gethostname(), None):
            roh = eintrag[4][0]
            try:
                adresse = ipaddress.ip_address(roh)
            except ValueError:
                continue
            if any(adresse in netz for netz in bereiche):
                return str(adresse)
    except Exception:
        pass
    return ""


# Was der Browser auf dieser Seite ueberhaupt tun darf. Der Sinn: Jarvis darf
# jetzt Bilder von fremden Seiten anzeigen - Skripte von dort aber unter
# keinen Umstaenden. "script-src 'self'" setzt das JavaScript-Verbot im
# Browser selbst durch, nicht nur in unserem Quelltext.
#
# 'unsafe-inline' bei style-src ist noetig, weil in index.html style="..."
# steht. Bei Skripten ist es NICHT erlaubt - und genau darauf kommt es an.
# data: bei img-src und media-src: eingefuegte Bilder und aufgenommener Ton
# kommen als data:-Adresse aus dem Browser selbst.
_RICHTLINIE = "; ".join([
    "default-src 'self'",
    "img-src 'self' https: data: blob:",
    "media-src 'self' data: blob:",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "connect-src 'self'",
    "font-src 'self'",
    "object-src 'none'",
    "frame-ancestors 'none'",
    "base-uri 'none'",
    "form-action 'none'",
])


@app.middleware("http")
async def schutzkoepfe(request: Request, call_next):
    antwort = await call_next(request)
    antwort.headers["Content-Security-Policy"] = _RICHTLINIE
    antwort.headers["X-Content-Type-Options"] = "nosniff"
    antwort.headers["Referrer-Policy"] = "no-referrer"
    return antwort


@app.middleware("http")
async def nur_erlaubte_netze(request: Request, call_next):
    import ipaddress

    if config.WEB_ZUGANG == "offen":
        return await call_next(request)
    herkunft = request.client.host if request.client else ""
    try:
        adresse = ipaddress.ip_address(herkunft)
    except ValueError:
        return PlainTextResponse("Kein Zugang.", status_code=403)
    if not any(adresse in netz for netz in _erlaubte_netze()):
        protokoll.schreibe("system", f"Zugriff abgewiesen von {herkunft}")
        return PlainTextResponse(
            "Diese Oberflaeche ist nur von diesem Rechner und aus dem eigenen "
            "Tailnet erreichbar.", status_code=403)
    return await call_next(request)


def _belegt(port: int, sekunden: float = 0.6) -> bool:
    """Antwortet auf diesem Port jemand?

    Geprueft wird durch VERBINDEN, nicht durch Binden. Das ist der
    Unterschied, an dem Jarvis sich selbst uebersehen hat: der laufende
    Server lauscht auf 0.0.0.0:80, und ein bind() auf 127.0.0.1:80 ist
    fuer Windows eine ANDERE Adresse. Es gelingt also - ohne
    SO_REUSEADDR und sogar mit SO_EXCLUSIVEADDRUSE.

    Die Folge war im Betrieb sichtbar: die Startdatei fragte "ist 80
    frei?", bekam "ja", und startete einen zweiten Server daneben. Danach
    landete jede Anfrage zufaellig bei einem von beiden - der Server war
    "mal an, mal aus", und dieselbe Adresse funktionierte mal und mal nicht.
    """
    import socket

    pruefer = socket.socket()
    pruefer.settimeout(sekunden)
    try:
        return pruefer.connect_ex(("127.0.0.1", port)) == 0
    except OSError:
        return False
    finally:
        pruefer.close()


def _freier_port(wunsch: int) -> int:
    """Ist der Wunschport belegt, weiche auf den Ausweichport aus.

    Port 80 ist schoen, weil der Browser dann keine Nummer verlangt - aber
    er kann jederzeit von anderer Software beansprucht werden. Dann laeuft
    Jarvis eben auf 8765 weiter, statt gar nicht zu starten.
    """
    import socket

    for kandidat in (wunsch, config.WEB_PORT_AUSWEICH):
        # Erst fragen, ob dort schon jemand antwortet - das findet auch den
        # eigenen Server, der auf allen Karten lauscht.
        if _belegt(kandidat):
            continue
        # Dann noch der Bindungstest: er findet den Fall, dass ein Programm
        # den Port haelt, ohne zu antworten.
        pruefer = socket.socket()
        try:
            pruefer.bind(("0.0.0.0", kandidat))
            return kandidat
        except OSError:
            continue
        finally:
            pruefer.close()
    return wunsch


def _ausgabe_umleiten() -> None:
    """Ohne Konsole ist sys.stdout None - und uvicorn stuerzt daran ab.

    Der Autostart benutzt pythonw.exe, damit kein schwarzes Fenster aufgeht.
    Dabei gibt es keine Standardausgabe. Uvicorn fragt beim Einrichten seiner
    Protokollierung sys.stdout.isatty() ab und bekommt ein AttributeError auf
    None - Jarvis startete also bei jedem Hochfahren gar nicht, ohne dass
    irgendwo etwas stand.

    Statt ins Leere zu schreiben geht die Ausgabe in eine Datei. Dann laesst
    sich nachsehen, warum er nicht hochkam.
    """
    import sys

    if sys.stdout is not None and sys.stderr is not None:
        return
    ziel = config.ROOT / "data" / "start.log"
    try:
        ziel.parent.mkdir(parents=True, exist_ok=True)
        # Nicht endlos wachsen lassen - niemand liest 200 MB Protokoll
        if ziel.exists() and ziel.stat().st_size > 1_000_000:
            ziel.unlink()
        datei = open(ziel, "a", encoding="utf-8", buffering=1)
    except Exception:
        import io

        datei = io.StringIO()          # lieber ins Leere als gar nicht starten
    if sys.stdout is None:
        sys.stdout = datei
    if sys.stderr is None:
        sys.stderr = datei


def start(host: str = "", port: "int | None" = None,
          taskleiste: bool = True) -> None:
    import os
    import signal

    _ausgabe_umleiten()                # muss VOR uvicorn passieren
    import uvicorn

    port = _freier_port(port or config.WEB_PORT)

    # Auf 127.0.0.1 zu lauschen hiesse: nur an diesem Rechner. Wer den PC aus
    # der Ferne bedient, kaeme gar nicht erst an. Also wird auf allen Karten
    # gelauscht - und die Zugangsschranke oben laesst nur den Rechner selbst
    # und das eigene Tailnet durch.
    if not host:
        host = "127.0.0.1" if config.WEB_ZUGANG == "lokal" else "0.0.0.0"

    name = config.WEB_NAME if _kurzname_gesetzt() else "127.0.0.1"
    nummer = "" if port == 80 else f":{port}"
    adresse = f"http://{name}{nummer}"
    print(f"\n  JARVIS-Oberflaeche: {adresse}")

    if config.WEB_ZUGANG != "lokal":
        fern = tailnet_adresse()
        if fern:
            print(f"  Aus der Ferne     : http://{fern}{nummer}")
            print(f"  (nur fuer Geraete im eigenen Tailnet - das WLAN kommt "
                  f"nicht durch)")
        else:
            print("  (kein Tailnet gefunden - nur von diesem Rechner "
                  "erreichbar)")
    print()
    protokoll.schreibe("system", "Weboberfläche gestartet")

    # Ein Symbol in der Taskleiste, sonst laeuft er unsichtbar und
    # unbeendbar im Hintergrund - besonders beim Autostart
    if taskleiste:
        from . import tray

        if tray.verfuegbar():
            tray.Tray(adresse,
                      beim_beenden=lambda: os.kill(os.getpid(), signal.SIGTERM)
                      ).starten_im_hintergrund()
        else:
            print("  (kein Symbol in der Taskleiste - pystray fehlt)")

    # Erst wenn der Server wirklich hochfaehrt - und in einem eigenen Faden,
    # weil das Laden des Weckwortmodells ein paar Sekunden dauert und die
    # Oberflaeche solange nicht warten soll.
    if config.WECKWORT_AN:
        threading.Thread(target=_weckwort_starten, daemon=True,
                         name="Weckwort-Start").start()
    else:
        print("  Weckwort: aus (JARVIS_WECKWORT_AN=1 in der .env schaltet es "
              "ein)")

    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    start()
