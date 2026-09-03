"""（任意）AI分類の自動化: data/chunks2/c*.json を Claude API で分類し r*.json を保存。

update_monthly.py --api から呼ばれる。既定の運用（Claude Code 上で分類→--resume）が
使えない場合の自動化オプション。要 `pip install anthropic` と ANTHROPIC_API_KEY。
分類は高頻度・低コストのため Claude Haiku 4.5 を使用。1チャンクを小バッチに分割して
JSONの信頼性を確保する（欠落は STEP13 が C12 で補完し警告）。

使い方:
  python classify_chunks.py [--model claude-haiku-4-5] [--batch 200]
"""
import argparse
import glob
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DATA, CAT_NAMES

VALID = set(CAT_NAMES)  # {'C01',...,'C12'}
PROMPT_PATH = Path(__file__).resolve().parent / "classification_prompt.md"

SYSTEM = """あなたは社内AI利用ログの分類担当です。各要素 {"id":uid,"q":発話} を、q の主目的で
次の12カテゴリのいずれか1つに分類してください。
C01 メール作成・返信・添削 / C02 文章校正・言い換え・敬語 / C03 資料・企画書・スライド作成 /
C04 報告書・議事録作成 / C05 営業戦略・企業リサーチ・ABM分析 / C06 製品・素材・技術の相談 /
C07 画像生成・画像編集 / C08 要約・翻訳・文書処理 / C09 データ・Excel・表・計算 /
C10 IT・ツール操作サポート / C11 アイデア出し・ネーミング・コピー / C12 業務知識・一般調査・その他
出力は {"uid":"C0X", ...} のフラットなJSON辞書のみ（キー=id、値=カテゴリコード）。全件必須、説明不要。"""


def _extract_json(text):
    """応答テキストから最初のJSONオブジェクトを取り出して dict に。失敗時 {}。"""
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return {}
    return {}


def classify_batch(client, model, items):
    msg = client.messages.create(
        model=model, max_tokens=8000,
        system=SYSTEM,
        messages=[{"role": "user", "content": json.dumps(items, ensure_ascii=False)}],
    )
    text = next((b.text for b in msg.content if b.type == "text"), "")
    d = _extract_json(text)
    return {str(k): v for k, v in d.items() if v in VALID}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="claude-haiku-4-5")
    ap.add_argument("--batch", type=int, default=200)
    a = ap.parse_args()

    chunks = sorted(glob.glob(str(DATA / "chunks2" / "c*.json")))
    if not chunks:
        print("[classify] c*.json がありません。分類不要。")
        return

    try:
        import anthropic
    except ImportError:
        print("[classify] anthropic 未インストール。`pip install anthropic` を実行するか、")
        print("           Claude Code 上で c*.json を分類し r*.json を保存→ --resume してください。")
        raise SystemExit(3)

    try:
        client = anthropic.Anthropic()
    except Exception as e:
        print(f"[classify] APIクライアント初期化失敗: {e}")
        print("           ANTHROPIC_API_KEY を設定するか、Claude Code 手動分類→--resume を。")
        raise SystemExit(3)

    total = 0
    for cpath in chunks:
        i = re.search(r"c(\d+)\.json$", cpath).group(1)
        items = json.loads(open(cpath, encoding="utf-8").read())
        result = {}
        for s in range(0, len(items), a.batch):
            sub = items[s:s + a.batch]
            try:
                result.update(classify_batch(client, a.model, sub))
            except anthropic.AuthenticationError:
                print("[classify] 認証エラー: ANTHROPIC_API_KEY を確認してください。")
                raise SystemExit(3)
            except Exception as e:
                print(f"[classify] c{i} バッチ{s}でエラー: {e}（この分は欠落→STEP13でC12補完）")
        rpath = DATA / "chunks2" / f"r{i}.json"
        rpath.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        total += len(result)
        print(f"[classify] c{i}: {len(result)}/{len(items)} 件 → r{i}.json")
    print(f"[classify] 完了: 計 {total} 件を分類。")


if __name__ == "__main__":
    main()
