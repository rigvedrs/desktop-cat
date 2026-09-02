@echo off
title Desktop Cat - build
cd /d "%~dp0"

echo.
echo   Building DesktopCat.exe
echo   ------------------------------------------------
echo   This takes a few minutes the first time.
echo.

set PY=py
py --version >nul 2>nul || set PY=python
%PY% --version >nul 2>nul || goto nopython

echo   [1/3] Installing PySide6 and PyInstaller...
%PY% -m pip install --upgrade --quiet pip
%PY% -m pip install --upgrade --quiet PySide6 pyinstaller
if errorlevel 1 goto failed

echo   [2/3] Packaging...
%PY% -m PyInstaller --noconfirm --onefile --windowed ^
  --name DesktopCat --icon cat.ico --splash splash.png ^
  --exclude-module PySide6.QtQml ^
  --exclude-module PySide6.QtQuick ^
  --exclude-module PySide6.QtWebEngineCore ^
  --exclude-module PySide6.QtMultimedia ^
  --exclude-module PySide6.Qt3DCore ^
  --exclude-module PySide6.QtCharts ^
  --exclude-module PySide6.QtDataVisualization ^
  cat.py
if errorlevel 1 goto failed

echo   [3/3] Done.
echo.
echo   Your file is here:
echo      %cd%\dist\DesktopCat.exe
echo.
echo   That single file is what you send to people. Nothing to install.
echo.
explorer "%cd%\dist"
pause
exit /b 0

:nopython
echo   Python was not found on this PC.
echo.
echo   Install it from https://www.python.org/downloads/
echo   IMPORTANT: tick "Add python.exe to PATH" on the first screen.
echo   Then run this file again.
echo.
pause
exit /b 1

:failed
echo.
echo   Something went wrong above.
echo   Fixes to try, in order:
echo     1. Delete the --splash splash.png part of the command in this file.
echo     2. Delete all the --exclude-module lines from this file.
echo   Then run it again.
echo.
pause
exit /b 1
