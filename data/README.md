# data/ フォルダ

このフォルダには**生データと中間生成ファイル**を置く。いずれも
**個人情報（社員メールアドレス）とチャット本文を含む**ため、
`.gitignore` によりGit管理対象外（この README のみ追跡）。

## 置くもの

| ファイル | 生成元 | 内容 |
|---|---|---|
| `gai-export-YYYY_MM_DD-YYYY_MM_DD.xlsx` | 手動配置（エクサベースAI管理画面からエクスポート） | 入力の生ログ（1行=1メッセージ） |
| `conversations.json` | STEP1 | 会話単位に集約したデータ |
| `chunks/chunk_*.json` | STEP2 | AI分類用の入力チャンク |
| `chunks/result_*.json` | AI分類（手動/サブエージェント） | 分類結果 |
| `classification.json` | STEP3 | 会話ID→カテゴリの統合マップ（単月版） |
| `classification_store.json` | STEP12/13 | 正規化キー→カテゴリの**蓄積ストア**（差分分類の要。月をまたいで再利用） |
| `uid_key.json` | STEP12 | uid→正規化キー（STEP13がstore更新に使用） |
| `classification_all.json` | STEP13 | 会話ID→カテゴリ（全期間版） |
| `user_rows.json` | STEP4 | ユーザー別の指標・リテラシースコア・象限 |
| `meta.json` | STEP4 | 中央値・カテゴリ名 |
| `aggregates.json` | STEP5 | 各種クロス集計 |

## 使い方

新しい月次エクスポートを分析する場合は、`gai-export-*.xlsx` をここに置いて
`scripts/` の STEP1〜STEP7 を順に実行する（詳細は `docs/引き継ぎ書.md`）。
