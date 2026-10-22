@echo off
REM === MultiPost: jalankan langsung dari source (tanpa build exe) ===
cd /d %~dp0
python -m pip install -r requirements.txt
python -m playwright install chromium
python app.py
pause
