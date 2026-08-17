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

    # 社員一覧マスタ（18_employee_master.py が生成）をメールで突合して氏名等を上書き。
    # 未生成でも動くようフォールバックする。
    emp_path = DATA / "employee_master.json"
    EMP = json.loads(emp_path.read_text(encoding="utf-8")) if emp_path.exists() else {}

    matched = 0
    ud = []
    for u in rows:
        topcat = max(u["cats"].items(), key=lambda x: x[1])[0] if u["cats"] else "C12"
        email = u["user"].lower()
        local = u["user"].split("@")[0]
        e = EMP.get(email)
        if e:
            matched += 1
        # 表示氏名: 社員マスタ(漢字) > 既存name > メールローカル部
        name = (e["name"] if e and e.get("name") else "") or u.get("name") or local
        ud.append({"user": local, "email": email, "name": name,
                   "kana": (e.get("kana") if e else "") or "",
                   "dept": (e.get("dept") if e else "") or "",
                   "title": (e.get("title") if e else "") or "",
                   "group": u["group"],
                   "claude": u["claude"], "active": u["active"], "convs": u["convs"], "msgs": u["umsgs"],
                   "mpm": round(u["msgs_per_month"], 1), "lit": u["literacy"], "q": u["quadrant"],
                   "am": u["active_months"], "adv": round(u["adv_rate"] * 100, 1),
                   "sp": round(u["sp_share"] * 100), "over": u["overspec"],
                   "fm": u["first_month"], "lm": u["last_month"], "top": CATN[topcat],
                   # リテラシー6サブ指標（内訳表示・向上余地の可視化用）
                   "turns": round(u["avg_turns"], 1), "plen": round(u["avg_len"]),
                   "struct": round(u["struct_rate"] * 100), "catdiv": u["cat_div"],
                   "tools": u["distinct_tools"],
                   # 補正の可視化: 手戻り率・テンプレ率
                   "rework": round(u.get("rework_rate", 0) * 100), "tmpl": round(u.get("tmpl_rate", 0) * 100)})
    print(f"社員マスタ突合: {matched}/{len(rows)}名（未突合はメール表示でフォールバック）")

    data = {"totals": agg["totals"], "monthly": agg["monthly"], "monthly_group": agg["monthly_group"],
            "quads": agg["quads"], "groupquad": agg["groupquad"], "cats": agg["cats"],
            "usage_trend": agg["usage_trend"], "partner_trend": agg["partner_trend"], "tool_trend": agg["tool_trend"],
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
