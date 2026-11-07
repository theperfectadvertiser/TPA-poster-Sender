@echo off
title TPA Poster Sender (Local Computer Storage Mode)
echo ========================================================
echo   Launching TPA Poster Sender (Local 100%% FREE Mode)
echo   Storage: Computer Local Storage (clients.db)
echo ========================================================
cd /d "%~dp0"
set USE_LOCAL_DB=true
call .venv\Scripts\activate.bat
streamlit run app.py
pause
