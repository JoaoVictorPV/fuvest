@echo off
echo ==========================================
echo      PROJETO SANFRAN 2027 - INICIANDO
echo ==========================================
echo.
echo Iniciando o servidor de desenvolvimento...
echo Por favor, aguarde a abertura do navegador.
echo.

start "Sanfran Server" cmd /c "npm run dev"

timeout /t 5 >nul

start chrome http://localhost:5173

echo.
echo Servidor iniciado! Mantenha esta janela (ou a do servidor) aberta.
echo.
pause
