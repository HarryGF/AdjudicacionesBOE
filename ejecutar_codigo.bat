@echo off
chcp 1252 >NUL

set PYTHON=C:\Users\hxmn8\anaconda3\python.exe
set DIRECTORIO=C:\Users\hxmn8\Documents\Practicas\BOE\Adjudicacion

cd /d "%DIRECTORIO%"
if errorlevel 1 (
    echo ERROR: No se encuentra el directorio %DIRECTORIO%
    pause
    exit /b 1
)

:: Creamos la carpeta de logs si no existe
if not exist "%DIRECTORIO%\Logs_Pipeline" mkdir "%DIRECTORIO%\Logs_Pipeline"

tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I "ollama.exe" >NUL
if errorlevel 1 (
    echo Arrancando Ollama...
    start "" "C:\Users\hxmn8\AppData\Local\Programs\Ollama\ollama.exe" serve
    timeout /t 10 /nobreak >NUL
)

%PYTHON% ejecutar_pipeline.py >> "%DIRECTORIO%\Logs_Pipeline\output.txt" 2>&1
pause
exit /b %ERRORLEVEL%