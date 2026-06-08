@echo off
chcp 65001 >NUL

:: Para que el programa funcione tienes que cambiar la ubicacion de los directorios por los tuyos
:: Directorio en el que usa Python
set "PYTHON=C:\Users\Pruebas"
:: Directorio donde se encuentra el programa
set "DIRECTORIO=C:\Users\Pruebas"
:: Directorio del uv
set "UV_PATH=C:\Users\Pruebas"
:: Directorio de ollama
set "OLLAMA_PATH=C:\Users\Pruebas"

for %%F in ("%UV_PATH%") do set "PATH=%%~dpF;%PATH%"

cd /d "%DIRECTORIO%"
if errorlevel 1 (
    echo ERROR: No se encuentra el directorio %DIRECTORIO%
    pause
    exit /b 1
)

if not exist "Logs_Pipeline" mkdir "Logs_Pipeline"

set "TIMESTAMP=%DATE:~6,4%-%DATE:~3,2%-%DATE:~0,2%_%TIME:~0,2%-%TIME:~3,2%-%TIME:~6,2%"
set "TIMESTAMP=%TIMESTAMP: =0%"
set "LOG=Logs_Pipeline\pipeline_%TIMESTAMP%.log"

echo [%DATE% %TIME%] === Inicio de ejecucion === >> "%LOG%"

if not exist "%UV_PATH%" (
    echo [%DATE% %TIME%] ERROR: No se encuentra uv en %UV_PATH% >> "%LOG%"
    exit /b 1
)
echo [%DATE% %TIME%] uv encontrado OK >> "%LOG%"

if not exist "%DIRECTORIO%\ejecutar_pipeline.py" (
    echo [%DATE% %TIME%] ERROR: No se encuentra ejecutar_pipeline.py en %DIRECTORIO% >> "%LOG%"
    exit /b 1
)
echo [%DATE% %TIME%] Script encontrado OK >> "%LOG%"

tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I "ollama.exe" >NUL
if errorlevel 1 (
    echo [%DATE% %TIME%] Arrancando Ollama... >> "%LOG%"
    start "" "%OLLAMA_PATH%" serve
    timeout /t 10 /nobreak >NUL
    echo [%DATE% %TIME%] Ollama arrancado, esperados 10s >> "%LOG%"
) else (
    echo [%DATE% %TIME%] Ollama ya estaba corriendo >> "%LOG%"
)

echo [%DATE% %TIME%] Lanzando pipeline... >> "%LOG%"
"%UV_PATH%" run ejecutar_pipeline.py >> "%LOG%" 2>&1
set "EXIT_CODE=%ERRORLEVEL%"

echo [%DATE% %TIME%] Codigo de salida: %EXIT_CODE% >> "%LOG%"
echo [%DATE% %TIME%] === Fin de ejecucion === >> "%LOG%"

exit /b %EXIT_CODE%