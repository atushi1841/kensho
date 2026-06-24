@echo off
chcp 65001 >nul
echo Kensho Dashboard 起動中...
"C:\Users\1F\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" -m streamlit run "D:\Project2\kensho\scripts\kensho_dashboard.py"
pause
