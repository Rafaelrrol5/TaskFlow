@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_CMD="
if defined TASKFLOW_PYTHON set "PYTHON_CMD=%TASKFLOW_PYTHON%"
if exist ".venv\Scripts\python.exe" set "PYTHON_CMD=.venv\Scripts\python.exe"
if not defined PYTHON_CMD where py >nul 2>nul && set "PYTHON_CMD=py -3"
if not defined PYTHON_CMD where python >nul 2>nul && set "PYTHON_CMD=python"

if not defined PYTHON_CMD (
    echo Python nao foi encontrado. Instale as dependencias de desenvolvimento primeiro.
    exit /b 1
)

%PYTHON_CMD% -c "import PyInstaller, webview" >nul 2>nul
if errorlevel 1 (
    echo Dependencias de build ausentes. Execute: %PYTHON_CMD% -m pip install -r requirements.txt
    exit /b 1
)

if exist "build\TaskFlow" rmdir /s /q "build\TaskFlow"
if exist "dist\TaskFlow" rmdir /s /q "dist\TaskFlow"

%PYTHON_CMD% -m PyInstaller --noconfirm --clean TaskFlow.spec
if errorlevel 1 exit /b 1

echo.
echo Build concluida: dist\TaskFlow\TaskFlow.exe
endlocal

