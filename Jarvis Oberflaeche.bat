@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
rem Oeffnet die Oberflaeche. Laeuft der Server schon (Autostart), wird nur
rem der Browser geoeffnet - sonst gaebe es Streit um den Port.
rem
rem Die Portnummer steht hier NICHT. Sie wurde frueher dreimal fest
rem eingetippt (8765), waehrend die Vorgabe inzwischen 80 ist - die
rem Laufpruefung griff also ins Leere, der Browser oeffnete einen toten
rem Port, und danach startete ein zweiter Server daneben. Auch die neue
rem Zahl einzutippen waere nur ein Pflaster: sobald 80 belegt ist, weicht
rem Jarvis auf 8765 aus, und dann stimmt sie wieder nicht.
rem
rem Also wird gefragt: jarvis.adresse sieht nach, wo wirklich einer lauscht,
rem und nennt sonst den Port, auf dem einer landen wuerde.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Bitte zuerst "Jarvis starten.bat" ausfuehren - das richtet alles ein.
    pause
    exit /b 1
)

rem --zustand gibt EINE Zeile aus: "laeuft <adresse>" oder "neu <adresse>".
rem
rem Frueher stand hier "set LAEUFT=%errorlevel%" direkt nach der Schleife.
rem Das ist unzuverlaessig: cmd reicht den Rueckgabewert eines Befehls aus
rem `for /f ... in (`...`)` nicht verlaesslich nach aussen. Geht es einmal
rem daneben, oeffnet sich der Browser UND ein zweiter Server startet
rem daneben - still und schwer zu finden. Jetzt steht die Auskunft in der
rem Ausgabe selbst, und die kommt immer an.
for /f "usebackq tokens=1,2" %%A in (`.venv\Scripts\python.exe -m jarvis.adresse --zustand`) do (
    set "ZUSTAND=%%A"
    set "ADRESSE=%%B"
)

if not defined ADRESSE (
    echo Die Adresse liess sich nicht ermitteln. Laeuft die Einrichtung?
    pause
    exit /b 1
)

if "%ZUSTAND%"=="laeuft" (
    echo Jarvis laeuft bereits - oeffne nur die Seite: %ADRESSE%
    rem Nicht "start" - das nimmt immer den Standardbrowser, also meist Edge,
    rem auch wenn daneben ein Brave mit allen Anmeldungen offensteht.
    rem --oeffnen bevorzugt einen bereits laufenden Browser.
    .venv\Scripts\python.exe -m jarvis.adresse --oeffnen >nul
    exit /b 0
)

echo Starte die Oberflaeche unter %ADRESSE% ...
rem Erst den Browser-Oeffner nebenher losschicken - er WARTET, bis der
rem Server antwortet, und oeffnet dann. Vorher ging das Fenster sofort auf
rem und traf auf einen toten Port: Fehlerseite, einmal aktualisieren, dann
rem ging es. Das war ein Teil des "mal geht es, mal nicht".
start "" /b .venv\Scripts\pythonw.exe -m jarvis.adresse --oeffnen --warten
.venv\Scripts\python.exe -m jarvis.web
pause
