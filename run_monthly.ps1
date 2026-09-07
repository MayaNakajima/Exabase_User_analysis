# 月次更新（利用実績＋メンバー一覧）を実行する
$py = "C:\work\anaconda_install\python.exe"
$scripts = Join-Path $PSScriptRoot "scripts"
if (-not (Test-Path (Join-Path $scripts "update_monthly.py"))) {
  Write-Host "scripts\update_monthly.py が見つかりません: $scripts"; Read-Host "Enterキーで閉じる"; return
}
Push-Location $scripts
$py_args = @("update_monthly.py")
if ($env:ANTHROPIC_API_KEY) { $py_args += "--api"; Write-Host "APIキー検出: 分類も自動化します（--api）" }
else { Write-Host "APIキー未設定: 新規プロンプトがある場合は分類ゲートで停止します（Claude Codeで分類→ python update_monthly.py --resume）" }
Write-Host "----------------------------------------"
& $py @py_args
$code = $LASTEXITCODE
Pop-Location
Write-Host "----------------------------------------"
if ($code -eq 0) { Write-Host "完了しました。ダッシュボードを開く.cmd で最新を表示できます。" }
else { Write-Host "途中終了（分類ゲート等）。表示された案内に従ってください。" }
Read-Host "Enterキーで閉じる"
