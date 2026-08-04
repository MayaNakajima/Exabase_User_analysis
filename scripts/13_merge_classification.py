"""STEP 13: AI分類結果を蓄積ストアに統合し全会話へ展開（差分運用対応）
        → data/classification_store.json（更新）, data/classification_all.json

処理:
1. data/chunks2/r*.json（uid→カテゴリ）を読み、uid_key.json で正規化キーに変換して
   data/classification_store.json（キー→カテゴリ）へ**追記更新**する。
2. conversations_all.json の全会話について、正規化キーで store を引き、
   会話ID→カテゴリ（classification_all.json）を生成する。

新規キーが無い月でも、store から全会話へ再展開されるため常に完全な分類が得られる。
"""
import glob
import json
from collections import Counter

from config import DATA, CAT_NAMES, norm_key


def main():
    store_path = DATA / "classification_store.json"
    store = json.loads(store_path.read_text(encoding="utf-8")) if store_path.exists() else {}

    uid_key_path = DATA / "uid_key.json"
    uid_key = json.loads(uid_key_path.read_text(encoding="utf-8")) if uid_key_path.exists() else {}

    # 新規分類結果を store に反映
    added = 0
    for p in sorted(glob.glob(str(DATA / "chunks2" / "r*.json"))):
        d = json.loads(open(p, encoding="utf-8").read())
        if isinstance(d, dict):
            for uid, cat in d.items():
                if cat in CAT_NAMES and str(uid) in uid_key:
                    store[uid_key[str(uid)]] = cat
                    added += 1
        elif isinstance(d, list):
            for it in d:
                uid = str(it.get("id"))
                cat = it.get("カテゴリ") or it.get("category")
                if cat in CAT_NAMES and uid in uid_key:
                    store[uid_key[uid]] = cat
                    added += 1
    store_path.write_text(json.dumps(store, ensure_ascii=False), encoding="utf-8")

    # 全会話へ展開
    conv = json.loads((DATA / "conversations_all.json").read_text(encoding="utf-8"))
    conv_cls = {}
    fallback = 0
    for c in conv:
        k = norm_key(c["first_user_msg"])
        cat = store.get(k)
        if cat is None:
            cat = "C12"
            fallback += 1
        conv_cls[c["conv_id"]] = cat
    (DATA / "classification_all.json").write_text(json.dumps(conv_cls, ensure_ascii=False), encoding="utf-8")

    print(f"store更新: +{added}件 / storeキー総数={len(store)}")
    print(f"全会話={len(conv)} / 未分類フォールバック(C12)={fallback}")
    if fallback:
        print("  ※ フォールバックがある場合は、STEP12で新規キーの分類漏れが無いか確認。")
    dist = Counter(conv_cls.values())
    for code in sorted(dist):
        print(f"  {code} {CAT_NAMES[code]}: {dist[code]}")


if __name__ == "__main__":
    main()
