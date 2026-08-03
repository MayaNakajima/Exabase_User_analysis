"""STEP 12: AI分類用チャンクを作成（重複初回発話を排除して効率化）
        → data/chunks2/c*.json, data/uid_map.json

初回発話を正規化して一意化し、ユニークな発話だけをN分割して出力する。
各ユニーク発話に整数uidを振り、uid→会話IDリストを uid_map.json に保存。
分類後は uid 単位の結果を STEP13 が全会話へ展開する。
"""
import json
import math
import re

from config import DATA

N_CHUNKS = 30
MAX_LEN = 200


def norm(s):
    return re.sub(r"\s+", "", s)[:120] if s else ""


def main():
    conv = json.loads((DATA / "conversations_all.json").read_text(encoding="utf-8"))
    key2convs, key2msg = {}, {}
    for c in conv:
        k = norm(c["first_user_msg"])
        key2convs.setdefault(k, []).append(c["conv_id"])
        if k not in key2msg:
            key2msg[k] = c["first_user_msg"] or ""
    uid_map, items = {}, []
    for uid, k in enumerate(key2convs):
        uid_map[str(uid)] = key2convs[k]
        msg = (key2msg[k] or "").replace("\n", " ").replace("\r", " ")[:MAX_LEN]
        items.append({"id": uid, "q": msg})
    (DATA / "uid_map.json").write_text(json.dumps(uid_map, ensure_ascii=False), encoding="utf-8")

    outdir = DATA / "chunks2"
    outdir.mkdir(exist_ok=True)
    per = math.ceil(len(items) / N_CHUNKS)
    for i in range(N_CHUNKS):
        ch = items[i * per:(i + 1) * per]
        if ch:
            (outdir / f"c{i}.json").write_text(json.dumps(ch, ensure_ascii=False), encoding="utf-8")
    print(f"unique first-msgs={len(items)} chunks={N_CHUNKS} per~{per}")
    print("→ 各 c*.json をAI分類し r*.json を同フォルダへ（scripts/classification_prompt.md）")


if __name__ == "__main__":
    main()
