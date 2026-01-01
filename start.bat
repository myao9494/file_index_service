@echo off
REM File Index Service 起動スクリプト (Windows)
REM バックエンドとフロントエンドを同時に起動

setlocal EnableDelayedExpansion

set SCRIPT_DIR=%~dp0
set BACKEND_PORT=8080
set FRONTEND_PORT=5174

echo === File Index Service ===

REM ポート使用中チェック
echo ポートをチェック中...

netstat -ano | findstr ":%BACKEND_PORT% " > nul 2>&1
if %errorlevel% == 0 (
    echo ポート %BACKEND_PORT% が使用中です
    set /p choice="プロセスを終了しますか? (y/n): "
    if /i "!choice!" == "y" (
        for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%BACKEND_PORT% "') do (
            taskkill /PID %%a /F > nul 2>&1
        )
        echo ポート %BACKEND_PORT% を解放しました
    ) else (
        echo 起動を中止します
        exit /b 1
    )
)

netstat -ano | findstr ":%FRONTEND_PORT% " > nul 2>&1
if %errorlevel% == 0 (
    echo ポート %FRONTEND_PORT% が使用中です
    set /p choice="プロセスを終了しますか? (y/n): "
    if /i "!choice!" == "y" (
        for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%FRONTEND_PORT% "') do (
            taskkill /PID %%a /F > nul 2>&1
        )
        echo ポート %FRONTEND_PORT% を解放しました
    ) else (
        echo 起動を中止します
        exit /b 1
    )
)

REM バックエンド起動
echo バックエンドを起動中... (ポート %BACKEND_PORT%)
cd /d "%SCRIPT_DIR%backend"

if not exist ".venv" (
    echo 仮想環境を作成中...
    python -m venv .venv
    call .venv\Scripts\activate
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate
)

start "File Index Backend" cmd /c "set PYTHONPATH=. && python -m uvicorn app.main:app --host 0.0.0.0 --port %BACKEND_PORT%"

REM フロントエンド起動
echo フロントエンドを起動中... (ポート %FRONTEND_PORT%)
cd /d "%SCRIPT_DIR%frontend"

if not exist "node_modules" (
    echo 依存関係をインストール中...
    npm install
)

start "File Index Frontend" cmd /c "npm run dev"

echo.
echo === サービス起動完了 ===
echo 管理GUI:  http://localhost:%FRONTEND_PORT%
echo API:      http://localhost:%BACKEND_PORT%
echo.
echo 停止: 各ウィンドウを閉じてください
echo.

pause
