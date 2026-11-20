@echo off
title Claude Code setup for Desktop Pet
echo.
echo  [1/3] Installing Claude Code ... (no progress bar, please wait)
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://claude.ai/install.ps1 | iex"
echo.
echo  [2/3] Adding Claude Code to PATH ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$d = Join-Path $env:USERPROFILE '.local\bin'; $p = [Environment]::GetEnvironmentVariable('Path','User'); if (-not (($p -split ';') -contains $d)) { [Environment]::SetEnvironmentVariable('Path', ($p.TrimEnd(';') + ';' + $d), 'User') }"
if not exist "%USERPROFILE%\.local\bin\claude.exe" (
  echo.
  echo  Install failed. Please open Claude_guide txt in this folder.
  pause
  exit /b
)
echo.
echo  [3/3] Login
echo   - Choose: Claude account with subscription
echo   - A browser opens. Log in, then paste the code back HERE and press Enter.
echo   - "Trust this folder?" -^> just press Enter (No, exit) - that's OK.
echo.
pause
cd /d "%USERPROFILE%"
"%USERPROFILE%\.local\bin\claude.exe"
echo.
echo  Done! Restart the pet (right-click - quit - RUN_xxx.bat).
pause
