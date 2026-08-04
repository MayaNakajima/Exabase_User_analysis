"""保持用アーカイブ生成（メッセージ全保持）
   data/raw_exports/gai-export-*.xlsx → data/archive/messages_YYYY-MM.jsonl.gz + manifest.json

全メッセージ（全カラム・全文）を重複排除し、月別にgzip圧縮したNDJSONとして保存する
「正規化マスタ」を作る。これが検索・再分析用の単一の真実源。原本xlsx（raw_exports/）は
最終的な正本として別途保持し、本マスタは原本からいつでも再生成できる。

追記運用: 新しい月次エクスポートを data/raw_exports/ に置いて本スクリプトを再実行すれば、
重複排除により該当月のマスタが更新される（既存分と重複するメッセージは自動で除外）。

※ ローカル実行は時間制限なし。サンドボックス等で大きいファイルが遅い場合は
   ファイル単位に分割して実行しても結果は同じ（月別ファイルへ追記マージ）。

出力レコード（配列）:
  [チャットパートナー, 会話ID, ユーザー, 時間, 役, メッセージ全文, 添付, 評価, 利用ツール]
"""
import gzip
import json
from collections import defaultdict

import openpyxl

from config import RAW_EXPORTS, ARCHIVE, RAW_GLOB


def main():
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    files = sorted(RAW_EXPORTS.glob(RAW_GLOB))
    if not files:
        raise SystemExit(f"入力なし: {RAW_EXPORTS}/{RAW_GLOB}")

    # 既存マスタを読み込み、重複排除キーの集合を復元（追記運用に対応）
    seen = set()
    bymonth = defaultdict(list)
    for gz in sorted(ARCHIVE.glob("messages_*.jsonl.gz")):
        mo = gz.name[len("messages_"):-len(".jsonl.gz")]
        for line in gzip.open(gz, "rt", encoding="utf-8"):
            rec = json.loads(line)
            bymonth[mo].append(rec)
            seen.add((rec[1], rec[3], rec[4], (rec[5] or "")[:60]))

    added = 0
    for f in files:
        wb = openpyxl.load_workbook(f, read_only=True)
        ws = wb.worksheets[0]
        for i, r in enumerate(ws.iter_rows(values_only=True)):
            if i == 0:
                continue
            partner, conv_id, user, ts, role, msg, attach, rating, tool = r[:9]
            if not conv_id:
                continue
            ts = str(ts)
            msg = str(msg) if msg is not None else ""
            key = (conv_id, ts, str(role), msg[:60])
            if key in seen:
                continue
            seen.add(key)
            rec = [partner, conv_id, user, ts, role, msg,
                   str(attach) if attach else "", str(rating) if rating else "",
                   str(tool) if tool else ""]
            bymonth[ts[:7]].append(rec)
            added += 1
        wb.close()
        print("scanned", f.name)

    total = 0
    for mo, recs in sorted(bymonth.items()):
        recs.sort(key=lambda x: x[3])  # by timestamp
        with gzip.open(ARCHIVE / f"messages_{mo}.jsonl.gz", "wt", encoding="utf-8") as w:
            for rec in recs:
                w.write(json.dumps(rec, ensure_ascii=False) + "\n")
        total += len(recs)

    manifest = {"sources": [f.name for f in files], "months": sorted(bymonth),
                "total_messages": total, "added_this_run": added}
    (ARCHIVE / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"archive months={len(bymonth)} total_messages={total} added={added}")
    print(f"→ {ARCHIVE}")


if __name__ == "__main__":
    main()
