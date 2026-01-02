@echo off
set PYTHONPATH=%~dp0
py -m streamlit run "%~dp0src\dashboard.py"
pause
