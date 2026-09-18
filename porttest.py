"""Ist Port 80 frei - und dürfen wir ihn belegen?"""
import socket

print("=== Hört dort schon jemand? ===")
probe = socket.socket()
probe.settimeout(1)
belegt = probe.connect_ex(("127.0.0.1", 80)) == 0
probe.close()
print(f"  {'BELEGT - jemand antwortet auf Port 80' if belegt else 'niemand da'}")

print("\n=== Dürfen wir ihn belegen? ===")
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    s.bind(("127.0.0.1", 80))
    s.listen(1)
    print("  ja - Port 80 laesst sich oeffnen, ohne Administratorrechte")
    geht = True
except OSError as exc:
    print(f"  nein: {exc}")
    geht = False
finally:
    s.close()

if geht:
    print("\n  Damit waere http://jarvis moeglich - ganz ohne Nummer.")
