@echo off
setlocal

REM File Index Service Windows起動スクリプト
REM ポート8080でバックエンド（+静的フロントエンド）を起動

set PORT=8080

echo Stopping existing process on port %PORT%...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :%PORT% ^| findstr LISTENING') do (
    echo Port %PORT% is in use by PID %%a. Killing process...
    taskkill /F /PID %%a
)

echo Starting File Index Service (Port %PORT%)...
echo Access http://localhost:%PORT% to manage the service.

cd backend
set PYTHONPATH=.
python -m uvicorn app.main:app --host 0.0.0.0 --port %PORT% --workers 1 --log-level info

cd ..
pause
