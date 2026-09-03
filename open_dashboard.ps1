# 最新の「利用分析ダッシュボード」HTMLを、既定ブラウザで描画表示する
# （.html の関連付けがエディタでも、必ずブラウザで開くよう file:// URL を既定ブラウザ実行ファイルに渡す）
function Open-InBrowser([string]$path) {
  $url = ([System.Uri]$path).AbsoluteUri
  # 1) 既定ブラウザ(http)の実行ファイルへ file:// URL を渡す
  try {
    $progId = (Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice' -ErrorAction Stop).ProgId
    $cmd = (Get-ItemProperty "Registry::HKEY_CLASSES_ROOT\$progId\shell\open\command" -ErrorAction Stop).'(default)'
    $exe = $null
    if ($cmd -match '"([^"]+\.exe)"') { $exe = $matches[1] } elseif ($cmd -match '^\s*([^\s"]+\.exe)') { $exe = $matches[1] }
    if ($exe -and (Test-Path -LiteralPath $exe)) { Start-Process -FilePath $exe -ArgumentList $url; return $true }
  } catch {}
  # 2) フォールバック: Edge プロトコル（Windows 11 標準）
  try { Start-Process ("microsoft-edge:" + $url); return $true } catch {}
  # 3) 最終フォールバック: URL を既定ハンドラで
  try { Start-Process $url; return $true } catch {}
  return $false
}

$out = Join-Path $PSScriptRoot 'output'
$f = Get-ChildItem -LiteralPath $out -Filter 'エクサベースAI_利用分析_ダッシュボード*.html' -ErrorAction SilentlyContinue |
     Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($f) {
  if (Open-InBrowser $f.FullName) { Write-Host ("ブラウザで開きました: " + $f.Name) }
  else { Write-Host 'ブラウザ起動に失敗しました。'; Read-Host 'Enterキーで閉じる' }
} else {
  Write-Host 'ダッシュボードHTMLが見つかりません。'
  Write-Host '先に更新を実行してください:  python scripts\update_monthly.py  など'
  Read-Host 'Enterキーで閉じる'
}
