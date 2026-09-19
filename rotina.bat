@echo off
REM Inicia a rotina local (segundo plano), desacoplada.
cd /d "%~dp0"
start "" /b .venv\Scripts\python.exe -u rotina.py >> rotina.log 2>&1