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

# 社内イベント出欠DB（別リポジトリ Event-Attendance-Management の SQLite）。
# email 突合でユーザー分析に出欠指標を付与する（表示・相関のみ／グループ配分には不算入）。
# 環境で差し替え可能なよう、存在すれば data/attendance.db を優先、無ければ既定のBoxパス。
_EVENT_DB_LOCAL = DATA / "attendance.db"
EVENT_DB = str(_EVENT_DB_LOCAL) if _EVENT_DB_LOCAL.exists() else (
    r"C:\Users\612316\Box\事業推進Div□\DX推進課\生成AI\Event-Attendance-Management\data\attendance.db")

# ---- 全期間（月次）パイプライン用 ----
RAW_EXPORTS = Path(r"C:\Users\612316\Box\事業推進Div□\DX推進課\生成AI\00_data")    # 月次xlsx・社員一覧の正本（2026-10 に data/raw_exports から移動）
ARCHIVE = DATA / "archive"            # 月別gzip正規化マスタ（gitignore）
MEMBERS_GLOB = "gai-members-export-*.xlsx"  # メンバー一覧（raw_exports配下）
SHAIN_GLOB = "社員一覧*.csv"  # 人事の社員一覧CSV（氏名突合用, Shift-JIS）。18_employee_master.py が使用

# 管理グループ（メンバー権限のサブグループトークンから判定）
GROUP_LABEL = {"core": "コアユーザー", "light": "ライトユーザー",
               "user": "ユーザー", "none": "未分類", "former": "退職/不明"}

# ---- 管理者（グループ分けで自動コア＆10%母数から除外）----
# 管理者は「自動でコア」。かつコア10%枠は "管理者を除いた在籍者" の上位10%で算定する。
# 判定は次のいずれかに該当する在籍者（OR）:
#   1) ADMIN_USERS に明示列挙されたメール（運用で追記＝最優先・確実）
#   2) メンバーのサブグループタグに ADMIN_SUBGROUPS を含む（11_members が is_admin として付与）
#   3) ADMIN_BY_OWNER=True かつ テナント権限が「オーナー」
ADMIN_SUBGROUPS = {"onward-cd_admin", "onward-cd_DX"}
# エクサベースAIの「管理者グループ」6名（onward-cd_admin / onward-cd_DX 所属。
# 2026-07-14 メンバースナップショット基準）。メンバーエクスポート取込後は
# 11_members の is_admin（タグ由来）でも自動検出されるが、確実性のため明示保持する。
ADMIN_USERS = {
    "a-miyairi@onward.co.jp",
    "k-owa@onward.co.jp",
    "kazunori.matsuyama@onward.co.jp",
    "kentaro.takeishi@onward.co.jp",
    "maya.nakajima@onward.co.jp",
    "t-fujita@onward.co.jp",
}
ADMIN_BY_OWNER = False       # テナント権限=オーナーは管理者としない（管理者はグループ所属で判定）

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

# 高付加価値（高度）ツール。リテラシー・過剰スペック判定に使用。
# 本プロジェクトの唯一の定義元（14/15 もここを import して使用）。
# 注: 画像生成（高速/高性能）は「準備・前処理を要する深い使い方」の signal としては
#     弱く、件数も多いため、高度ツールからは除外している（2026-08）。
#     将来、チャット内容（例: 詳細な指示・反復調整・業務成果物への組込み）に応じて
#     画像生成を高度に分類する改修余地あり。その際はここに条件付きで戻す/別指標化する。
ADV_TOOLS = {
    "Deep Research (詳細)", "文書検索 (RAG)", "スライド作成 (PowerPoint)",
    "ファイル出力 (Word、Excelなど)", "ウェブリサーチ (高速)", "国内記事検索",
    "官公需案件検索", "音声書き起こし", "SharePointファイル検索", "Teams検索",
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
