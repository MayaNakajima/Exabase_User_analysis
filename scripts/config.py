"""共通設定・定数定義。

エクサベースAI 利用実態分析パイプラインの共通パス・カテゴリ・
リテラシースコア重み・過剰スペック判定条件をここに集約する。
"""
import re
from pathlib import Path


def norm_key(s):
    """初回発話を正規化した分類キー（差分分類の突合キー）。
    空白を除去し先頭120文字。STEP12/13で共通利用する。"""
    return re.sub(r"\s+", "", s)[:120] if s else ""

# ---- パス ----
BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"        # 入力(raw export)と中間ファイル置き場（gitignore対象）
OUTPUT = BASE / "output"    # 最終成果物（xlsx / html）

# 入力エクスポートのファイル名パターン（data/ 配下）
RAW_GLOB = "gai-export-*.xlsx"

# ---- 全期間（月次）パイプライン用 ----
RAW_EXPORTS = DATA / "raw_exports"    # 月次xlsxの正本アーカイブ（gitignore）
ARCHIVE = DATA / "archive"            # 月別gzip正規化マスタ（gitignore）
MEMBERS_GLOB = "gai-members-export-*.xlsx"  # メンバー一覧（raw_exports配下）
SHAIN_GLOB = "社員一覧*.csv"  # 人事の社員一覧CSV（氏名突合用, Shift-JIS）。18_employee_master.py が使用

# 管理グループ（メンバー権限のサブグループトークンから判定）
GROUP_LABEL = {"core": "コアユーザー", "light": "ライトユーザー",
               "user": "ユーザー", "none": "未分類", "former": "退職/不明"}

# Claude（Claude Code含む）利用許可者。高度用途はClaudeにオフロードするため
# ExaBaseの上位モデル利用・リテラシー解釈に注記し、過剰スペック集計から除外する
CLAUDE_USERS = {
    "a-miyairi@onward.co.jp",
    "kazunori.matsuyama@onward.co.jp",
    "kentaro.takeishi@onward.co.jp",
    "maya.nakajima@onward.co.jp",
}

# ---- チャット内容 12分類 ----
CAT_NAMES = {
    "C01": "メール作成・返信・添削",
    "C02": "文章校正・言い換え・敬語",
    "C03": "資料・企画書・スライド作成",
    "C04": "報告書・議事録作成",
    "C05": "営業戦略・企業リサーチ・ABM分析",
    "C06": "製品・素材・技術の相談",
    "C07": "画像生成・画像編集",
    "C08": "要約・翻訳・文書処理",
    "C09": "データ・Excel・表・計算",
    "C10": "IT・ツール操作サポート",
    "C11": "アイデア出し・ネーミング・コピー",
    "C12": "業務知識・一般調査・その他",
}

# 高付加価値（高度）ツール。リテラシー・過剰スペック判定に使用
ADV_TOOLS = {
    "Deep Research (詳細)", "文書検索 (RAG)", "スライド作成 (PowerPoint)",
    "ファイル出力 (Word、Excelなど)", "ウェブリサーチ (高速)", "国内記事検索",
    "官公需案件検索", "音声書き起こし", "画像生成 (高性能, GPT-image)",
    "画像生成 (高速, Nano Banana)", "SharePointファイル検索", "Teams検索",
    "Outlookカレンダー予定確認", "Box検索", "ヘルプページ検索",
}

# 単純用途カテゴリ（従量課金が過剰になりやすい）
SIMPLE_CATS = {"C01", "C02", "C11", "C12"}

# リテラシー複合スコアの重み（合計1.0）。各指標は169名内の百分位に変換後に加重平均
LITERACY_WEIGHTS = {
    "_avg_turns": 0.18,      # 会話の深さ（1会話あたり平均往復）
    "_avg_len": 0.18,        # プロンプト具体性（初回発話の平均文字数）
    "_adv_rate": 0.20,       # 高度ツール活用率
    "_cat_div": 0.16,        # 用途の多様性（利用カテゴリ数）
    "_struct_rate": 0.18,    # 構造化プロンプト率
    "_distinct_tools": 0.10, # 利用ツール種類数
}

# 過剰スペック判定: Standard/Premium かつ 単純カテゴリ かつ 往復<=この値 かつ 高度ツール未使用
OVERSPEC_MAX_TURNS = 2

# ---- 評価バイアス補正（リテラシー指標の水増し・手戻りを相殺）----
# 会話の深さ補正: 「やり直し/空振り」を示すユーザー発話を検出し、往復数から除外する。
# 目的＝AIの失敗による手戻り（例:「回答が希望と違う」「やり直して」）を、
# 建設的な深掘りと同一視しないため。検出は10_ingest.pyで会話ごとに集計する。
REWORK_PAT = re.compile(
    r"(やり直|やりなお|もう一度|もういちど|再度|再作成|作り直|作りなお|書き直|書きなお|"
    r"違う|ちがう|そうじゃ|そうでは|ダメ|だめ|エラー|失敗|反映され|うまくいか|"
    r"できてい?ない|なってい?ない|表示されな|直ってい?ない|希望と|イメージと)")

# プロンプト水増し補正: 同一の初回発話（正規化キー）を TEMPLATE_MIN_USERS 人以上が共有する場合、
# テンプレート/エージェント由来とみなし、具体性(初回文字数)・構造化率の加点対象から除外する。
# 目的＝本人の作文力ではなく定型文/AIガイドに由来する長さ・構造を、本人のリテラシーとして評価しないため。
TEMPLATE_MIN_USERS = 3
