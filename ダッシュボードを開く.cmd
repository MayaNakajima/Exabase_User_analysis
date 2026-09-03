@echo off
rem Open the latest usage-analysis dashboard HTML in the default browser.
rem (ASCII-only content; Japanese handling is in open_dashboard.ps1 to avoid cmd codepage issues)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0open_dashboard.ps1"
