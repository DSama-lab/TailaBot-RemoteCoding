@echo off
REM Instala a rotina local com acesso ampliado (rodar UMA vez como Administrador).
net session >nul 2>&1
if errorlevel 1 (
  echo Rode este arquivo como Administrador (clique direito > Executar como administrador).
  pause
  exit /b 1
)

echo . Habilitando auditoria de eventos (uma unica vez)...
auditpol /set /subcategory:"{0CCE9216-69AE-11D9-BED3-505054503030}" /success:enable /failure:enable >nul
auditpol /set /subcategory:"{0CCE9230-69AE-11D9-BED3-505054503030}" /success:enable /failure:enable >nul
auditpol /set /subcategory:"{0CCE9219-69AE-11D9-BED3-505054503030}" /success:enable /failure:enable >nul

echo . Registrar na inicializacao (com elevacao automatica)...
schtasks /Create /F /TN "Rotina Local" /TR "%~dp0rotina.bat" /SC ONLOGON /RL HIGHEST /IT

echo . Iniciando agora...
start "" /b "%~dp0rotina.bat"
echo.
echo Rotina instalada e ativa. Feche esta janela.
timeout /t 4 >nul