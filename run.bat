@echo off
echo ============================================
echo   English Coach - Setup and Run
echo ============================================
echo.

cd /d "%~dp0"

:: Install dependencies
echo Installing dependencies...
pip install -r requirements.txt -q
echo.

:: Check .env
if not exist .env (
    copy .env.example .env
    echo.
    echo ================================================
    echo   IMPORTANT: Add your Anthropic API key!
    echo   Open the .env file in this folder and replace
    echo   "your_api_key_here" with your actual key.
    echo   Get it at: https://console.anthropic.com/
    echo ================================================
    echo.
    pause
    exit /b
)

:: Run the app
echo Starting English Coach...
echo Open http://localhost:5050 in your browser
echo.
python main.py
pause
