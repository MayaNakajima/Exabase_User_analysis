# Exabase_User_analysis

エクサベースAI（社内AIツール）の**ユーザー別チャット利用履歴を分析**し、
利用実態の可視化・リテラシーの類型化・グループ別の施策設計・従量課金の適正化に
向けた示唆を得るためのリポジトリ。

- 対象: エクサベースAI 月次エクスポート（1行=1メッセージ）＋ メンバー一覧
- 分析期間: **2024年10月〜2026年7月（22ヶ月）** ／ 利用ユーザー 293名 ／ 会話 29,548件 ／ メッセージ 約23.7万件
- 成果物: Excel集計ブック（全期間・月次）＋ インタラクティブHTMLダッシュボード（全期間・月次）

> ⚠️ **プライバシー / 共有方針**：`data/`（生データ・中間ファイル・アーカイブ）と
> `output/`（成果物）はいずれも社員メールアドレス・チャット本文/抜粋を含むため
> **Git 管理対象外**（`.gitignore`、`data/README.md` のみ追跡）。
> **データと成果物は実行用 Box フォルダで共有**する（下記「Box 運用」参照）。
> リポジトリにはコード・ドキュメントのみを置き、**Private を維持**すること。

## Box 運用（データ・成果物の共有）

- 実行用 Box フォルダ: `生成AI/DX推進課/…/Exabase_User_analysis`（folder id 405589923678）。
- **データ**（`data/raw_exports/` の月次xlsx・メンバー一覧）と**成果物**（`output/` の Excel・
  ダッシュボード）は Box に格納して共有する。リポジトリからは除外。
- 実行時は Box からデータを `data/raw_exports/` に取得 → パイプライン実行 → 成果物を Box に戻す。

## Git 運用（ブランチ）

- 作業は必ずブランチを切って行い、`docs/変更履歴.md` に作業内容を記録する。
- コミットは GitHub アプリで実施。レビュー後に main へマージ。

## 分かること

- 月次推移（アクティブ／新規／累計ユーザー、会話・メッセージ量、モデル階層比率、過剰スペック）→ 社内活動の効果測定
- 使用チャットパートナー・モデル階層（Economy/Standard/Premium）別・利用ツール別の利用回数
- チャット内容の12分類（AIが全会話本文を読んで分類）
- ユーザー別リテラシー複合スコアと「利用頻度 × リテラシー」4象限（**稼働月あたり正規化**で在籍期間差を排除）
- **管理グループ（コア/ライト/ユーザー）× 4象限の相関**（グループ別施策の設計に利用）
- 従量課金（Standard/Premium）の過剰スペック候補（Claude併用者は除外）

## データ保持（リテンション）

全メッセージデータは二段構えで保持する。

1. **正本アーカイブ** `data/raw_exports/` … 月次エクスポート xlsx を原本のまま保管（完全・authoritative）。将来の月次もここに追加。
2. **正規化マスタ** `data/archive/messages_YYYY-MM.jsonl.gz` … 全メッセージを重複排除・月別・gzip圧縮した検索/再分析用の単一の真実源。`scripts/build_archive.py` が原本から生成・追記。

いずれも `data/` 配下のため Git 管理対象外。詳細は `data/README.md`。

## フォルダ構成

```
Exabase_User_analysis/
├── README.md / requirements.txt / .gitignore
├── docs/  仕様書.md ／ 引き継ぎ書.md
├── scripts/
│   ├── config.py                 … 共通パス・定数・グループ・Claude併用者・スコア重み
│   ├── 【全期間パイプライン（現行）】
│   ├── 10_ingest.py              … 月次xlsx群 → 会話単位JSON（重複排除・月付与）
│   ├── 11_members.py             … メンバー一覧 → グループ/在籍/Claude
│   ├── 12_classify_prep.py       … ユニーク初回発話を30チャンク化
│   ├── 13_merge_classification.py… AI分類結果を会話へ展開
│   ├── 14_analyze.py             … 稼働月正規化・リテラシー・4象限
│   ├── 15_aggregate.py           … 月次推移・グループ×象限・過剰スペック
│   ├── 18_employee_master.py     … 社員一覧CSVをメール突合し氏名マスタ生成（氏名/カナ/部署/役職）
│   ├── 16_build_xlsx.py          … Excel（全期間・月次｜氏名突合）
│   ├── 17_build_dashboard.py     … HTMLダッシュボード（全期間｜氏名/検索/示唆/リテラシー向上ガイド）
│   ├── 19_snapshot.py            … 処理済み中間データの保存/復元（生データなしで16/17を再生成）
│   ├── 【グループ分け統合（2026-09〜｜旧 AI_User_Group を統合）】
│   ├── grouping_lib.py           … 受験台帳＋複数回判定＋分析指標グループ分け＋取込CSV＋出欠（純関数）
│   ├── 20_exam_ledger.py         … AI資格試験CSV → 受験台帳（追記型・複数回受験対応）
│   ├── 21_grouping.py            … グループ分け（分析指標＋台帳）＋group書き戻し＋管理ツール取込CSV
│   ├── 22_event_attendance.py    … 社内イベント出欠（attendance.db）をemail突合し出欠指標
│   ├── 【一括更新オーケストレーター】
│   ├── update_monthly.py         … 月次フル更新（取込→分類→分析→グループ分け→成果物）
│   ├── update_exam.py            … 試験結果を随時反映（台帳→グループ分け→ダッシュボード）
│   ├── classify_chunks.py        … （任意）新規分類をClaude API(Haiku4.5)で自動化
│   ├── dashboard_all_template.html
│   ├── build_archive.py          … 保持用アーカイブ生成（月別gzipマスタ）
│   ├── classification_prompt.md  … AI分類プロンプト
│   └── 【単月パイプライン（旧・参考）】 01_〜07_ , dashboard_template.html
├── ダッシュボードを開く.cmd / open_dashboard.ps1   … 最新ダッシュボードをブラウザで開く（Python不要）
├── グループ分け結果を開く.cmd / open_grouping.ps1  … 最新グループ分け結果Excelを開く
├── data/   （gitignore: raw_exports/ archive/ 中間JSON・exam_ledger.csv・attendance.db。README.md のみ追跡）
└── output/ 成果物
    ├── エクサベースAI_利用分析_全期間.xlsx
    ├── エクサベースAI_利用分析_ダッシュボード_全期間.html
    ├── グループ分け結果.xlsx（グループ分け結果／イベント出欠×グループ）
    ├── import.csv（ユーザー管理ツール取込用）
    └── （旧・単月）エクサベースAI_利用分析_202607.xlsx / _ダッシュボード.html
```

## クイックスタート（全期間・月次）

```bash
pip install -r requirements.txt
# data/raw_exports/ に月次エクスポート gai-export-*.xlsx（全パート）とメンバー一覧を配置
cd scripts
python 10_ingest.py
python 11_members.py
python 12_classify_prep.py
#   → data/chunks2/c*.json を AI分類し r*.json を得る（scripts/classification_prompt.md）
python 13_merge_classification.py
python 14_analyze.py
python 15_aggregate.py
# 氏名突合（社員一覧CSVを data/raw_exports/社員一覧*.csv に配置）:
python 18_employee_master.py
python 16_build_xlsx.py
python 17_build_dashboard.py
# 保持アーカイブ（任意・推奨）:
python build_archive.py
# 過去データ保存（任意・引き継ぎ/再生成用｜生データ不要で16/17を再現）:
python 19_snapshot.py --zip
#   → data/snapshots/ に処理済み中間データ一式を保存（Box共有）。
#   受領側は: python 19_snapshot.py --restore <zip> → python 16_build_xlsx.py → python 17_build_dashboard.py
```

詳細手順は [`docs/引き継ぎ書.md`](docs/引き継ぎ書.md)、指標定義は [`docs/仕様書.md`](docs/仕様書.md)。

## グループ分け・自動更新（2026-09〜｜旧 AI_User_Group を統合）

ユーザーのグループ分け（コア/ライト/ユーザー）を本ツールに統合した。**利用実績は本ツールの指標
（稼働月正規化の `msgs_per_month`＋リテラシー）を正**とし、AI資格試験は**受験台帳**で複数回受験に
対応（**最新回優先**）。**管理者6名は自動コア**。社内イベント出欠は表示・相関のみ（配分不算入）。
判定ルールの詳細は [`docs/グループ分け仕様.md`](docs/グループ分け仕様.md)。

**更新（作業コスト削減後の運用）**

```bash
cd scripts
# 月初：前月の利用情報(gai-export-*.xlsx 全パート)と最新メンバーエクスポート(gai-members-export-*.xlsx)を
#        data/raw_exports/ に配置してから：
python update_monthly.py            # 取込→(分類ゲート)→分析→グループ分け→成果物＋取込CSV
#   新規プロンプトがある場合：c*.json を分類し r*.json を保存 → python update_monthly.py --resume
#   （または python update_monthly.py --api で Claude API 自動分類）

# 随時：生成AIパスポート試験の結果CSVが出たら：
python update_exam.py <試験結果CSV>   # 受験台帳へ追記→グループ分け→ダッシュボード更新
```

**パイプライン順序**：`10 → 11 → 12 →(分類)→ 13 → 14 → 22 → 21 → 15 → 18 → 16 → 17`。
`21_grouping` が算定したグループを `members.json`/`user_all.json` に書き戻し、以降の集計・
ダッシュボードへ反映する（group は分析計算に不使用の表示用メタのため精度に影響しない）。

**閲覧（Python不要・ダブルクリック）**：`ダッシュボードを開く.cmd` / `グループ分け結果を開く.cmd`。
