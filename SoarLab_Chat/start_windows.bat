@echo off
cd /d "%~dp0"
python -m pip install -r requirements.txt || goto :error
python diagnostico_soar.py || goto :error
python app.py
goto :eof
:error
echo Native validation failed. Check the messages above.
pause
