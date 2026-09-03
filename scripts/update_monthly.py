"""月次データ更新 → 全分析・グループ分け・ダッシュボードを一括更新（フル精度）

前月の利用情報(2_*.xlsx)とメンバーエクスポート(gai-members-export-*.xlsx)を
data/raw_exports/ に置いてから実行する。利用ログの取込からAI分類・分析・
グループ分け・成果物生成までを1コマンドで回す。AI分類は「更新時にフル実行」。

■ AI分類ゲート（高度分析）
  分類は増分・キャッシュ式（classification_store.json）。新規プロンプトが
  0件なら分類不要で全自動。新規があれば data/chunks2/c*.json を生成して一旦停止する。
    - Claude Code 上での運用: 生成された c*.json を classification_prompt.md に従い
      分類して r*.json を保存 → 本スクリプトを --resume で再実行。
    - --api 指定時: classify_chunks.py（Claude API）で自動分類を試みる（要 ANTHROPIC_API_KEY）。

使い方:
  python update_monthly.py                 # 取込→(分類ゲート)→分析→グループ分け→成果物
  python update_monthly.py --resume        # 分類(r*.json)完了後に再開
  python update_monthly.py --api           # 新規分類を Claude API で自動化（任意）
  python update_monthly.py --dry-run       # 実行内容の確認のみ
  python update_monthly.py --skip-archive  # 保持アーカイブ生成を省略
"""
import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
from config import DATA, RAW_EXPORTS, RAW_GLOB, MEMBERS_GLOB

PY = sys.executable
CHUNK_DIR = DATA / "chunks2"


def preflight():
    """月次更新に必要な入力が raw_exports に揃っているか確認する。"""
    problems = []
    if not list(RAW_EXPORTS.glob(RAW_GLOB)):
        problems.append(f"利用情報エクスポートなし: {RAW_EXPORTS}/{RAW_GLOB}")
    if not list(RAW_EXPORTS.glob(MEMBERS_GLOB)):
        problems.append(f"メンバーエクスポートなし: {RAW_EXPORTS}/{MEMBERS_GLOB}")
    if problems:
        print("[入力チェック] 月次更新の前に、data/raw_exports/ へ次を配置してください:")
        for p in problems:
            print("   -", p)
        print("  ・前月の利用情報 gai-export-YYYY_MM_01-YYYY_MM_31.xlsx（全パート）")
        print("  ・最新のメンバーエクスポート gai-members-export-*.xlsx")
        raise SystemExit(2)

PRE = [("10_ingest.py", []), ("11_members.py", []), ("12_classify_prep.py", [])]
POST = [
    ("13_merge_classification.py", []),
    ("14_analyze.py", []),
    ("22_event_attendance.py", []),   # 出欠指標（email突合・表示/相関のみ）
    ("21_grouping.py", []),           # グループ分け（分析指標＋受験台帳）＋group書き戻し
    ("15_aggregate.py", []),          # 月次推移・グループ×象限（新グループで）
    ("18_employee_master.py", []),    # 氏名突合
    ("16_build_xlsx.py", []),         # Excel
    ("17_build_dashboard.py", []),    # HTMLダッシュボード
]


def run(name, args):
    print(f"\n===== {name} {' '.join(args)} =====", flush=True)
    r = subprocess.run([PY, str(SCRIPTS / name), *args], cwd=str(SCRIPTS))
    if r.returncode != 0:
        raise SystemExit(f"[中断] {name} が失敗しました (exit {r.returncode})")


def pending_chunks():
    return sorted(CHUNK_DIR.glob("c*.json"))


def results_ready():
    """c*.json に対応する r*.json が揃っているか。"""
    cs = {p.name[1:] for p in CHUNK_DIR.glob("c*.json")}   # '0.json' 等
    rs = {p.name[1:] for p in CHUNK_DIR.glob("r*.json")}
    return cs and cs.issubset(rs)


def main():
    ap = argparse.ArgumentParser(description="月次データ更新の一括実行")
    ap.add_argument("--resume", action="store_true", help="分類(r*.json)完了後に13以降を再開")
    ap.add_argument("--api", action="store_true", help="新規分類を Claude API で自動化（要APIキー）")
    ap.add_argument("--skip-archive", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if a.dry_run:
        print("月次更新プラン:")
        if not a.resume:
            for n, ar in PRE:
                print("   -", n, " ".join(ar))
            print("   - [分類ゲート] 新規プロンプトがあれば classify（--api）or 手動→--resume")
        for n, ar in POST:
            print("   -", n, " ".join(ar))
        if not a.skip_archive:
            print("   - build_archive.py")
        return

    if not a.resume:
        preflight()
        for n, ar in PRE:
            run(n, ar)
        chunks = pending_chunks()
        if chunks:
            print(f"\n[分類ゲート] 新規プロンプト {len(chunks)} チャンク（data/chunks2/c*.json）")
            if a.api:
                run("classify_chunks.py", [])
            else:
                print("  高度AI分析（分類）が必要です。次のいずれかを実施してください:")
                print("   A) Claude Code で c*.json を classification_prompt.md に従い分類し r*.json を保存")
                print("      → その後 `python update_monthly.py --resume` を実行")
                print("   B) `python update_monthly.py --api`（Claude APIで自動分類・要 ANTHROPIC_API_KEY）")
                return
        else:
            print("\n[分類ゲート] 新規プロンプト0件。分類はキャッシュから再展開（全自動）。")
    else:
        if pending_chunks() and not results_ready():
            raise SystemExit("[中断] c*.json に対する r*.json が不足。分類を完了してから --resume してください。")

    # 月次では最新メンバーエクスポートをスナップショットに、管理ツール取込CSVも生成する
    snaps = sorted(RAW_EXPORTS.glob(MEMBERS_GLOB))
    snap = str(snaps[-1]) if snaps else None
    for n, ar in POST:
        if n == "21_grouping.py" and snap:
            run(n, ar + ["--snapshot", snap])
        else:
            run(n, ar)
    if not a.skip_archive:
        run("build_archive.py", [])
    print("\n✅ 完了: 月次更新（分析・グループ分け・ダッシュボード）を反映しました。")
    print("   成果物: output/ 配下（Excel・HTMLダッシュボード・グループ分け結果・import.csv）")


if __name__ == "__main__":
    main()
