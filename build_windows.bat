@echo off
setlocal
cd /d "%~dp0"
py -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto failed
py generate_assets.py
if errorlevel 1 goto failed
py -m PyInstaller --noconfirm --clean --windowed --onefile --name Labelizer4x6 --icon labelizer.ico --add-data "labelizer.ico;." --add-data "checkbox_checked.png;." --add-data "drop_pdf_icon.png;." --collect-all cv2 --collect-all fitz labelizer.py
if errorlevel 1 goto failed
echo.
echo Finished: dist\Labelizer4x6.exe
pause
exit /b 0
:failed
echo Build failed. Check the error above.
pause
exit /b 1
