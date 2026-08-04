"""STEP 7: インタラクティブHTMLダッシュボードを作成
        → output/エクサベースAI_利用分析_ダッシュボード.html

user_rows.json / aggregates.json / meta.json からダッシュボード用の
コンパクトなデータ構造を組み立て、scripts/dashboard_template.html の
DATA_PLACEHOLDER に埋め込んで単一HTMLとして出力する(Chart.jsはCDN)。
"""
import json

from config import DATA, OUTPUT, CAT_NAMES

TEMPLATE = __file__.rsplit("07_", 1)[0] + "dashboard_template.html"


def main():
    rows = json.loads((DATA / "user_rows.json").read_text(encoding="utf-8"))
    agg = json.loads((DATA / "aggregates.json").read_text(encoding="utf-8"))
    meta = json.loads((DATA / "meta.json").read_text(encoding="utf-8"))

    udata = []
    for u in rows:
        tiers = u["tiers"]
        tt = sum(tiers.values()) or 1
        sp = (tiers.get("Standard", 0) + tiers.get("Premium", 0)) / tt * 100
        topcat = max(u["cats"].items(), key=lambda x: x[1])[0] if u["cats"] else "C12"
        udata.append({
            "user": u["user"].split("@")[0], "freq": u["user_msgs"], "convs": u["convs"],
            "lit": u["literacy"], "q": u["quadrant"][:2], "turns": round(u["avg_turns"], 1),
            "adv": round(u["adv_rate"] * 100, 1), "struct": round(u["struct_rate"] * 100, 1),
            "catdiv": u["cat_div"], "ntools": u["distinct_tools"],
            "stdprem": u["std_prem_convs"], "over": u["overspec_convs"],
            "spshare": round(sp, 0), "top": CAT_NAMES[topcat],
        })

    # ダッシュボードが参照するキーに合わせる（agg['cat'] を使用）
    agg_out = dict(agg)
    agg_out["cat"] = agg["cats"]
    data = {"users": udata, "agg": agg_out, "cat": CAT_NAMES, "meta": meta}

    with open(TEMPLATE, encoding="utf-8") as f:
        html = f.read()
    html = html.replace("DATA_PLACEHOLDER", json.dumps(data, ensure_ascii=False))

    outpath = OUTPUT / "エクサベースAI_利用分析_ダッシュボード.html"
    outpath.write_text(html, encoding="utf-8")
    print(f"出力: {outpath} ({len(html)//1024} KB)")


if __name__ == "__main__":
    main()
