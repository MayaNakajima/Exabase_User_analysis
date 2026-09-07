@echo off
rem Apply an exam-result CSV (file picker). (ASCII-only; logic in run_exam.ps1)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_exam.ps1"
