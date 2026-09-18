"""Warum erkennt der Schutz die anderen Jarvis-Prozesse nicht?"""
import subprocess
import sys
import time

import psutil

print("Mein Interpreter:", sys.executable)
print()

hintergrund = subprocess.Popen([sys.executable, "-u", "-m", "jarvis.web"],
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
time.sleep(6)
print(f"Testserver gestartet, PID {hintergrund.pid}\n")

for p in psutil.process_iter(["pid", "name", "exe", "cmdline"]):
    try:
        if "python" not in (p.info["name"] or "").lower():
            continue
        exe = p.info["exe"] or "(nicht lesbar)"
        cmd = " ".join(p.info["cmdline"] or [])[:60]
        gleich = exe.lower() == (sys.executable or "").lower()
        print(f"  PID {p.info['pid']:>6}  exe-gleich={gleich}")
        print(f"          exe: {exe}")
        print(f"          cmd: {cmd}")
    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
        print(f"  PID {p.info['pid']:>6}  nicht lesbar: {type(e).__name__}")

hintergrund.terminate()
