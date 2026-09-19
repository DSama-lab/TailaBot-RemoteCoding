@echo off
REM Launcher do TailaBot (detached via Task Scheduler / clique duplo)
cd /d "C:\Users\Dubainana\Documents\AAA digital PROJECT\AAA    TBOT 00 GENERAL 2026 - XPS\TBot-TailaBot\TailaBot-RemoteCoding"
.venv\Scripts\python.exe -u tailabot_remote.py >> bot_run.log 2>> bot_run.err.log