"""STEP 20: AI資格試験結果CSV → data/exam_ledger.csv（受験台帳・追記型）

任意タイミングで新しい試験回の結果を台帳へ追記する（複数回受験対応）。
同一 round_id×email は最新で置換。回次(round_id)は --date、無ければCSVファイル名の
YYYYMMDD、それも無ければ本日。

使い方:
  python 20_exam_ledger.py <試験結果CSV> [--date YYYYMMDD] [--ledger data/exam_ledger.csv]
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DATA
import grouping_lib as gl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", help="AI資格試験の結果CSV")
    ap.add_argument("--date", default=None, help="回次(YYYYMMDD)。省略時はファイル名から自動判別")
    ap.add_argument("--ledger", default=str(DATA / "exam_ledger.csv"))
    a = ap.parse_args()

    led = gl.update_ledger(a.csv, a.ledger, a.date)
    sm, _ = gl.derive_exam_status(led)
    print("台帳件数:", len(led), " 対象者:", led["email"].nunique())
    print("回次:", sorted(led["round_id"].unique()))
    print("資格内訳:", dict(Counter(v[1] for v in sm.values())))
    print("saved:", a.ledger)


if __name__ == "__main__":
    main()
