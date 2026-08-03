"""STEP 5: 各種クロス集計 → data/aggregates.json

パートナー別・ツール別・カテゴリ別(モデル階層クロス)・4象限別・
過剰スペック候補を集計し、Excel/ダッシュボードの共通データソースを作る。
"""
import json
import statistics
from collections import defaultdict, Counter

from config import DATA, CAT_NAMES, ADV_TOOLS, SIMPLE_CATS, OVERSPEC_MAX_TURNS

QUAD_ORDER = ["Q1_高頻度・高リテラシー", "Q2_高頻度・低リテラシー",
              "Q3_低頻度・高リテラシー", "Q4_低頻度・低リテラシー"]


def main():
    convs = json.loads((DATA / "conversations.json").read_text(encoding="utf-8"))
    cls = json.loads((DATA / "classification.json").read_text(encoding="utf-8"))
    rows = json.loads((DATA / "user_rows.json").read_text(encoding="utf-8"))
    for c in convs:
        c["cat"] = cls.get(c["conv_id"], "C12")

    # パートナー別
    partner = defaultdict(lambda: {"convs": 0, "umsgs": 0, "amsgs": 0, "tier": None, "model": None})
    for c in convs:
        p = partner[c["partner"] or "None"]
        p["convs"] += 1
        p["umsgs"] += c["user_msgs"]
        p["amsgs"] += c["asst_msgs"]
        p["tier"], p["model"] = c["tier"], c["model"]
    partner_list = [{"partner": k, "model": v["model"], "tier": v["tier"], "convs": v["convs"],
                     "user_msgs": v["umsgs"], "asst_msgs": v["amsgs"],
                     "total_msgs": v["umsgs"] + v["amsgs"]} for k, v in partner.items()]
    partner_list.sort(key=lambda x: -x["total_msgs"])

    # ツール別（複合利用は各ツールにカウント）
    tool_convs = Counter()
    for c in convs:
        for t in set(c["tools"]):
            tool_convs[t] += 1
    tool_list = sorted([{"tool": t, "convs": n} for t, n in tool_convs.items()],
                       key=lambda x: -x["convs"])

    # カテゴリ別 + 階層クロス
    cat_tot, cat_msgs = Counter(), Counter()
    cat_tier = defaultdict(Counter)
    for c in convs:
        cat_tot[c["cat"]] += 1
        cat_tier[c["cat"]][c["tier"]] += 1
        cat_msgs[c["cat"]] += c["user_msgs"] + c["asst_msgs"]
    cat_list = [{"code": code, "name": CAT_NAMES[code], "convs": cat_tot.get(code, 0),
                 "msgs": cat_msgs.get(code, 0),
                 "economy": cat_tier[code].get("Economy", 0),
                 "standard": cat_tier[code].get("Standard", 0),
                 "premium": cat_tier[code].get("Premium", 0)} for code in CAT_NAMES]
    cat_list.sort(key=lambda x: -x["convs"])

    # 4象限別
    quad = defaultdict(lambda: {"users": 0, "convs": 0, "msgs": 0, "lit": [], "turns": [],
                                "advrate": [], "overspec": 0, "stdprem": 0})
    for r in rows:
        q = quad[r["quadrant"]]
        q["users"] += 1
        q["convs"] += r["convs"]
        q["msgs"] += r["user_msgs"]
        q["lit"].append(r["literacy"])
        q["turns"].append(r["avg_turns"])
        q["advrate"].append(r["adv_rate"])
        q["overspec"] += r["overspec_convs"]
        q["stdprem"] += r["std_prem_convs"]
    quad_list = [{"quadrant": q, "users": quad[q]["users"], "convs": quad[q]["convs"],
                  "msgs": quad[q]["msgs"],
                  "avg_lit": round(statistics.mean(quad[q]["lit"]), 1) if quad[q]["lit"] else 0,
                  "avg_turns": round(statistics.mean(quad[q]["turns"]), 2) if quad[q]["turns"] else 0,
                  "avg_advrate": round(statistics.mean(quad[q]["advrate"]) * 100, 1) if quad[q]["advrate"] else 0,
                  "overspec": quad[q]["overspec"], "stdprem": quad[q]["stdprem"]} for q in QUAD_ORDER]

    # 過剰スペック候補
    overspec = []
    for c in convs:
        if (c["tier"] in ("Standard", "Premium") and c["cat"] in SIMPLE_CATS
                and c["user_msgs"] <= OVERSPEC_MAX_TURNS
                and not any(t in ADV_TOOLS for t in c["tools"])):
            overspec.append({"user": c["user"], "model": c["model"], "tier": c["tier"],
                             "cat": c["cat"], "catname": CAT_NAMES[c["cat"]],
                             "q": (c["first_user_msg"] or "")[:90]})

    agg = {"partners": partner_list, "tools": tool_list, "cats": cat_list, "quads": quad_list,
           "overspec_count": len(overspec), "overspec": overspec,
           "totals": {"convs": len(convs), "users": len(rows),
                      "umsgs": sum(c["user_msgs"] for c in convs),
                      "amsgs": sum(c["asst_msgs"] for c in convs)}}
    (DATA / "aggregates.json").write_text(json.dumps(agg, ensure_ascii=False), encoding="utf-8")
    print(f"パートナー{len(partner_list)} / ツール{len(tool_list)} / カテゴリ{len(cat_list)} / 過剰候補{len(overspec)}")
    print(f"出力: {DATA/'aggregates.json'}")


if __name__ == "__main__":
    main()
