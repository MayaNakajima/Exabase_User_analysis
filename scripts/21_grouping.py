"""STEP 21: グループ分け（分析ツール指標 ＋ 受験台帳）

data/user_all.json（per-user 指標）と data/members.json（在籍・最終ログイン）、
data/exam_ledger.csv（受験台帳）から、コア/ライト/ユーザーを配分する。
- 利用実績は分析ツールの指標を優先（msgs_per_month・literacy）
- 資格は最新回優先。コアは最新回合格のみ（非合格はライトへ降格）

出力:
  data/grouping_all.json           … 後段（ダッシュボード）取込用
  output/グループ分け結果.xlsx     … 閲覧・確認用（PII含む・gitignore対象）

使い方:
  python 21_grouping.py [--ledger data/exam_ledger.csv] [--ref YYYY-MM-DD]
"""
import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DATA, OUTPUT, ADMIN_USERS, ADMIN_BY_OWNER
import grouping_lib as gl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default=str(DATA / "exam_ledger.csv"))
    ap.add_argument("--ref", default=None, help="直近アクティビティ基準日(YYYY-MM-DD)。省略時は最終ログイン最大日")
    ap.add_argument("--xlsx", default=str(OUTPUT / "グループ分け結果.xlsx"))
    ap.add_argument("--snapshot", default=None,
                    help="現行メンバースナップショット（import用CSV or メンバーエクスポートxlsx）。指定時に取込CSVを生成")
    ap.add_argument("--import-out", dest="import_out", default=str(OUTPUT / "import.csv"),
                    help="管理ツール取込CSVの出力先")
    ap.add_argument("--no-writeback", action="store_true",
                    help="members.json / user_all.json への group 書き戻しを行わない")
    ap.add_argument("--run-label", default=None,
                    help="履歴の時点ラベル（例 2026-08）。省略時は本日日付。同一ラベルは置換")
    a = ap.parse_args()

    users = json.load(open(DATA / "user_all.json", encoding="utf-8"))
    members = json.load(open(DATA / "members.json", encoding="utf-8"))
    led = gl.load_ledger(a.ledger)
    if led is None:
        print("警告: 受験台帳が見つかりません（全員『情報なし』扱い）:", a.ledger)
    sm, det = gl.derive_exam_status(led)

    admins = gl.detect_admins(members, admin_users=ADMIN_USERS, admin_by_owner=ADMIN_BY_OWNER)
    df = gl.compute_grouping(users, members, sm, det, ref_date=a.ref, admins=admins)

    # イベント出欠指標を付与（表示・相関のみ／配分不算入）。event_metrics.json があれば。
    ev_corr = None
    ev_path = DATA / "event_metrics.json"
    if ev_path.exists():
        ev = json.load(open(ev_path, encoding="utf-8")).get("metrics", {})
        df["参加イベント数"] = df["メールアドレス"].map(lambda e: (ev.get(gl._ekey(e)) or {}).get("ev_att", 0))
        df["申込イベント数"] = df["メールアドレス"].map(lambda e: (ev.get(gl._ekey(e)) or {}).get("ev_reg", 0))
        df["無断欠席数"] = df["メールアドレス"].map(lambda e: (ev.get(gl._ekey(e)) or {}).get("ev_noshow", 0))
        df["出席率"] = df["メールアドレス"].map(lambda e: (ev.get(gl._ekey(e)) or {}).get("ev_rate"))
        ev_corr = gl.event_group_correlation(df, ev)

    recs = df.to_dict(orient="records")
    json.dump(recs, open(DATA / "grouping_all.json", "w", encoding="utf-8"), ensure_ascii=False)

    # グループ分け履歴を追記（時点間の変化を追える）
    run_date, hist_path = gl.append_grouping_history(df, DATA, run_label=a.run_label)
    print(f"履歴追記: {os.path.basename(hist_path)} (run_date={run_date})")

    # --- group を members.json / user_all.json へ書き戻し（15/16/17 が新グループを使用）---
    # group は分析計算（象限・リテラシー）に不使用のため、精度に影響しない表示用メタデータ。
    if not a.no_writeback:
        label_to_code = {gl.GROUP_CORE: "core", gl.GROUP_LIGHT: "light", gl.GROUP_USER: "user"}
        code_map = {str(e).strip().lower(): label_to_code.get(g)
                    for e, g in zip(df["メールアドレス"], df["グループ"]) if label_to_code.get(g)}
        n_m = 0
        for email, code in code_map.items():
            if email in members:
                members[email]["group"] = code
                n_m += 1
        (DATA / "members.json").write_text(json.dumps(members, ensure_ascii=False), encoding="utf-8")
        n_u = 0
        for u in users:
            c = code_map.get(str(u.get("user", "")).strip().lower())
            if c:
                u["group"] = c
                n_u += 1
        json.dump(users, open(DATA / "user_all.json", "w", encoding="utf-8"), ensure_ascii=False)
        print(f"書き戻し: members.json {n_m}件 / user_all.json {n_u}件 の group を更新")
    Path(a.xlsx).parent.mkdir(parents=True, exist_ok=True)
    xlsx_path = a.xlsx

    def _write_xlsx(path):
        with pd.ExcelWriter(path, engine="openpyxl") as wr:
            df.to_excel(wr, sheet_name="グループ分け結果", index=False)
            if ev_corr is not None:
                ev_corr.to_excel(wr, sheet_name="イベント出欠×グループ", index=False)

    try:
        _write_xlsx(xlsx_path)
    except PermissionError:
        # 出力先が Excel で開かれている等でロックされている場合、日時付きの別名に退避出力
        import datetime as _dt
        base, ext = os.path.splitext(a.xlsx)
        xlsx_path = f"{base}_{_dt.datetime.now():%Y%m%d%H%M%S}{ext}"
        _write_xlsx(xlsx_path)
        print(f"警告: {a.xlsx} がロックされていたため {os.path.basename(xlsx_path)} に出力しました。"
              f"（Excelを閉じて再実行すると正式名で保存されます）")

    active = int((df["アカウント状態"] == "アクティブ").sum())
    n_base = int(((df["管理者"] != "管理者") & (df["アカウント状態"] == "アクティブ")).sum())
    print("総数:", len(df), " アクティブ:", active, " 管理者:", len(admins),
          " コア10%母数(管理者除く在籍):", n_base)
    print("管理者:", sorted(admins))
    print("グループ:", dict(Counter(df["グループ"])))
    print("資格:", dict(Counter(df["資格状況"])))
    core = df[df["グループ"] == gl.GROUP_CORE]
    core_admin = int((core["管理者"] == "管理者").sum())
    core_ranked = len(core) - core_admin
    print("コア:", len(core), " = 管理者", core_admin, "+ ランキング", core_ranked)
    nonadmin_core_pass = int((core[core["管理者"] != "管理者"]["資格状況"] == gl.EXAM_PASS).sum())
    print("  ランキングコアの合格:", nonadmin_core_pass, "/", core_ranked, "（＝全員合格であるべき）")
    print("saved:", xlsx_path)
    print("saved: data/grouping_all.json")

    # 管理ツール取込CSV（スナップショット指定時のみ）
    if a.snapshot:
        imp = gl.build_import_csv(df, a.snapshot, a.import_out, admins=admins)
        print("取込CSV action:", dict(Counter(imp["action"])))
        # 検算1: 結果に居る全員が、自分のグループの管理タグを持つ（不一致0であるべき）
        gmap = {str(e).strip().lower(): g for e, g in zip(df["メールアドレス"], df["グループ"])}
        mism = 0
        for _, r in imp.iterrows():
            ek = str(r.get("email", "")).strip().lower()
            if ek in gmap and gl.GROUP_TO_SUBGROUP[gmap[ek]] not in str(r.get("subgroup_assignments", "")):
                mism += 1
        print("  管理タグ不一致:", mism, "(0であるべき)")
        # 検算2: 管理者は取込CSVでも権限 admin
        adm_rows = imp[imp["email"].astype(str).str.strip().str.lower().isin(admins)]
        adm_admin = sum(1 for s in adm_rows["subgroup_assignments"] if "|admin" in str(s))
        print(f"  管理者の権限admin: {adm_admin}/{len(adm_rows)}")
        print("saved:", a.import_out)

    if ev_corr is not None:
        print("\n=== イベント出欠 × グループ ===")
        print(ev_corr.to_string(index=False))


if __name__ == "__main__":
    main()
