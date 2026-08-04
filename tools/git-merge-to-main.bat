@echo off
REM ============================================================
REM レビューOK後、指定ブランチを main にマージして push する。
REM 使い方:  tools\git-merge-to-main.bat ブランチ名
REM 例:      tools\git-merge-to-main.bat feature/xxxx
REM ============================================================
setlocal
cd /d "%~dp0.."
if "%~1"=="" echo [エラー] ブランチ名を指定してください & exit /b 1

git switch main || git checkout main
if errorlevel 1 echo [エラー] main が見つかりません。初回は tools\git-init-main.bat を先に実行。 & exit /b 1
git merge --no-ff %1 -m "Merge %1 into main"
git push origin main
echo.
echo 完了: %1 を main にマージし push しました。
echo （不要になったブランチは GitHub 側で削除できます）
endlocal
