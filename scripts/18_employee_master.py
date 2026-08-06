"""STEP 18: 社員一覧CSV → data/employee_master.json（メール突合用の氏名マスタ）

人事の社員一覧CSV（Shift-JIS / cp932）をメールアドレスをキーに読み込み、
ダッシュボード・Excelで表示する **氏名（漢字）・カナ・部署・役職** の
突合マスタ `data/employee_master.json` を生成する。

- 入力: data/raw_exports/社員一覧*.csv（複数可）。**新しい年のファイルを優先**し、
  古い年のファイルは退職者などの補完に使う（＝新→古の順にマージし、既存キーは上書きしない）。
- 列はヘッダー名で動的にマッピングするため、年によって列位置がずれても追従する。
- グループ（コア/ライト/ユーザー）は人事CSVには無い（エクサベース権限由来）ため、
  ここでは扱わない。氏名等の表示情報のみを供給する。

このマスタは 16_build_xlsx / 17_build_dashboard がメールで突合して利用する。
"""
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DATA, RAW_EXPORTS, SHAIN_GLOB


def find_col(header, *keys, exact=None):
    """ヘッダー行から、部分一致（keys）または完全一致（exact）で列indexを返す。無ければ-1。"""
    if exact:
        for i, h in enumerate(header):
            if h.strip() == exact:
                return i
    for i, h in enumerate(header):
        hs = h.strip()
        if any(k in hs for k in keys):
            return i
    return -1


def load_csv(path):
    """1つの社員一覧CSVを {email(lower): info} で返す。"""
    with open(path, encoding="cp932", newline="") as fh:
        rd = list(csv.reader(fh))
    if not rd:
        return {}
    h = rd[0]
    c = {
        "email": find_col(h, "メール", "mail"),
        "sei": find_col(h, exact="姓"),
        "mei": find_col(h, exact="名"),
        "sei_kana": find_col(h, "姓（カナ）", "姓(カナ)"),
        "mei_kana": find_col(h, "名（カナ）", "名(カナ)"),
        "group": find_col(h, exact="グループ"),
        "div": find_col(h, "Div"),
        "bu": find_col(h, exact="部"),
        "ka": find_col(h, exact="課"),
        "title": find_col(h, "役職"),
        "shokushu": find_col(h, "職種"),
        "zaiseki": find_col(h, "在籍"),
    }
    if c["email"] < 0:
        raise SystemExit(f"メール列が見つかりません: {path.name} / header={h}")

    def g(row, key):
        i = c[key]
        return row[i].strip() if 0 <= i < len(row) and row[i] else ""

    out = {}
    for row in rd[1:]:
        email = g(row, "email").lower()
        if not email or "@" not in email:
            continue
        name = (g(row, "sei") + " " + g(row, "mei")).strip()
        kana = (g(row, "sei_kana") + " " + g(row, "mei_kana")).strip()
        # 部署 = 組織グループ / Div. / 部 / 課 を非空だけ連結
        dept = " ".join(x for x in [g(row, "group"), g(row, "div"), g(row, "bu"), g(row, "ka")] if x)
        out[email] = {
            "name": name,
            "kana": kana,
            "dept": dept,
            "title": g(row, "title") or g(row, "shokushu"),
            "hr_status": g(row, "zaiseki"),
        }
    return out


def main():
    files = sorted(RAW_EXPORTS.glob(SHAIN_GLOB))
    if not files:
        raise SystemExit(f"社員一覧CSVなし: {RAW_EXPORTS}/{SHAIN_GLOB}")
    # 新しい年（ファイル名末尾の年が大きい）を優先。sortedは昇順なので新→古へ処理し、
    # 既存キーは上書きしない（＝新しい年の情報を優先）。
    def year_key(p):
        m = re.search(r"(20\d{2})", p.name)
        return int(m.group(1)) if m else 0
    files = sorted(files, key=year_key, reverse=True)

    master = {}
    for f in files:
        d = load_csv(f)
        added = 0
        for email, info in d.items():
            if email not in master and info["name"]:
                master[email] = info
                added += 1
        print(f"  {f.name}: {len(d)}件読込 → 新規{added}件（優先: 先に読んだファイル）")

    (DATA / "employee_master.json").write_text(
        json.dumps(master, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"employee_master.json = {len(master)}件（source: {[f.name for f in files]}）")


if __name__ == "__main__":
    main()
