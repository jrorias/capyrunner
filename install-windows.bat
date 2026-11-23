@echo off
REM CapyRunner installer for Windows (per-user). Needs Python 3.9+ from python.org (tick "Add to PATH").
setlocal
set "SRC=%~dp0"
set "APPDIR=%LOCALAPPDATA%\CapyRunner"
set "VENV=%APPDIR%\venv"

where py >nul 2>nul && (set "PY=py -3") || (set "PY=python")
%PY% -c "import sys; sys.exit(0 if sys.version_info>=(3,9) else 1)" || (
  echo Python 3.9+ not found. Install it from https://www.python.org/downloads/ and run this again.
  pause & exit /b 1
)

echo Creating virtual environment...
%PY% -m venv "%VENV%" || (pause & exit /b 1)
"%VENV%\Scripts\python.exe" -m pip install -q --upgrade pip
echo Installing CapyRunner (downloads PySide6-Essentials, ~60 MB the first time)...
"%VENV%\Scripts\python.exe" -m pip install -q --upgrade "%SRC%." || (pause & exit /b 1)

echo Creating Start Menu shortcut...
powershell -NoProfile -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Programs')+'\CapyRunner.lnk');" ^
  "$s.TargetPath='%VENV%\Scripts\pythonw.exe'; $s.Arguments='-m capyrunner'; $s.WorkingDirectory='%APPDIR%';" ^
  "$s.Description='CapyRunner'; $s.Save()"

echo Starting CapyRunner...
start "" "%VENV%\Scripts\pythonw.exe" -m capyrunner
echo.
echo Done. Find the runner in the taskbar tray (drag it out of the ^^ overflow to keep it visible).
echo Turn on "Start when I log in" in Settings if you want it at startup.
pause
