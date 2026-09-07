@echo off
rem Run the monthly update pipeline. (ASCII-only; logic in run_monthly.ps1)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_monthly.ps1"
