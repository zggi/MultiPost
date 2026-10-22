@echo off
REM === MultiPost: build MultiPost.exe (jalankan di Windows, di folder ini) ===
setlocal
cd /d %~dp0

echo [1/4] Cek Python...
python --version || (echo Python belum terinstall. Install dari python.org, centang "Add to PATH". & pause & exit /b 1)

echo [2/4] Install dependency...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller || goto :err
python -m playwright install chromium || goto :err

echo [3/4] Build exe...
python -m PyInstaller --noconfirm --clean --onedir --windowed --collect-all playwright --name MultiPost app.py || goto :err

echo [4/4] Selesai.
echo File: dist\MultiPost\MultiPost.exe  (klik 2x file itu)
echo PENTING: folder data\ (akun + sesi login) dibuat otomatis di dalam dist\MultiPost\.
echo Jangan pisahkan MultiPost.exe dari folder dist\MultiPost\ - kirim/salin SATU folder itu utuh.
pause
exit /b 0

:err
echo GAGAL. Baca pesan error di atas.
pause
exit /b 1
