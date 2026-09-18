"""Prüft die <en>-Markierung: wird sie versteckt, steuert sie die Stimme,
und übersteht sie das zerstückelte Eintreffen beim Streamen?"""
from jarvis.voice import SentenceSpeaker


class MerkSpeaker:
    """Statt zu sprechen: aufschreiben, was mit welcher Sprache käme.
    Jeder Eintrag ist ein Satz, der aus mehreren Stücken bestehen kann."""
    enabled = True

    def __init__(self):
        self.saetze = []

    def say_teile(self, teile):
        self.saetze.append([(s, t.strip()) for t, s in teile])

    def say(self, text, sprache=None):
        self.say_teile([(text, sprache)])

    def wait(self, timeout=0): ...
    def verstummen(self): ...


def durchlauf(haeppchen: list[str]):
    speaker = MerkSpeaker()
    saetze = SentenceSpeaker(speaker)
    sichtbar = "".join(saetze.feed(h) for h in haeppchen)
    sichtbar += saetze.flush()
    return sichtbar, speaker.saetze


print("=== 1. Tag am Stueck ===")
sicht, gesagt = durchlauf(["Der Befehl heisst <en>save as</en>, Sir. "])
print(f"  sichtbar: {sicht!r}")
for satz in gesagt:
    print(f"  Satz: {satz}")
assert "<en>" not in sicht and "</en>" not in sicht
assert [("", "Der Befehl heisst"), ("en", "save as"), ("de", ", Sir")] == gesagt[0] or gesagt[0][1] == ("en", "save as"), gesagt

print("\n=== 2. Tag zerstueckelt, wie beim Streamen ===")
sicht2, gesagt2 = durchlauf(
    ["Der Befehl", " heisst ", "<", "en", ">", "save", " as", "<", "/", "en",
     ">", ", Sir. "])
print(f"  sichtbar: {sicht2!r}")
for satz in gesagt2:
    print(f"  Satz: {satz}")
assert sicht2 == sicht, f"{sicht2!r} != {sicht!r}"
assert gesagt2 == gesagt

print("\n=== 3. Kein spitzes Zeichen darf aufblitzen ===")
speaker = MerkSpeaker()
saetze = SentenceSpeaker(speaker)
zwischenstaende = []
for h in ["Test ", "<", "e", "n", ">", "hello", "<", "/", "e", "n", ">", " ok."]:
    zwischenstaende.append(saetze.feed(h))
saetze.flush()
print(f"  Teilausgaben: {zwischenstaende}")
assert not any("<" in z for z in zwischenstaende), "Tag war kurz sichtbar"

print("\n=== 4. Ganzer englischer Satz ===")
sicht4, gesagt4 = durchlauf(["<en>I am afraid I cannot do that, Sir.</en>"])
print(f"  sichtbar: {sicht4!r}")
print(f"  gesagt:   {gesagt4}")
assert gesagt4 == [[("en", "I am afraid I cannot do that, Sir.")]], gesagt4

print("\n=== 5. Ohne Markierung: die Wortliste entscheidet ===")
sicht5, gesagt5 = durchlauf(["Guten Morgen, Sir. Good morning, Sir."])
print(f"  sichtbar: {sicht5!r}")
for satz in gesagt5:
    print(f"  Satz: {satz}")
assert all(s is None for satz in gesagt5 for s, _ in satz), gesagt5

print("\n=== 6. Modell bricht mitten im Tag ab ===")
sicht6, gesagt6 = durchlauf(["Alles klar, Sir. <e"])
print(f"  sichtbar: {sicht6!r} (der Rest kommt am Ende doch heraus)")

print("\nAlles wie erwartet.")
