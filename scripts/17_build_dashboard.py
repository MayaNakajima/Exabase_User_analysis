"""STEP 17: 経時ダッシュボード → output/エクサベースAI_利用分析_ダッシュボード_全期間.html

data/aggregates_all.json + data/user_all.json + data/meta_all.json から
ダッシュボード用のコンパクトなデータを組み立て、scripts/dashboard_all_template.html
の DATA_PLACEHOLDER に埋め込んで単一HTMLとして出力する（Chart.jsはCDN）。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DATA, OUTPUT

TEMPLATE = Path(__file__).resolve().parent / "dashboard_all_template.html"


def main():
    agg = json.loads((DATA / "aggregates_all.json").read_text(encoding="utf-8"))
    rows = json.loads((DATA / "user_all.json").read_text(encoding="utf-8"))
    meta = json.loads((DATA / "meta_all.json").read_text(encoding="utf-8"))
    CATN, GL = meta["cat_names"], meta["grp_label"]

    ud = []
    for u in rows:
        topcat = max(u["cats"].items(), key=lambda x: x[1])[0] if u["cats"] else "C12"
        ud.append({"user": u["user"].split("@")[0], "name": u["name"], "group": u["group"],
                   "claude": u["claude"], "active": u["active"], "convs": u["convs"], "msgs": u["umsgs"],
                   "mpm": round(u["msgs_per_month"], 1), "lit": u["literacy"], "q": u["quadrant"],
                   "am": u["active_months"], "adv": round(u["adv_rate"] * 100, 1),
                   "sp": round(u["sp_share"] * 100), "over": u["overspec"],
                   "fm": u["first_month"], "lm": u["last_month"], "top": CATN[topcat]})

    data = {"totals": agg["totals"], "monthly": agg["monthly"], "monthly_group": agg["monthly_group"],
            "quads": agg["quads"], "groupquad": agg["groupquad"], "cats": agg["cats"],
            "partners": [p for p in agg["partners"] if p["partner"] != "None"], "tools": agg["tools"][:16],
            "claude_users": agg["claude_users"], "overspec_count": agg["overspec_count"],
            "users": ud, "catnames": CATN, "grplabel": GL,
            "median_freq": meta["median_freq"], "median_lit": meta["median_lit"]}

    html = TEMPLATE.read_text(encoding="utf-8").replace("DATA_PLACEHOLDER", json.dumps(data, ensure_ascii=False))
    out = OUTPUT / "エクサベースAI_利用分析_ダッシュボード_全期間.html"
    out.write_text(html, encoding="utf-8")
    print(f"出力: {out} ({len(html)//1024} KB)")


if __name__ == "__main__":
    main()
