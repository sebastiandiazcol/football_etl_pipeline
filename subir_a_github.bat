@echo off
title Subir Cambios a GitHub - Football Analytics
cd /d "%~dp0"
set "PATH=C:\Users\scdia\.local\bin;C:\Users\scdia\.local\git\cmd;C:\Users\scdia\.local\git\mingw64\bin;%PATH%"

echo =====================================================================
echo  SUBIENDO CODIGO A TU REPOSITORIO DE GITHUB
echo  Repositorio: https://github.com/sebastiandiazcol/football_etl_pipeline
echo =====================================================================
echo.

git push -u origin main
if %ERRORLEVEL% EQU 0 goto exito

echo.
echo =====================================================================
echo  AUTORIZACION DE GITHUB REQUERIDA (SOLO 1 VEZ)
echo =====================================================================
echo  Se abrira tu navegador web con un codigo para autorizar en 1 clic.
echo.
gh auth login --hostname github.com --git-protocol https --web

echo.
echo Configurando credenciales de Git...
gh auth setup-git

echo.
echo Reintentando subida a GitHub...
git push -u origin main

if %ERRORLEVEL% EQU 0 goto exito

echo.
echo Ocurrio un error. Verifica que tengas permisos de escritura en sebastiandiazcol/football_etl_pipeline.
pause
exit /b 1

:exito
echo.
echo =====================================================================
echo  ¡LISTO! Codigo subido exitosamente a GitHub (rama main).
echo  Ahora ya puedes ir a https://share.streamlit.io/ y darle a "Deploy!".
echo =====================================================================
echo.
pause
