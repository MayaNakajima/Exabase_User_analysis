"""STEP 13: AI分類結果をマージ・会話へ展開 → data/classification_all.json

data/chunks2/r*.json（uid→カテゴリ）を統合し、uid_map で全会話IDへ展開。
未分類は C12 で補完し、全会話をカバーしているか検証する。
"""
import glob
import json
from collections import Counter

from config import DATA, CAT_NAMES


def main():
    uid_map = json.loads((DATA / "uid_map.json").read_text(encoding="utf-8"))
    uid2cat = {}
    for p in sorted(glob.glob(str(DATA / "chunks2" / "r*.json"))):
        d = json.loads(open(p, encoding="utf-8").read())
        if isinstance(d, dict):
            for k, v in d.items():
                if isinstance(v, str) and v in CAT_NAMES:
                    uid2cat[str(k)] = v
        elif isinstance(d, list):
            for it in d:
                uid2cat[str(it.get("id"))] = it.get("カテゴリ") or it.get("category")

    conv_cls = {}
    for uid, cids in uid_map.items():
        cat = uid2cat.get(str(uid), "C12")
        for cid in cids:
            conv_cls[cid] = cat

    conv = json.loads((DATA / "conversations_all.json").read_text(encoding="utf-8"))
    for c in conv:
        conv_cls.setdefault(c["conv_id"], "C12")
    cov = sum(1 for c in conv if c["conv_id"] in conv_cls)

    (DATA / "classification_all.json").write_text(json.dumps(conv_cls, ensure_ascii=False), encoding="utf-8")
    print(f"uid classified={len(uid2cat)}/{len(uid_map)} convs={len(conv)} covered={cov}")
    dist = Counter(conv_cls[c["conv_id"]] for c in conv)
    for k in sorted(dist):
        print(f"  {k} {CAT_NAMES[k]}: {dist[k]}")


if __name__ == "__main__":
    main()
