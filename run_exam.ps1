# AI資格試験の結果CSVを選んで反映する（受験台帳→グループ分け→ダッシュボード）
Add-Type -AssemblyName System.Windows.Forms
$py = "C:\work\anaconda_install\python.exe"
$scripts = Join-Path $PSScriptRoot "scripts"
$dlg = New-Object System.Windows.Forms.OpenFileDialog
$dlg.Filter = "CSVファイル (*.csv)|*.csv|すべてのファイル (*.*)|*.*"
$dlg.Title = "AI資格試験の結果CSVを選択してください"
$dataDir = Join-Path $PSScriptRoot "data"
if (Test-Path $dataDir) { $dlg.InitialDirectory = $dataDir }
if ($dlg.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) {
  Write-Host "キャンセルしました"; Read-Host "Enterキーで閉じる"; return
}
$csv = $dlg.FileName
Write-Host ("反映する試験結果: " + $csv)
Write-Host "----------------------------------------"
Push-Location $scripts
& $py "update_exam.py" $csv
Pop-Location
Write-Host "----------------------------------------"
Write-Host "完了しました。グループ分け結果を開く.cmd で最新を確認できます。"
Read-Host "Enterキーで閉じる"
