@echo off
REM Builds a standalone Windows executable (dist\vmfinder.exe) that bundles
REM Python, Flask and pyVmomi - no Python install needed on the target
REM machine. Must be run on Windows (PyInstaller does not cross-compile).
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found on PATH. Install Python 3.8+ from python.org and try again.
    exit /b 1
)

if not exist .venv (
    python -m venv .venv
)
call .venv\Scripts\activate.bat

pip install -q -r requirements.txt
pip install -q pyinstaller pywin32

if "%VMFINDER_VERSION%"=="" set VMFINDER_VERSION=dev
python generate_version_info.py %VMFINDER_VERSION%

pyinstaller --onefile --name vmfinder ^
    --icon "templates\static\favicon.ico" ^
    --add-data "templates;templates" ^
    --version-file version_info.txt ^
    --collect-all pyVmomi ^
    --collect-all pyVim ^
    VMFinder.py

rmdir /s /q build 2>nul
del /q vmfinder.spec version_info.txt 2>nul

echo.
echo Built: dist\vmfinder.exe
