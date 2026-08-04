@echo off
REM ============================================================
REM 【初回のみ】main へ初回コミットして push し、ベースラインを作る。
REM （リポジトリにコミットが1つも無いとブランチ作成・マージができないため）
REM 使い方:  tools\git-init-main.bat "初回コミット: 分析基盤一式"
REM ============================================================
setlocal
cd /d "%~dp0.."
if "%~1"=="" echo [エラー] コミットメッセージを指定してください & exit /b 1

git rev-parse --verify HEAD >nul 2>&1
if not errorlevel 1 (
  echo [注意] 既にコミットが存在します。初回用のこのスクリプトは不要です。
  echo         通常の変更は  tools\git-commit-branch.bat  を使ってください。
  exit /b 1
)

REM 既定ブランチ名を main に
git symbolic-ref HEAD refs/heads/main
git add -A
git commit -m %1
git push -u origin main
echo.
echo 完了: main に初回コミットして push しました。
echo 以降の変更は  tools\git-commit-branch.bat ブランチ名 "説明"  → レビュー → tools\git-merge-to-main.bat ブランチ名  で運用します。
endlocal
