@echo off
REM ============================================================
REM ブランチを作成して全変更をコミット＆push する。
REM 使い方:  tools\git-commit-branch.bat ブランチ名 "コミットメッセージ"
REM 例:      tools\git-commit-branch.bat feature/xxxx "○○を追加"
REM ============================================================
setlocal
cd /d "%~dp0.."
if "%~1"=="" echo [エラー] ブランチ名を指定してください & exit /b 1
if "%~2"=="" echo [エラー] コミットメッセージを指定してください & exit /b 1

REM まだ1つもコミットが無い（初回）場合は、先に main へ初回コミットが必要
git rev-parse --verify HEAD >nul 2>&1
if errorlevel 1 (
  echo [注意] このリポジトリにはまだコミットがありません。
  echo         初回は  tools\git-init-main.bat "初回コミット"  を先に実行してください。
  exit /b 1
)

git switch -c %1 || git checkout -b %1
git add -A
git commit -m %2
git push -u origin %1
echo.
echo 完了: ブランチ %1 を push しました。
echo GitHub でレビュー後、  tools\git-merge-to-main.bat %1  で main へマージできます。
endlocal
