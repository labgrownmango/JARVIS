"""Trockenlauf der Oberflaeche: Statusanzeige, Streaming, satzweises Sprechen -
mit einem gefälschten Modell, also ohne API-Key und ohne Kosten."""
import os
import time

os.environ["JARVIS_SIMPLE_INPUT"] = "1"   # Eingaben kommen aus dem Skript

import jarvis.main as m
from jarvis.brain import Brain

ANTWORT = ("Der Arbeitsspeicher liegt bei siebenundachtzig Prozent, Sir. "
           "Das ist reichlich viel. Ich empfehle, ein paar Browser-Tabs zu opfern.")


def fake_ask(self, user_text, on_status=lambda s: None,
             on_delta=lambda d: None, max_tool_rounds=5,
             # Die Attrappe muss alles annehmen, was das Echte annimmt -
             # sonst faellt sie beim naechsten neuen Parameter um. Gemessen:
             # nach der Einfuehrung von 'gesprochen' stand mitten in der
             # Vorfuehrung "[Fehler] fake_ask() got an unexpected keyword
             # argument". Der Test lief trotzdem mit Rueckgabewert 0 durch,
             # die Reihe meldete gruen - gesehen hat es niemand.
             **rest):
    on_status("denkt")
    time.sleep(2.0)                       # Modell denkt
    on_status("werkzeug:system_status")
    time.sleep(1.2)                       # Werkzeug laeuft
    on_status("denkt")
    time.sleep(1.5)
    for wort in ANTWORT.split(" "):       # Antwort tropft wortweise ein
        on_delta(wort + " ")
        time.sleep(0.06)
    return ANTWORT


def fake_init(self):
    self.history = []
    self.model = "moonshotai/kimi-k3"
    self.rangliste = [self.model]
    self.ping = [{"modell": self.model, "zustand": "frei", "dauer": 1.4}]


def fake_pingen(self):
    return self.ping


Brain.ask = fake_ask
Brain.__init__ = fake_init
Brain.pingen = fake_pingen

import builtins
eingaben = iter(["/zeit", "/hilfe /st", "Wie voll ist mein Arbeitsspeicher?",
                 "/ende"])
builtins.input = lambda prompt="": (print(prompt, end=""), next(eingaben))[1]

m.main()
