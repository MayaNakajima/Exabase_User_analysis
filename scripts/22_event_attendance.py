"""STEP 22: 社内イベント出欠 → data/event_metrics.json

Event-Attendance-Management の attendance.db を email 突合し、ユーザーごとの
出欠指標（申込数・参加数・出席率・無断欠席・チャネル・最終参加）を算出する。
出欠は表示・相関のみに用い、グループ配分（エンゲージメント）には算入しない。

- data/event_metrics.json … email→指標（21_grouping / ダッシュボードが利用）
- user_all.json にも ev_* を付与（存在すれば・加算的で分析計算には不使用）

使い方:
  python 22_event_attendance.py [--db <attendance.db>]
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DATA, EVENT_DB
import grouping_lib as gl

EV_FIELDS = ["ev_reg", "ev_att", "ev_present", "ev_partial",
             "ev_noshow", "ev_unreg_att", "ev_rate", "ev_channels", "ev_last"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=EVENT_DB, help="attendance.db のパス")
    a = ap.parse_args()

    metrics, summary = gl.load_event_metrics(a.db)
    if not metrics:
        print("警告: 出欠データが取得できません（DB無し/空）:", a.db)
    json.dump({"summary": summary, "metrics": metrics},
              open(DATA / "event_metrics.json", "w", encoding="utf-8"), ensure_ascii=False)

    print("DB:", summary["db"])
    print("イベント数:", summary["events_total"],
          " 申込延べ:", summary["registrations_total"],
          " 出席者(≥1):", summary["attendees_total"])
    print("参加回数分布:", dict(Counter(m["ev_att"] for m in metrics.values())))

    # user_all.json に ev_* を付与（存在時のみ・加算的）
    ua_path = DATA / "user_all.json"
    if ua_path.exists():
        users = json.load(open(ua_path, encoding="utf-8"))
        n = 0
        for u in users:
            m = metrics.get(gl._ekey(u.get("user")))
            if m:
                u.update({k: m[k] for k in EV_FIELDS})
                n += 1
            else:
                u.setdefault("ev_att", 0)
                u.setdefault("ev_reg", 0)
        json.dump(users, open(ua_path, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"user_all.json に出欠付与: {n}名")

    # グループ相関（grouping_all.json があれば）
    ga_path = DATA / "grouping_all.json"
    if ga_path.exists():
        import pandas as pd
        gdf = pd.DataFrame(json.load(open(ga_path, encoding="utf-8")))
        corr = gl.event_group_correlation(gdf, metrics)
        print("\n=== グループ × 出欠 ===")
        print(corr.to_string(index=False))
    print("\nsaved: data/event_metrics.json")


if __name__ == "__main__":
    main()
