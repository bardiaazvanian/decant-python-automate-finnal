@echo off
cd /d "%~dp0"
"C:\Users\bardia\AppData\Local\Programs\Python\Python313\python.exe" decant_price_updater.py
if %ERRORLEVEL% neq 0 (
    echo Script failed with error code %ERRORLEVEL%
    pause
)
