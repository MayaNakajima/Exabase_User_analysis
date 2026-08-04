"""STEP 12: AI分類用チャンクを作成（差分運用対応）
        → data/chunks2/c*.json, data/uid_map.json, data/uid_key.json

初回発話を正規化キー(config.norm_key)で一意化し、
**まだ分類していないキーだけ**をN分割して出力する（差分運用）。
過去に分類済みのキーは data/classification_store.json に蓄積されており、
それに無いキー（＝新規プロンプト）のみを対象にする。

- 初回実行（store無し）：全ユニークキーが対象（従来どおり全件分類）。
- 2回目以降：新規キーのみ。テンプレ再利用の多い実運用では対象が大きく減る。
- 新規キーが0件の場合：チャンクは作られず、STEP13でstoreから全会話へ再展開するだけ。

各チャンク要素は {"id": 整数uid, "q": 発話}。分類結果は r<i>.json（uid→カテゴリ）。
uid→正規化キーの対応は uid_key.json に保存し、STEP13がstoreを更新するのに使う。
"""
import json
import math

from config import DATA, norm_key

MAX_LEN = 200
CHUNK_SIZE = 900   # 1チャンクあたりの目安件数（新規件数に応じてチャンク数は自動調整）
MAX_CHUNKS = 40


def main():
    conv = json.loads((DATA / "conversations_all.json").read_text(encoding="utf-8"))
    store_path = DATA / "classification_store.json"
    store = json.loads(store_path.read_text(encoding="utf-8")) if store_path.exists() else {}

    key2msg = {}
    keys = []
    seen = set()
    for c in conv:
        k = norm_key(c["first_user_msg"])
        if k not in seen:
            seen.add(k)
            keys.append(k)
            key2msg[k] = c["first_user_msg"] or ""

    new_keys = [k for k in keys if k not in store]
    reused = len(keys) - len(new_keys)

    # 出力ディレクトリを掃除（前月の残りチャンクを消す）
    outdir = DATA / "chunks2"
    outdir.mkdir(exist_ok=True)
    for p in list(outdir.glob("c*.json")) + list(outdir.glob("r*.json")):
        try:
            p.unlink()
        except OSError:
            pass

    uid_key = {}
    items = []
    for uid, k in enumerate(new_keys):
        uid_key[str(uid)] = k
        msg = (key2msg[k] or "").replace("\n", " ").replace("\r", " ")[:MAX_LEN]
        items.append({"id": uid, "q": msg})
    (DATA / "uid_key.json").write_text(json.dumps(uid_key, ensure_ascii=False), encoding="utf-8")
    # uid_map（uid→会話ID群）も後方互換のため出力
    key2convs = {}
    for c in conv:
        key2convs.setdefault(norm_key(c["first_user_msg"]), []).append(c["conv_id"])
    uid_map = {str(uid): key2convs[k] for uid, k in enumerate(new_keys)}
    (DATA / "uid_map.json").write_text(json.dumps(uid_map, ensure_ascii=False), encoding="utf-8")

    if items:
        n_chunks = min(MAX_CHUNKS, max(1, math.ceil(len(items) / CHUNK_SIZE)))
        per = math.ceil(len(items) / n_chunks)
        for i in range(n_chunks):
            ch = items[i * per:(i + 1) * per]
            if ch:
                (outdir / f"c{i}.json").write_text(json.dumps(ch, ensure_ascii=False), encoding="utf-8")
        print(f"ユニークキー={len(keys)} / 分類済(再利用)={reused} / 新規={len(new_keys)} → chunks={n_chunks}")
        print("→ data/chunks2/c*.json をAI分類し r*.json を保存（scripts/classification_prompt.md）")
    else:
        print(f"ユニークキー={len(keys)} / 全て分類済み（新規0）。チャンク生成なし。")
        print("→ そのまま STEP13 を実行すれば store から全会話へ再展開されます。")


if __name__ == "__main__":
    main()
