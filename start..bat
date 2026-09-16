@echo off
start "Avatar Server" cmd /k "cd /d C:\Users\dell\Desktop\AI-Avatar-Project\avatar && py -3.11 -m http.server 8000"
timeout /t 2 /nobreak >nul
start "Brain Server" cmd /k "cd /d C:\Users\dell\Desktop\AI-Avatar-Project\brain && py -3.11 server.py"
timeout /t 3 /nobreak >nul
start http://localhost:8000