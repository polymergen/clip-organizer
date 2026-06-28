@echo off
cd /d "d:\codes_native_windows\UnifiedTools"
"D:\Installed\Anaconda\envs\PyEditorFromFFS\python.exe" main.py %*
if errorlevel 1 pause
