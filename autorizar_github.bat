@echo off
title Autorizar GitHub - 1 Clic
cd /d "%~dp0"
set "PATH=C:\Users\scdia\.local\bin;C:\Users\scdia\.local\git\cmd;C:\Users\scdia\.local\git\mingw64\bin;%PATH%"

echo =====================================================================
echo  AUTORIZAR TU CUENTA DE GITHUB (1 CLIC EN EL NAVEGADOR)
echo =====================================================================
echo.
gh auth login --hostname github.com --git-protocol https --web
gh auth setup-git
echo.
echo =====================================================================
echo  ¡AUTORIZADO! Ahora puedes ejecutar subir_a_github.bat
echo =====================================================================
pause
