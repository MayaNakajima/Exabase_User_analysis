"""グループ分け履歴（data/grouping_history.csv）から2時点のグループ変更者を一覧化する。

グループ分けは 21_grouping 実行のたびに履歴へ追記される。本ツールはアプリ本体を変えずに、
任意の2時点の差分（誰がどのグループへ移ったか）をCSVで出す。

使い方:
  python grouping_diff.py                      # 最新2時点を比較
  python grouping_diff.py --from 2026-07 --to 2026-08
  python grouping_diff.py --list               # 記録されている時点(run_date)一覧
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DATA, OUTPUT
import grouping_lib as gl
import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="frm", default=None, help="比較元の run_date（例 2026-07）")
    ap.add_argument("--to", dest="to", default=None, help="比較先の run_date（例 2026-08）")
    ap.add_argument("--list", action="store_true", help="記録済みの時点を一覧表示")
    ap.add_argument("--out", default=None, help="出力CSVパス（省略時は output/ に自動命名）")
    a = ap.parse_args()

    hist_path = DATA / "grouping_history.csv"
    if not hist_path.exists():
        print("履歴がありません（21_grouping を実行すると作成されます）:", hist_path)
        return
    if a.list:
        h = pd.read_csv(hist_path, encoding="utf-8-sig", dtype=str)
        from collections import Counter
        print("記録済みの時点(run_date) と人数:")
        for r in sorted(h["run_date"].unique()):
            print("  ", r, int((h["run_date"] == r).sum()), "名")
        return

    runs, diff, _ = gl.diff_grouping_history(DATA, a.frm, a.to)
    if diff is None:
        print("比較できる時点が不足しています（2時点以上必要）。現在の時点:", runs)
        return
    frm, to = runs
    up = int((diff["方向"] == "上位化").sum()) if len(diff) else 0
    down = int((diff["方向"] == "下位化").sum()) if len(diff) else 0
    print(f"=== {frm} → {to} グループ変更 {len(diff)}名（上位化 {up} / 下位化 {down}）===")
    if len(diff):
        print(diff.to_string(index=False))
    out = a.out or str(OUTPUT / f"グループ変更_{frm}_to_{to}.csv")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    diff.to_csv(out, index=False, encoding="utf-8-sig")
    print("\nsaved:", out)


if __name__ == "__main__":
    main()
