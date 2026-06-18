@echo off
echo YouTube Research Agent
echo =====================

if not exist .env (
    echo ERROR: .env file not found!
    echo Copy .env.example to .env and fill in your API keys.
    pause
    exit /b 1
)

pip install -r requirements.txt --quiet
echo Starting server at http://localhost:8000
python app.py
pause
