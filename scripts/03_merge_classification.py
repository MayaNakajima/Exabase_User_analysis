"""STEP 3: AI分類結果をマージ・検証 → data/classification.json

data/chunks/result_*.json を集約し、{会話ID: カテゴリコード} の辞書に統合する。
出力形式ゆれ(フラット辞書 / リスト形式)を吸収し、全会話をカバーしているか検証する。
"""
import json

from config import DATA, CAT_NAMES


def main():
    chunkdir = DATA / "chunks"
    mapping = {}
    for p in sorted(chunkdir.glob("result_*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(d, dict):
            for k, v in d.items():
                if isinstance(v, str) and v.startswith("C"):
                    mapping[k] = v
        elif isinstance(d, list):
            for it in d:
                cid = it.get("会話ID") or it.get("id")
                code = it.get("カテゴリ") or it.get("category")
                if cid and code:
                    mapping[cid] = code

    convs = json.loads((DATA / "conversations.json").read_text(encoding="utf-8"))
    ids = {c["conv_id"] for c in convs}
    missing = ids - set(mapping)
    extra = set(mapping) - ids
    bad = {k: v for k, v in mapping.items() if v not in CAT_NAMES}

    print(f"分類済: {len(mapping)} / 会話: {len(ids)}")
    print(f"未分類: {len(missing)} / 余分: {len(extra)} / 不正コード: {len(bad)}")
    if missing:
        print("※ 未分類の会話があります。C12(その他)で補完します:", list(missing)[:5])
        for cid in missing:
            mapping[cid] = "C12"

    (DATA / "classification.json").write_text(
        json.dumps(mapping, ensure_ascii=False), encoding="utf-8")

    from collections import Counter
    for code, n in sorted(Counter(mapping.values()).items()):
        print(f"  {code} {CAT_NAMES.get(code,'?')}: {n}")
    print(f"出力: {DATA/'classification.json'}")


if __name__ == "__main__":
    main()
