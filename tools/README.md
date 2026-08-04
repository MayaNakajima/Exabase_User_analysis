# tools/ — Git運用ヘルパー（Windows）

ローカルの git を使って、ブランチ運用を1コマンドで行うためのバッチ。
コマンドプロンプトでリポジトリ直下から実行する（ダブルクリックでも可だが引数指定のためcmd推奨）。

## 初回だけ（コミットが1つも無い状態）
```
tools\git-init-main.bat "初回コミット: 分析基盤一式"
```
main にベースラインを作成して push する。これをやらないとブランチ作成・マージができない。

## 通常の変更（2回目以降）
```
tools\git-commit-branch.bat feature/xxxx "変更内容の説明"
```
→ GitHub でレビュー →
```
tools\git-merge-to-main.bat feature/xxxx
```

## 補足
- push 時に認証を求められたら、GitHub にサインイン済みの資格情報で進める。
- 変更内容の記録は `docs/変更履歴.md` に残す運用（レビュー観点もそこに記載）。
- GitHub Desktop を使う場合も同じ流れ（ブランチ作成→コミット→PR→マージ）。
