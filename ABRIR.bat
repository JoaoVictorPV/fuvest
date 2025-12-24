@echo off
setlocal
color 0C

echo =======================================================
echo           PROJETO SANFRAN 2027 - DIREITO USP
echo =======================================================
echo.

:: Define o caminho direto do Node.js
set NPM_PATH="C:\Program Files\nodejs\npm.cmd"
if not exist %NPM_PATH% set NPM_PATH=npm

echo [1/3] Limpando cache do servidor...
if exist "node_modules\.vite" rmdir /s /q "node_modules\.vite"

echo.
echo [2/3] Iniciando o servidor de desenvolvimento...
echo      (Uma nova janela de comando sera aberta)

:: Inicia o servidor com a flag --force para limpar cache e garantir novo carregamento
start "SERVIDOR SANFRAN" cmd /k "call %NPM_PATH% run dev -- --force"

echo.
echo [3/3] Aguardando o servidor carregar (15s)...
timeout /t 15 >nul

echo.
echo [*] Abrindo o sistema no Google Chrome...

:: Tenta encontrar o Chrome em caminhos comuns
set CHROME_EXE="C:\Program Files\Google\Chrome\Application\chrome.exe"
if not exist %CHROME_EXE% set CHROME_EXE="C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
if not exist %CHROME_EXE% set CHROME_EXE=chrome.exe

start "" %CHROME_EXE% "http://localhost:5173"

echo.
echo =======================================================
echo  SISTEMA REINICIADO COM LIMPEZA DE CACHE! 
echo.
echo  IMPORTANTE: Se a tela ficar branca, aguarde 10 segundos
echo  e pressione F5 no Chrome.
echo =======================================================
echo.
pause
