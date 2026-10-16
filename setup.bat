@echo off
setlocal EnableDelayedExpansion
title Finance Tracker Setup

:: Check for Administrative Privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Requesting Administrative Privileges...
    echo Silakan jalankan script ini sebagai Administrator.
    pause
    exit /b 1
)

set "ROOT=%~dp0"
set "CLI_DIR=%ROOT%apps\cli"
set "API_DIR=%ROOT%packages\api"
set "WEB_DIR=%ROOT%packages\web"
set "ENV_FILE=%WEB_DIR%\.env"
set "SETUP_DONE=%ROOT%.setup_done"

:: Resolve Python Executable
set "PYTHON_EXE=python"
set "PYTHON_ARGS="
python --version >nul 2>&1
if %errorlevel% neq 0 (
    if exist "%USERPROFILE%\AppData\Local\Programs\Python\Python310\python.exe" (
        set "PYTHON_EXE=%USERPROFILE%\AppData\Local\Programs\Python\Python310\python.exe"
    ) else if exist "%USERPROFILE%\AppData\Local\Programs\Python\Launcher\py.exe" (
        set "PYTHON_EXE=%USERPROFILE%\AppData\Local\Programs\Python\Launcher\py.exe"
        set "PYTHON_ARGS=-3.10"
    )
)

if exist "%SETUP_DONE%" goto :MAIN_MENU

:: ============================================================
:: SETUP — hanya jalan sekali
:: ============================================================
cls
echo.
echo  ======================================================
echo   Finance Tracker — First-Time Setup
echo  ======================================================
echo.

echo  [1/6] Checking Python...
"%PYTHON_EXE%" %PYTHON_ARGS% --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python tidak ditemukan di PATH atau lokasi standar.
    echo  Download: https://www.python.org/downloads/
    echo  Centang "Add Python to PATH" saat install.
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('^"%PYTHON_EXE%^" %PYTHON_ARGS% --version 2^>^&1') do set "PY_VER=%%v"
echo         Python %PY_VER% OK

echo  [2/6] Checking Node.js...
node --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Node.js tidak ditemukan di PATH.
    echo  Download: https://nodejs.org/
    pause
    exit /b 1
)
for /f %%v in ('node --version 2^>^&1') do set "NODE_VER=%%v"
echo         Node.js %NODE_VER% OK

echo  [3/6] Installing Python dependencies...
if exist "%CLI_DIR%\requirements.txt" (
    echo         Installing CLI requirements...
    "%PYTHON_EXE%" %PYTHON_ARGS% -m pip install -r "%CLI_DIR%\requirements.txt" --quiet
)
if exist "%API_DIR%\requirements.txt" (
    echo         Installing API requirements...
    "%PYTHON_EXE%" %PYTHON_ARGS% -m pip install -r "%API_DIR%\requirements.txt" --quiet
)
if exist "%ROOT%apps\api\requirements.txt" (
    echo         Installing apps/api requirements...
    "%PYTHON_EXE%" %PYTHON_ARGS% -m pip install -r "%ROOT%apps\api\requirements.txt" --quiet
)
if exist "%CLI_DIR%\stock_analyzer\requirements.txt" (
    echo         Installing stock analyzer requirements...
    "%PYTHON_EXE%" %PYTHON_ARGS% -m pip install -r "%CLI_DIR%\stock_analyzer\requirements.txt" --quiet
)
echo         Installing additional packages (pandas-ta, yfinance, apscheduler, xgboost, pytesseract, scikit-learn)...
"%PYTHON_EXE%" %PYTHON_ARGS% -m pip install yfinance apscheduler xgboost pytesseract scikit-learn --quiet
"%PYTHON_EXE%" %PYTHON_ARGS% -m pip install "git+https://github.com/twopirllc/pandas-ta.git@development" --quiet
if errorlevel 1 (
    echo  [WARNING] Gagal install pandas-ta via git, mencoba pip standard...
    "%PYTHON_EXE%" %PYTHON_ARGS% -m pip install pandas-ta --quiet
)
echo         Python deps OK

echo  [4/6] Installing Node.js dependencies...
if exist "%WEB_DIR%" (
    cmd /c "cd /d "%WEB_DIR%" && npm install --silent"
    if errorlevel 1 (
        echo  [ERROR] Gagal install Node dependencies di packages\web.
        pause
        exit /b 1
    )
)
echo         Node deps OK

echo  [5/6] Configuring environment...
if not exist "%ENV_FILE%" (
    (
        echo # Finance Tracker — Security Configuration
        echo FINANCE_TRACKER_HOST=127.0.0.1
        echo FINANCE_TRACKER_PORT=8444
        echo FINANCE_TRACKER_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:45678
        echo VITE_API_PORT=8444
        echo FINANCE_TRACKER_DEV_MODE=1
        echo FINANCE_TRACKER_RATE_LIMIT=200
        echo ALLOWED_IP_WHITELIST=127.0.0.1,localhost
    ) > "%ENV_FILE%"
    echo         .env generated OK
) else (
    echo         .env sudah ada, dilewati OK
)

echo  [6/6] Cleanup...
echo         Skipping TLS certificate (Simplified Mode) OK

echo. > "%SETUP_DONE%"

echo.
echo  Setup selesai!
echo.
timeout /t 2 /nobreak >nul

:: ============================================================
:: MAIN MENU
:: ============================================================
:MAIN_MENU
cls
echo.
echo  ======================================================
echo   Finance Tracker  |  CLI v10.0  /  By Zhvny
echo  ======================================================
echo.
echo   1. Command Line Interface
echo   2. Graphical User Interface
echo   3. Exit
echo.
set "CHOICE="
set /p "CHOICE=  Select: "

if "%CHOICE%"=="1" goto :START_CLI
if "%CHOICE%"=="2" goto :START_GUI
if "%CHOICE%"=="3" exit /b 0

echo.
echo  Pilihan tidak valid. Masukkan 1, 2, atau 3.
timeout /t 2 /nobreak >nul
goto :MAIN_MENU

:: ============================================================
:: CLI
:: ============================================================
:START_CLI
cls
echo  Memulai CLI... (ketik 0 di dalam CLI untuk keluar)
echo.
"%PYTHON_EXE%" %PYTHON_ARGS% "%CLI_DIR%\main.py"
echo.
echo  CLI selesai.
timeout /t 2 /nobreak >nul
goto :MAIN_MENU

:: ============================================================
:: GUI
:: ============================================================
:START_GUI
cls
echo.
echo  ======================================================
echo   Finance Tracker — GUI Mode
echo  ======================================================
echo.

echo  API Server  : http://127.0.0.1:8444
echo  Dev Server  : http://localhost:45678
echo.
echo  Membuka server di window terpisah...
echo  Tutup window server untuk menghentikan GUI.
echo.

start "FT - API Server" cmd /k "cd /d "%API_DIR%" && "%PYTHON_EXE%" %PYTHON_ARGS% api_server.py"

echo [*] Waiting for API Server to become healthy on port 8444...
:WAIT_API_SETUP
timeout /t 2 /nobreak >nul
curl -s --max-time 2 http://localhost:8444/api/health >nul 2>&1
if %errorlevel% neq 0 (
    echo [.] API not ready yet, retrying...
    goto WAIT_API_SETUP
)
echo [*] API Server is healthy!

start "FT - React Dev" cmd /k "cd /d "%WEB_DIR%" && npm run dev"
timeout /t 3 /nobreak >nul
start "" "http://localhost:45678"

pause
goto :MAIN_MENU
