@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
rem Startet Jarvis. Parameter werden durchgereicht, z.B.:  "Jarvis starten.bat" --voice
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [Setup] Lege virtuelle Umgebung an ...
    python -m venv .venv || goto :kein_python
    .venv\Scripts\python.exe -m pip install --upgrade pip
    .venv\Scripts\python.exe -m pip install -r requirements.txt
)

if not exist "voices\de_DE-thorsten-medium.onnx" (
    echo [Setup] Lade die Sprachausgabe-Stimme ...
    .venv\Scripts\python.exe -m piper.download_voices de_DE-thorsten-medium --data-dir voices
)

if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo.
    echo [Setup] .env wurde angelegt. Trag deinen NVIDIA-Key bei JARVIS_API_KEY ein
    echo         und starte danach erneut.
    notepad ".env"
    pause
    exit /b 1
)

.venv\Scripts\python.exe -m jarvis.main %*
pause
exit /b 0

:kein_python
echo.
echo Python fehlt. Installiere es mit:
echo     winget install -e --id Python.Python.3.12
pause
exit /b 1
