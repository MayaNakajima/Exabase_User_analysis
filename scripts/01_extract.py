"""STEP 1: rawエクスポート(xlsx) → 会話単位JSON(data/conversations.json)

エクサベースAIのメッセージ明細(1行=1メッセージ)を会話ID単位に集約し、
パートナー/モデル階層/往復数/使用ツール/初回発話などを付与する。
"""
import json
import re
import statistics
from collections import defaultdict

import openpyxl

from config import DATA, RAW_GLOB


def tier(partner: str) -> str:
    m = re.search(r"/\s*(Economy|Standard|Premium)", str(partner))
    return m.group(1) if m else "Unknown"


def model_short(partner: str) -> str:
    if not partner:
        return "Unknown"
    return str(partner).split("/")[0].strip()


def main():
    raw_files = sorted(DATA.glob(RAW_GLOB))
    if not raw_files:
        raise SystemExit(f"入力ファイルが見つかりません: {DATA}/{RAW_GLOB}")
    src = raw_files[-1]
    print(f"読み込み: {src.name}")

    wb = openpyxl.load_workbook(src, read_only=True)
    ws = wb.worksheets[0]

    convs = {}
    order = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        partner, conv_id, user, ts, role, msg, attach, rating, tool = r
        if not conv_id:
            continue
        c = convs.get(conv_id)
        if c is None:
            c = {
                "conv_id": conv_id, "user": user, "partner": partner,
                "model": model_short(partner), "tier": tier(partner),
                "first_ts": str(ts), "last_ts": str(ts),
                "user_msgs": 0, "asst_msgs": 0, "tools": set(),
                "first_user_msg": None, "user_msg_lens": [], "ratings": [],
            }
            convs[conv_id] = c
            order.append(conv_id)
        c["last_ts"] = str(ts)
        if role == "user":
            c["user_msgs"] += 1
            if msg:
                c["user_msg_lens"].append(len(str(msg)))
                if c["first_user_msg"] is None:
                    c["first_user_msg"] = str(msg)
        elif role == "assistant":
            c["asst_msgs"] += 1
        if tool:
            for t in str(tool).split(","):
                c["tools"].add(t.strip())
        if rating:
            c["ratings"].append(str(rating))

    out = []
    for cid in order:
        c = convs[cid]
        c["tools"] = sorted(c["tools"])
        out.append(c)

    (DATA / "conversations.json").write_text(
        json.dumps(out, ensure_ascii=False), encoding="utf-8")

    turns = [c["user_msgs"] for c in out]
    print(f"会話数: {len(out)} / ユーザー数: {len({c['user'] for c in out})}")
    print(f"平均往復: {statistics.mean(turns):.2f} / 中央値: {statistics.median(turns)}")
    print(f"出力: {DATA/'conversations.json'}")


if __name__ == "__main__":
    main()
