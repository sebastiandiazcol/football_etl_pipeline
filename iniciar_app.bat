@echo off
title Football Analytics & Probabilidades Web App
cd /d "%~dp0"
echo =====================================================================
echo  INICIANDO FOOTBALL ANALYTICS & PROBABILIDADES WEB APP
echo =====================================================================
echo  Abriendo interfaz en tu navegador (http://localhost:8501)...
echo  Presiona Ctrl + C en esta ventana para detener el servidor.
echo =====================================================================
".venv\Scripts\streamlit.exe" run app.py
pause
