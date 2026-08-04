"""STEP 4: リテラシー複合スコア算出 + 4象限分類 → data/user_rows.json, data/meta.json

会話データと分類結果から、ユーザーごとの各種指標を集計し、
6指標の百分位を加重平均してリテラシースコア(0-100)を算出。
利用頻度(発話数)とリテラシーそれぞれの中央値で4象限に分類する。
相関(頻度・リテラシー・従量課金選択・高度ツール)も出力する。
"""
import bisect
import json
import math
import re
import statistics
from collections import defaultdict, Counter

from config import (DATA, CAT_NAMES, ADV_TOOLS, SIMPLE_CATS,
                    LITERACY_WEIGHTS, OVERSPEC_MAX_TURNS)


def is_structured(msg: str) -> bool:
    if not msg:
        return False
    if re.search(r"あなたは.{0,20}(専門家|プロ|コピーライター|リサーチャー|コンサル)", msg):
        return True
    if re.search(r"(^|\n)\s*(\d+[\.\)、]|[・\-*#【])", msg):
        return True
    if re.search(r"(条件|前提|背景|目的|制約|フォーマット|以下の|＃|#)", msg) and len(msg) > 120:
        return True
    return False


def pctl_rank(vals):
    srt = sorted(vals)
    n = len(srt)
    return [bisect.bisect_right(srt, v) / n * 100 for v in vals]


def corr(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return cov / (sx * sy) if sx and sy else 0


def main():
    convs = json.loads((DATA / "conversations.json").read_text(encoding="utf-8"))
    cls = json.loads((DATA / "classification.json").read_text(encoding="utf-8"))
    for c in convs:
        c["cat"] = cls.get(c["conv_id"], "C12")

    users = defaultdict(lambda: {
        "convs": 0, "user_msgs": 0, "asst_msgs": 0, "turn_list": [],
        "tools": Counter(), "adv_tool_convs": 0, "tool_convs": 0,
        "partners": Counter(), "tiers": Counter(), "cats": Counter(),
        "first_lens": [], "structured": 0, "std_prem_convs": 0, "overspec_convs": 0,
    })

    for c in convs:
        u = users[c["user"]]
        u["convs"] += 1
        u["user_msgs"] += c["user_msgs"]
        u["asst_msgs"] += c["asst_msgs"]
        u["turn_list"].append(c["user_msgs"])
        u["partners"][c["model"]] += 1
        u["tiers"][c["tier"]] += c["user_msgs"]  # 発話数で重み付け
        u["cats"][c["cat"]] += 1
        fm = c["first_user_msg"] or ""
        u["first_lens"].append(len(fm))
        if is_structured(fm):
            u["structured"] += 1
        if c["tools"]:
            u["tool_convs"] += 1
            for t in c["tools"]:
                u["tools"][t] += 1
            if any(t in ADV_TOOLS for t in c["tools"]):
                u["adv_tool_convs"] += 1
        if c["tier"] in ("Standard", "Premium"):
            u["std_prem_convs"] += 1
            if (c["cat"] in SIMPLE_CATS and c["user_msgs"] <= OVERSPEC_MAX_TURNS
                    and not any(t in ADV_TOOLS for t in c["tools"])):
                u["overspec_convs"] += 1

    rows = []
    for name, u in users.items():
        n = u["convs"]
        rows.append({
            "user": name, "convs": n, "user_msgs": u["user_msgs"],
            "avg_turns": statistics.mean(u["turn_list"]),
            "avg_len": statistics.mean(u["first_lens"]) if u["first_lens"] else 0,
            "tool_rate": u["tool_convs"] / n,
            "adv_rate": u["adv_tool_convs"] / n,
            "cat_div": len(u["cats"]),
            "struct_rate": u["structured"] / n,
            "distinct_tools": len(u["tools"]),
            "std_prem_convs": u["std_prem_convs"],
            "overspec_convs": u["overspec_convs"],
            "tiers": dict(u["tiers"]), "partners": dict(u["partners"]),
            "cats": dict(u["cats"]), "tools": dict(u["tools"]),
        })

    # 各指標を百分位化
    for key in ["avg_turns", "avg_len", "adv_rate", "cat_div", "struct_rate", "distinct_tools"]:
        pr = pctl_rank([r[key] for r in rows])
        for r, p in zip(rows, pr):
            r["_" + key] = p

    # 加重平均でリテラシースコア
    for r in rows:
        r["literacy"] = round(sum(r[k] * w for k, w in LITERACY_WEIGHTS.items()), 1)

    freqs = [r["user_msgs"] for r in rows]
    lit = [r["literacy"] for r in rows]
    med_freq = statistics.median(freqs)
    med_lit = statistics.median(lit)

    for r in rows:
        hi_f = r["user_msgs"] >= med_freq
        hi_l = r["literacy"] >= med_lit
        if hi_f and hi_l:
            r["quadrant"] = "Q1_高頻度・高リテラシー"
        elif hi_f and not hi_l:
            r["quadrant"] = "Q2_高頻度・低リテラシー"
        elif not hi_f and hi_l:
            r["quadrant"] = "Q3_低頻度・高リテラシー"
        else:
            r["quadrant"] = "Q4_低頻度・低リテラシー"
        tot = sum(r["tiers"].values()) or 1
        r["std_prem_share"] = (r["tiers"].get("Standard", 0) + r["tiers"].get("Premium", 0)) / tot

    print(f"中央値 頻度: {med_freq} / リテラシー: {med_lit}")
    for q, n in sorted(Counter(r["quadrant"] for r in rows).items()):
        print(f"  {q}: {n}")
    print("--- 相関 ---")
    print(f"  頻度×リテラシー: {corr(freqs, lit):.3f}")
    print(f"  リテラシー×Std/Prem発話比率: {corr(lit, [r['std_prem_share'] for r in rows]):.3f}")
    print(f"  リテラシー×高度ツール率: {corr(lit, [r['adv_rate'] for r in rows]):.3f}")
    print(f"  リテラシー×平均往復: {corr(lit, [r['avg_turns'] for r in rows]):.3f}")

    (DATA / "user_rows.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    (DATA / "meta.json").write_text(json.dumps(
        {"med_freq": med_freq, "med_lit": med_lit, "cat_names": CAT_NAMES},
        ensure_ascii=False), encoding="utf-8")
    print(f"出力: {DATA/'user_rows.json'}, {DATA/'meta.json'}")


if __name__ == "__main__":
    main()
