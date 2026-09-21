@echo off 
set INSIEDR_SCHEDULED_TASK=1 
if exist "D:\Projects\AISH\InsiEDR\.env" for /f "usebackq tokens=1,2 delims==" %%A in ("D:\Projects\AISH\InsiEDR\.env") do set %%A=%%B 
cd /d "D:\Projects\AISH\InsiEDR" 
"D:\Projects\AISH\InsiEDR\.venv\Scripts\python.exe" -m agent.agent 
