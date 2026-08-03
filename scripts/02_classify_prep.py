"""STEP 2: AI分類用のチャンクファイルを作成(data/chunks/chunk_*.json)

各会話の初回発話(最大400字)と使用ツールを、N分割したJSON配列として書き出す。
このチャンクを AI(サブエージェント) に渡し、docs/引き継ぎ書.md の分類プロンプトで
12カテゴリに分類させ、結果を data/chunks/result_*.json として受け取る。
"""
import json
import math

from config import DATA

N_CHUNKS = 10
MAX_LEN = 400


def main():
    convs = json.loads((DATA / "conversations.json").read_text(encoding="utf-8"))
    items = []
    for c in convs:
        fm = (c["first_user_msg"] or "").replace("\n", " ").replace("\r", " ")
        items.append({"id": c["conv_id"], "q": fm[:MAX_LEN], "tools": ";".join(c["tools"])})

    outdir = DATA / "chunks"
    outdir.mkdir(exist_ok=True)
    per = math.ceil(len(items) / N_CHUNKS)
    for i in range(N_CHUNKS):
        ch = items[i * per:(i + 1) * per]
        if not ch:
            continue
        (outdir / f"chunk_{i}.json").write_text(
            json.dumps(ch, ensure_ascii=False), encoding="utf-8")
        print(f"chunk_{i}.json: {len(ch)}件")
    print(f"合計 {len(items)}件 / 出力先: {outdir}")
    print("→ 次に各chunkをAI分類し result_i.json を同フォルダに保存(引き継ぎ書 参照)")


if __name__ == "__main__":
    main()
