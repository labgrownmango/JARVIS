"""
Einfaches Token‑Schätz‑Skript.
Liest entweder eine angegebene Datei oder den Standard‑Eingabestrom,
schätzt die Token‑Anzahl grob und gibt das Ergebnis aus.
Keine Netzwerkzugriffe, keine Dateiänderungen.
"""

import argparse
import sys


def estimate_tokens(text: str) -> int:
    """
    Grobe Token‑Schätzung:
    - Eine gängige Faustregel: ~4 Zeichen pro Token.
    - Zusätzlich wird die Wortzahl herangezogen (ein Wort ≈ 1,3 Token).
    Das Maximum beider Schätzungen wird zurückgegeben, um eine
    konservative Obergrenze zu liefern.
    """
    if not text:
        return 0
    char_based = len(text) // 4
    word_based = int(len(text.split()) * 1.3)
    return max(char_based, word_based)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Schätzt grob die Token‑Anzahl einer Datei oder von stdin."
    )
    parser.add_argument(
        "file",
        nargs="?",
        type=argparse.FileType("r", encoding="utf-8"),
        default=sys.stdin,
        help="Zu lesende Datei; wird weggelassen, wird stdin verwendet.",
    )
    args = parser.parse_args()

    try:
        with args.file as f:
            content = f.read()
    except OSError as e:
        sys.stderr.write(f"Fehler beim Lesen der Eingabe: {e}\n")
        sys.exit(1)

    token_estimate = estimate_tokens(content)
    print(f"Geschätzte Token-Anzahl: {token_estimate}")


if __name__ == "__main__":
    main()
