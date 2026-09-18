"""Prueft die Slash-Befehle und die Vorschlagsanzeige - ohne API, ohne Kosten."""
import io
from contextlib import redirect_stdout

from jarvis import commands
from jarvis.prompt import LineEditor

editor = LineEditor(commands.namen_mit_hilfe())

print("=== Vorschlaege beim Tippen ===")
for eingabe in ["/", "/h", "/st", "/stu", "/w", "/xyz", "hallo"]:
    treffer = editor._treffer(eingabe)
    print(f"  {eingabe:<8} -> {treffer or '(keine)'}")

print("\n=== Tab-Vervollstaendigung ===")
for eingabe in ["/h", "/st", "/na"]:
    treffer = editor._treffer(eingabe)
    ergaenzt = editor._gemeinsamer_anfang(treffer)
    print(f"  {eingabe:<6} + Tab -> {ergaenzt!r}"
          f"{'  (eindeutig)' if len(treffer) == 1 else ''}")

print("\n=== So sieht die Zeile im Terminal aus ===")
puffer = io.StringIO()
with redirect_stdout(puffer):
    editor._zeichne("DU: ", "/st")
sichtbar = puffer.getvalue().replace("\x1b", "<ESC>")
print(f"  Rohausgabe: {sichtbar[:120]}...")


class FakeSpeaker:
    enabled = True


class FakeBrain:
    history = []
    model = "moonshotai/kimi-k3"
    rangliste = ["moonshotai/kimi-k3"]
    ping = [
        {"modell": "moonshotai/kimi-k3", "zustand": "frei", "dauer": 1.2},
        {"modell": "openai/gpt-oss-20b", "zustand": "belegt", "dauer": 0.3},
    ]

    def reset(self):
        self.history.clear()

    def pingen(self):
        return self.ping


ctx = commands.Kontext(FakeBrain(), FakeSpeaker(), False)

print("\n=== Befehle ausfuehren ===")
for eingabe in ["/hilfe", "/hilfe /st", "/zeit", "/status", "/modell",
                "/wetter Koeln", "/gedaechtnis", "/öffne", "/stimme",
                "/s", "/quatsch", "/zei"]:
    ergebnis = commands.ausfuehren(eingabe, ctx)
    text = "BEENDEN" if ergebnis is commands.BEENDEN else str(ergebnis)
    kurz = text if len(text) < 200 else text[:200] + " ..."
    print(f"\n> {eingabe}\n{kurz}")

print("\n=== /ende ===")
print(commands.ausfuehren("/ende", ctx) is commands.BEENDEN)
