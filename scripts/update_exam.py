"""試験結果アップロード → グループ分け・ダッシュボード更新（随時・軽量）

生成AIパスポート試験の結果CSVを1本渡すと、受験台帳へ追記し、グループ分けと
成果物（Excel・HTMLダッシュボード）を再生成する。利用ログの再取込・AI分類は
行わないため軽量（数秒〜数十秒）。任意のタイミングで実行できる。

使い方:
  python update_exam.py <試験結果CSV> [--date YYYYMMDD] [--snapshot <取込用CSV/xlsx>]
  python update_exam.py <試験結果CSV> --dry-run   # 実行内容の確認のみ
"""
import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
PY = sys.executable


def run(name, args):
    print(f"\n===== {name} {' '.join(args)} =====", flush=True)
    r = subprocess.run([PY, str(SCRIPTS / name), *args], cwd=str(SCRIPTS))
    if r.returncode != 0:
        raise SystemExit(f"[中断] {name} が失敗しました (exit {r.returncode})")


def main():
    ap = argparse.ArgumentParser(description="試験結果→グループ分け・ダッシュボード更新")
    ap.add_argument("exam_csv", help="AI資格試験の結果CSV")
    ap.add_argument("--date", default=None, help="回次(YYYYMMDD)。省略時はファイル名から自動")
    ap.add_argument("--snapshot", default=None, help="管理ツール取込CSVを生成する場合の現行スナップショット")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if not Path(a.exam_csv).exists():
        raise SystemExit(f"試験結果CSVが見つかりません: {a.exam_csv}")

    steps = [
        ("20_exam_ledger.py", [a.exam_csv] + (["--date", a.date] if a.date else [])),
        ("22_event_attendance.py", []),                 # 出欠指標を最新化（任意・軽量）
        ("21_grouping.py", (["--snapshot", a.snapshot] if a.snapshot else [])),
        ("15_aggregate.py", []),                         # 書き戻したグループで再集計
        ("18_employee_master.py", []),
        ("16_build_xlsx.py", []),
        ("17_build_dashboard.py", []),
    ]
    print("試験結果更新プラン:")
    for n, ar in steps:
        print("   -", n, " ".join(ar))
    if a.dry_run:
        return
    for n, ar in steps:
        run(n, ar)
    print("\n✅ 完了: 試験結果を反映し、グループ分け・ダッシュボードを更新しました。")


if __name__ == "__main__":
    main()
