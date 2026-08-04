"""STEP 10（全期間パイプライン）: 月次xlsxを統合 → data/conversations_all.json

data/raw_exports/ の gai-export-*.xlsx を全て読み、メッセージを重複排除して
会話単位に集約。会話には first_ts から算出した month(YYYY-MM) を付与する。
エクスポートは3万行上限で分割されることがあるため、必ず全パートを揃えること。
（ローカル実行は時間制限なし。サンドボックス等で遅い場合はファイル単位に分割実行）
"""
import json
import re

import openpyxl

from config import DATA, RAW_EXPORTS, RAW_GLOB


def tier(p):
    m = re.search(r"/\s*(Economy|Standard|Premium)", str(p))
    return m.group(1) if m else "Unknown"


def model_short(p):
    return "Unknown" if not p else str(p).split("/")[0].strip()


def main():
    files = sorted(RAW_EXPORTS.glob(RAW_GLOB))
    if not files:
        raise SystemExit(f"入力なし: {RAW_EXPORTS}/{RAW_GLOB}")
    seen = set()
    convs = {}
    order = []
    total = dup = 0
    for f in files:
        wb = openpyxl.load_workbook(f, read_only=True)
        ws = wb.worksheets[0]
        for i, r in enumerate(ws.iter_rows(values_only=True)):
            if i == 0:
                continue
            partner, conv_id, user, ts, role, msg, attach, rating, tool = r[:9]
            if not conv_id:
                continue
            total += 1
            umsg = str(msg)[:400] if (role == "user" and msg) else ""
            key = (conv_id, str(ts), str(role), umsg[:60])
            if key in seen:
                dup += 1
                continue
            seen.add(key)
            c = convs.get(conv_id)
            if c is None:
                c = {"conv_id": conv_id, "user": user, "partner": partner,
                     "model": model_short(partner), "tier": tier(partner),
                     "first_ts": str(ts), "user_msgs": 0, "asst_msgs": 0,
                     "tools": set(), "first_user_ts": None, "first_user_msg": None, "first_len": 0}
                convs[conv_id] = c
                order.append(conv_id)
            if str(ts) < c["first_ts"]:
                c["first_ts"] = str(ts)
            if role == "user":
                c["user_msgs"] += 1
                if umsg and (c["first_user_ts"] is None or str(ts) < c["first_user_ts"]):
                    c["first_user_ts"] = str(ts)
                    c["first_user_msg"] = umsg
                    c["first_len"] = len(umsg)
            elif role == "assistant":
                c["asst_msgs"] += 1
            if tool:
                for t in str(tool).split(","):
                    t = t.strip()
                    if t:
                        c["tools"].add(t)
        wb.close()
        print("done", f.name)

    out = []
    for cid in order:
        c = convs[cid]
        c["tools"] = sorted(c["tools"])
        c["month"] = c["first_ts"][:7]
        c.pop("first_user_ts", None)
        out.append(c)
    (DATA / "conversations_all.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")

    from collections import Counter
    mc = Counter(c["month"] for c in out)
    print(f"msg={total} dup={dup} conversations={len(out)} months={len(mc)}")
    for m in sorted(mc):
        print(" ", m, mc[m])
    print(f"users={len({c['user'] for c in out if c['user']})}")


if __name__ == "__main__":
    main()
