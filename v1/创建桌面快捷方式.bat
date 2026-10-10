@echo off
cd /d "%~dp0"
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\MeClaw.lnk'); $s.TargetPath = '%~dp0启动MeClaw.vbs'; $s.WorkingDirectory = '%~dp0'; $s.IconLocation = 'pythonw.exe,0'; $s.Save(); echo 'Done'"
pause
