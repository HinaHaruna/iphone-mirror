@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo [!] ไม่พบ Python — ติดตั้งจาก https://www.python.org/downloads/ ก่อน ^(ติ๊ก "Add Python to PATH"^)
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [*] สร้าง virtual environment...
  python -m venv .venv
)

call ".venv\Scripts\activate.bat"

python -c "import customtkinter, PIL, keyboard" 2>nul
if errorlevel 1 (
  echo [*] ติดตั้ง dependencies...
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
)

python app.py
if errorlevel 1 pause
endlocal
