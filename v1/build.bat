@echo off
pip install -r requirements.txt
pyinstaller --noconfirm --onedir ^
    --add-data "web;web" ^
    --add-data "backend;backend" ^
    --name MeClaw ^
    --windowed ^
    main.py
echo Build complete! Check dist/MeClaw/
pause
