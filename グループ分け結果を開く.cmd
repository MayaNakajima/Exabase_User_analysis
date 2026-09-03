@echo off
rem Open the latest grouping-result Excel.
rem (ASCII-only content; Japanese handling is in open_grouping.ps1 to avoid cmd codepage issues)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0open_grouping.ps1"
