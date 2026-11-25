@echo off
cd /d "%~dp0"
title RabbitPet

set "PY="
where py >nul 2>nul
if not errorlevel 1 set "PY=py"
if defined PY goto have_py
where python >nul 2>nul
if not errorlevel 1 python -c "import sys" >nul 2>nul
if not errorlevel 1 set "PY=python"
if defined PY goto have_py
if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PY=%LocalAppData%\Programs\Python\Python312\python.exe"
if defined PY goto have_py

echo [1/3] Installing Python... please wait
where winget >nul 2>nul
if errorlevel 1 goto dl_py
winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
goto set_py
:dl_py
powershell -NoProfile -Command "Invoke-WebRequest https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe -OutFile $env:TEMP\py_setup.exe"
"%TEMP%\py_setup.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1
:set_py
set "PY=%LocalAppData%\Programs\Python\Python312\python.exe"
if not exist "%PY%" (
  echo Python install failed. Please install from python.org and run again.
  pause
  exit /b
)

:have_py
"%PY%" -c "import PyQt5" >nul 2>nul
if not errorlevel 1 goto test_qt
echo [2/3] Installing PyQt5...
"%PY%" -m pip install --user pyqt5

:test_qt
"%PY%" -c "from minibuddies import runtime;from PyQt5.QtWidgets import QApplication;QApplication([])" >nul 2>nul
if not errorlevel 1 goto run
echo [3/3] Reinstalling Qt...
"%PY%" -m pip uninstall -y pyqt5 pyqt5-qt5 pyqt5-sip >nul 2>nul
"%PY%" -m pip install --user --force-reinstall --no-cache-dir pyqt5

:run
set "PYW=pythonw"
if /i "%PY%"=="py" set "PYW=pyw"
if /i not "%PY%"=="py" if /i not "%PY%"=="python" set "PYW=%PY:python.exe=pythonw.exe%"
start "" "%PYW%" buddies.py yuni+kanna+huya+hina+mashiro+lize+tabi+rin+riko+shibuki+nana+toa+rang+hiyori+mary+bingha!
exit /b
