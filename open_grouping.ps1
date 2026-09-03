# 最新の「グループ分け結果」Excelを開く
$out = Join-Path $PSScriptRoot 'output'
$f = Get-ChildItem -LiteralPath $out -Filter 'グループ分け結果*.xlsx' -ErrorAction SilentlyContinue |
     Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($f) { Start-Process $f.FullName; Write-Host ("開きました: " + $f.Name) }
else {
  Write-Host 'グループ分け結果Excelが見つかりません。'
  Write-Host '先に更新を実行してください:  python scripts\update_exam.py <試験結果CSV>  など'
  Read-Host 'Enterキーで閉じる'
}
