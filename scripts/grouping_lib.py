"""グループ分けライブラリ（分析ツール統合版）

エクサベースAI 利用分析の per-user 指標（data/user_all.json）と在籍情報
（data/members.json）、AI資格試験の受験台帳（data/exam_ledger.csv）を突合し、
利用者を コアユーザー / ライトユーザー / ユーザー の3グループに分類する。

■ 設計方針（2026-09 単一ツール化）
  - 利用実績は分析ツールの指標を「正」とする（稼働月正規化の msgs_per_month・literacy）。
    旧・独立スコアリング（頻度/量/最終ログイン/継続の108点法）は廃止し、本ライブラリへ一本化。
  - 資格試験は複数回受験に対応（受験台帳）。判定は「最新回優先」。
      * 実受験（合格/不合格）が1回でもあれば最新回の結果を採用（過去合格でも最新が不合格なら不合格）。
      * 未受験は結果とみなさない（過去に実受験があればその最新結果を維持）。
      * 実受験ゼロで未受験のみ … 1回=申込済・未受験(猶予) / 2回以上=未受験(常習)。
      * 台帳に一度も無い … 情報なし。
  - コアは「最新回合格」のみ。非合格がコア圏に入ったらライトへ降格（繰り上げなし）。
  - イベント出欠はグループ配分に不算入（分析ダッシュボードの表示・相関でのみ利用）。

このモジュールは副作用を持たない純粋関数群。CLIは 20_exam_ledger.py / 21_grouping.py。
"""
import os
import re
import bisect
import json
import sqlite3
import datetime as dt

import pandas as pd

# ---- グループ・資格ラベル -------------------------------------------------
GROUP_CORE = "コアユーザー"
GROUP_LIGHT = "ライトユーザー"
GROUP_USER = "ユーザー"

EXAM_PASS = "受験済・合格"
EXAM_FAIL = "受験済・不合格"
EXAM_APPLIED = "申込済・未受験（猶予）"
EXAM_NOTTAKEN = "未受験（常習）"
EXAM_NO_INFO = "情報なし"

# ---- 設定 -----------------------------------------------------------------
EXAM_SCORE = {"pass": 8, "fail": 5, "not_taken_grace": 0,
              "not_taken_repeat": -5, "no_info": -5}
DEFAULT_ALLOCATION = {"core": 0.10, "light": 0.35, "user": 0.55}
# エンゲージメントスコアの配点（合計1.0）。
# 方針: ユーザー分析ツールの分析（「利用頻度 × リテラシー」の4象限）をそのまま利用する。
#   freq     = 稼働月正規化の利用頻度 msgs_per_month の百分位（分析ツールの横軸）
#   literacy = リテラシー複合スコア（分析ツールが config.LITERACY_WEIGHTS で算定した縦軸）
#   recency  = 参考情報（既定は配点0＝スコアに不算入。表示のみ）
# 4象限が両軸を対称（各軸の中央値分割）に扱うのに合わせ、freq と literacy は等重み。
ENGAGE_WEIGHTS = {"freq": 0.5, "literacy": 0.5, "recency": 0.0}
# 最終ログイン経過日数 → 直近アクティビティ点（0..100）。既定では配点0のため表示専用。
RECENCY_THRESHOLDS = [(3, 100), (7, 85), (14, 70), (30, 50), (60, 30), (90, 15)]

LEDGER_COLUMNS = ["round_id", "email", "sei", "mei",
                  "status_raw", "status_norm", "source", "imported_at"]


# ==========================================================================
# 受験台帳（複数回受験に対応）
# ==========================================================================
def load_exam_csv(path):
    """AI資格試験の結果CSVを読み込み、email/status_raw(/sei/mei) の DataFrame を返す。
    列名は自動判別（メール列・受験状況/結果列・姓・名）。読めなければ None。"""
    if not path or not os.path.exists(path):
        return None
    ex = None
    for enc in ("utf-8-sig", "cp932", "utf-8"):
        try:
            ex = pd.read_csv(path, encoding=enc, dtype=str)
            break
        except Exception:
            ex = None
    if ex is None:
        return None
    mc = next((c for c in ex.columns if "メール" in str(c) or "mail" in str(c).lower()), None)
    sc = next((c for c in ex.columns if "受験" in str(c) or "状況" in str(c) or "結果" in str(c)), None)
    if mc is None or sc is None:
        return None
    ren = {mc: "email", sc: "status_raw"}
    if "姓" in ex.columns:
        ren["姓"] = "sei"
    if "名" in ex.columns:
        ren["名"] = "mei"
    ex = ex.rename(columns=ren)
    ex["email"] = ex["email"].astype(str).str.strip().str.lower()
    keep = ["email", "status_raw"] + [c for c in ("sei", "mei") if c in ex.columns]
    return ex[keep].dropna(subset=["email"])


def normalize_status(s):
    """生の受験状況文字列を PASS / FAIL / NOTTAKEN の3値に正規化する。
    - 「合格」を含み「不合格」を含まない → PASS
    - 「不合格」を含む                   → FAIL
    - 「未受験」「未ログイン」空欄        → NOTTAKEN（申込はしたが受験していない）
    - その他で「受験」を含む             → FAIL（受験済みだが結果不明は安全側で不合格）
    """
    s = "" if s is None or (isinstance(s, float) and pd.isna(s)) else str(s)
    if "合格" in s and "不合格" not in s:
        return "PASS"
    if "不合格" in s:
        return "FAIL"
    if ("未受験" in s) or ("未ログイン" in s) or (s.strip() == ""):
        return "NOTTAKEN"
    if "受験" in s:
        return "FAIL"
    return "NOTTAKEN"


def exam_round_id(csv_path, exam_date=None):
    """回次ID（YYYYMMDD 文字列＝辞書順で時系列順）を決める。
    exam_date 指定 → その日付 / 無ければファイル名中の YYYYMMDD / それも無ければ本日。"""
    if exam_date:
        d = re.sub(r"\D", "", str(exam_date))
        if len(d) >= 8:
            return d[:8]
        if d:
            return d
    m = re.search(r"(20\d{6})", os.path.basename(str(csv_path)))
    if m:
        return m.group(1)
    return dt.date.today().strftime("%Y%m%d")


def _exam_df_to_ledger_rows(exam_df, round_id, source=""):
    df = exam_df.copy()
    df["round_id"] = str(round_id)
    df["status_norm"] = df["status_raw"].apply(normalize_status)
    for c in ("sei", "mei"):
        if c not in df.columns:
            df[c] = ""
    df["sei"] = df["sei"].fillna("")
    df["mei"] = df["mei"].fillna("")
    df["source"] = source
    df["imported_at"] = dt.datetime.now().isoformat(timespec="seconds")
    return df[LEDGER_COLUMNS]


def load_ledger(ledger_path):
    """受験台帳CSVを読み込む。無ければ None。"""
    if not ledger_path or not os.path.exists(ledger_path):
        return None
    led = None
    for enc in ("utf-8-sig", "cp932", "utf-8"):
        try:
            led = pd.read_csv(ledger_path, encoding=enc, dtype=str)
            break
        except Exception:
            led = None
    if led is None or led.empty:
        return None
    for c in LEDGER_COLUMNS:
        if c not in led.columns:
            led[c] = ""
    led["email"] = led["email"].astype(str).str.strip().str.lower()
    miss = led["status_norm"].isna() | (led["status_norm"].astype(str).str.strip() == "")
    if miss.any():
        led.loc[miss, "status_norm"] = led.loc[miss, "status_raw"].apply(normalize_status)
    return led[LEDGER_COLUMNS]


def update_ledger(exam_csv, ledger_path, exam_date=None):
    """新しい試験結果CSVを受験台帳へ追記（同一 round_id×email は最新で置換）して保存し、
    更新後の台帳DataFrameを返す。"""
    new = load_exam_csv(exam_csv)
    if new is None:
        raise ValueError("試験結果CSVが読めません: %s" % exam_csv)
    rid = exam_round_id(exam_csv, exam_date)
    rows = _exam_df_to_ledger_rows(new, rid, source=os.path.basename(str(exam_csv)))
    led = load_ledger(ledger_path)
    merged = pd.concat([led, rows], ignore_index=True) if led is not None else rows
    merged = merged.drop_duplicates(subset=["round_id", "email"], keep="last")
    merged = merged.sort_values(["email", "round_id"]).reset_index(drop=True)
    if ledger_path:
        merged.to_csv(ledger_path, index=False, encoding="utf-8-sig")
    return merged


def single_csv_to_ledger(exam_csv, exam_date=None):
    """レガシー単発CSVを、保存せずメモリ上の1回分台帳に変換する。"""
    new = load_exam_csv(exam_csv)
    if new is None:
        return None
    rid = exam_round_id(exam_csv, exam_date)
    return _exam_df_to_ledger_rows(new, rid, source=os.path.basename(str(exam_csv)))


def derive_exam_status(ledger, score=None):
    """受験台帳から email→(資格スコア, 資格ラベル) と分析用内訳 detail を導出する。
    戻り値: (status_map, detail_map)
      status_map[email] = (score, label)
      detail_map[email] = {受験回数, 未受験回数, 最新受験回, 初回合格回, 合格までの受験回数}
    """
    c = score or EXAM_SCORE
    p = c.get("pass", 8)
    f = c.get("fail", 5)
    g = c.get("not_taken_grace", 0)
    rpt = c.get("not_taken_repeat", -5)
    ni = c.get("no_info", -5)
    status_map, detail_map = {}, {}
    if ledger is None or len(ledger) == 0:
        return status_map, detail_map
    for email, rows in ledger.groupby("email"):
        rr = rows[rows["status_norm"].isin(["PASS", "FAIL"])].sort_values("round_id")
        n_nt = rows[rows["status_norm"] == "NOTTAKEN"]["round_id"].nunique()
        if not rr.empty:
            latest = rr.iloc[-1]["status_norm"]
            sc, lb = (p, EXAM_PASS) if latest == "PASS" else (f, EXAM_FAIL)
        elif n_nt >= 2:
            sc, lb = rpt, EXAM_NOTTAKEN
        elif n_nt == 1:
            sc, lb = g, EXAM_APPLIED
        else:
            sc, lb = ni, EXAM_NO_INFO
        status_map[email] = (sc, lb)
        passes = rr[rr["status_norm"] == "PASS"].sort_values("round_id")
        attempts_to_pass = ""
        if not passes.empty:
            first_pass_rid = passes.iloc[0]["round_id"]
            attempts_to_pass = int((rr["round_id"] <= first_pass_rid).sum())
        detail_map[email] = {
            "受験回数": int(len(rr)),
            "未受験回数": int(n_nt),
            "最新受験回": (str(rr.iloc[-1]["round_id"]) if not rr.empty else ""),
            "初回合格回": (str(passes.iloc[0]["round_id"]) if not passes.empty else ""),
            "合格までの受験回数": attempts_to_pass,
        }
    return status_map, detail_map


def name_map_from_ledger(ledger):
    """受験台帳の姓名から email→氏名（各人の最新回の姓名）を作る。"""
    m = {}
    if ledger is None or len(ledger) == 0:
        return m
    for email, rows in ledger.sort_values("round_id").groupby("email"):
        last = rows.iloc[-1]
        sei = "" if pd.isna(last.get("sei")) else str(last.get("sei"))
        mei = "" if pd.isna(last.get("mei")) else str(last.get("mei"))
        nm = ("%s%s" % (sei, mei)).strip()
        if nm:
            m[email] = nm
    return m


# ==========================================================================
# エンゲージメントスコア & グループ配分
# ==========================================================================
def _percentiles(vals):
    """各値の百分位（0..100）。同値は右端順位で評価。"""
    s = sorted(vals)
    n = len(s)
    return [(bisect.bisect_right(s, v) / n * 100) if n else 0.0 for v in vals]


def detect_admins(members, admin_users=None, admin_by_owner=True):
    """在籍者から管理者メール集合を判定する（OR条件）。
      1) admin_users に列挙          2) member['is_admin']（サブグループタグ由来）
      3) admin_by_owner かつ 権限=オーナー
    """
    admin_users = set(admin_users or [])
    admins = set()
    for email, m in members.items():
        if email in admin_users:
            admins.add(email)
        elif m.get("is_admin"):
            admins.add(email)
        elif admin_by_owner and str(m.get("permission", "")) == "オーナー":
            admins.add(email)
    return admins


def _recency_score(last_login, ref):
    """最終ログイン日（datetime.date or 'YYYY-MM-DD'）→ 直近アクティビティ点（0..100）。"""
    if not last_login:
        return 0
    if isinstance(last_login, str):
        try:
            last_login = dt.date.fromisoformat(last_login[:10])
        except Exception:
            return 0
    days = (ref - last_login).days
    for lim, pts in RECENCY_THRESHOLDS:
        if days <= lim:
            return pts
    return 0


def compute_grouping(users, members, exam_status_map, exam_detail=None,
                     allocation=None, weights=None, ref_date=None, admins=None):
    """グループ分けを計算して DataFrame を返す。

    users: data/user_all.json のリスト（per-user 指標。'user'=email）
    members: data/members.json の dict（email → {active,last_login,name,...}）
    exam_status_map: derive_exam_status() の status_map
    exam_detail: derive_exam_status() の detail_map（任意・分析列用）
    ref_date: 直近アクティビティの基準日（省略時は members の最終ログイン最大日）
    admins: 管理者メール集合（自動でコア。コア10%枠の母数から除外）。None なら管理者なし。
    """
    allocation = allocation or DEFAULT_ALLOCATION
    weights = weights or ENGAGE_WEIGHTS
    exam_detail = exam_detail or {}
    admins = set(admins or [])

    umap = {u["user"]: u for u in users}
    # 基準日: 明示 → members の last_login 最大 → 本日
    if ref_date is None:
        lls = [m.get("last_login") for m in members.values() if m.get("last_login")]
        dates = []
        for s in lls:
            try:
                dates.append(dt.date.fromisoformat(str(s)[:10]))
            except Exception:
                pass
        ref_date = max(dates) if dates else dt.date.today()
    elif isinstance(ref_date, str):
        ref_date = dt.date.fromisoformat(ref_date[:10])

    # 対象母集団 = メンバー全員（在籍者）。利用指標が無い人は 0 とする。
    rows = []
    for email, mi in members.items():
        u = umap.get(email, {})
        freq = float(u.get("msgs_per_month", 0) or 0)
        lit = float(u.get("literacy", 0) or 0)
        rec = _recency_score(mi.get("last_login"), ref_date)
        name = mi.get("name") or u.get("name") or ""
        sc, label = exam_status_map.get(email, (EXAM_SCORE["no_info"], EXAM_NO_INFO))
        det = exam_detail.get(email, {})
        rows.append({
            "メールアドレス": email,
            "氏名": name,
            "管理者": "管理者" if email in admins else "",
            "利用頻度(月)": round(freq, 2),
            "リテラシー": round(lit, 1),
            "直近点": rec,
            "資格スコア": sc,
            "資格状況": label,
            "受験回数": det.get("受験回数", 0),
            "未受験回数": det.get("未受験回数", 0),
            "最新受験回": det.get("最新受験回", ""),
            "合格までの受験回数": det.get("合格までの受験回数", ""),
            "アカウント状態": "アクティブ" if mi.get("active") else "削除済み",
        })
    df = pd.DataFrame(rows)
    if df.empty:
        df["エンゲージメント"] = []
        df["グループ"] = []
        return df

    # --- エンゲージメントスコア（アクティブのみ百分位化して算出）---
    active_mask = df["アカウント状態"] == "アクティブ"
    act = df[active_mask].copy()
    if not act.empty:
        fp = _percentiles(act["利用頻度(月)"].tolist())
        # リテラシーは既に 0..100 の百分位加重。直近点も 0..100。
        eng = [round(weights["freq"] * fp[i]
                     + weights["literacy"] * act["リテラシー"].iloc[i]
                     + weights["recency"] * act["直近点"].iloc[i], 2)
               for i in range(len(act))]
        act["エンゲージメント"] = eng
    else:
        act["エンゲージメント"] = []
    df = df.merge(act[["メールアドレス", "エンゲージメント"]], on="メールアドレス", how="left")
    df["エンゲージメント"] = df["エンゲージメント"].fillna(0.0)

    # --- 配分 ---
    df = _assign_groups(df, allocation, admins)
    # 並び: グループ→エンゲージメント降順
    order = {GROUP_CORE: 0, GROUP_LIGHT: 1, GROUP_USER: 2}
    df["_o"] = df["グループ"].map(order).fillna(9)
    df = df.sort_values(["_o", "エンゲージメント"], ascending=[True, False]).drop(columns="_o").reset_index(drop=True)
    return df


def _assign_groups(df, allocation, admins=None):
    """グループを配分する。
      - 管理者（admins）は在籍・資格・順位に関わらず自動でコア。10%枠の母数から除外。
      - 管理者を除いた在籍者を エンゲージメント降順に コア10%/ライト35%/ユーザー55% 配分。
      - コアは最新回合格のみ（非合格はライトへ降格。繰り上げなし）。
      - 削除済み（非管理者）は強制ユーザー。
    """
    admins = set(admins or [])
    is_admin = df["メールアドレス"].isin(admins)
    admin_rows = df[is_admin].copy()
    admin_rows["グループ"] = GROUP_CORE  # 自動コア（資格ゲート・在籍を問わない）

    rest = df[~is_admin].copy()
    active = rest[rest["アカウント状態"] == "アクティブ"].copy()
    deleted = rest[rest["アカウント状態"] != "アクティブ"].copy()
    active = active.sort_values("エンゲージメント", ascending=False).reset_index(drop=True)
    n = len(active)  # 管理者を抜いた在籍者数 ＝ 10%枠の母数
    nc = int(round(n * allocation["core"]))
    nl = int(round(n * allocation["light"]))
    grp = [GROUP_CORE if i < nc else GROUP_LIGHT if i < nc + nl else GROUP_USER
           for i in range(n)]
    active["グループ"] = grp
    demote = (active["グループ"] == GROUP_CORE) & (active["資格状況"] != EXAM_PASS)
    active.loc[demote, "グループ"] = GROUP_LIGHT
    deleted["グループ"] = GROUP_USER
    return pd.concat([admin_rows, active, deleted], ignore_index=True)


# ==========================================================================
# 管理ツール取込（アップロード）用CSV生成
# --------------------------------------------------------------------------
#  グループ分け結果の「グループ」を、ユーザー管理ツールの一括登録CSV
#  （action/email/.../subgroup_assignments）に変換する。突合はメールアドレス。
#  管理タグ（user/light-user/core-user）のみ更新し、部署等の他タグは保持する。
# ==========================================================================
GROUP_TO_SUBGROUP = {
    GROUP_CORE:  "onward-cd_core-user",
    GROUP_LIGHT: "onward-cd_light-user",
    GROUP_USER:  "onward-cd_user",
}
MANAGED_SUBGROUPS = set(GROUP_TO_SUBGROUP.values())
# これらのタグ所属者は、どのグループでも管理タグ権限を admin にする（管理者グループ）
ADMIN_GROUPS = {"onward-cd_admin", "onward-cd_DX"}
IMPORT_COLUMNS = ["action", "email", "first_name", "last_name",
                  "profession", "is_active", "group_permission", "subgroup_assignments"]


def _parse_subgroups(s):
    """'name|perm; name2|perm2' を [(name,perm),...] に分解。"""
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return []
    out = []
    for t in str(s).split(";"):
        t = t.strip()
        if not t:
            continue
        if "|" in t:
            n, perm = t.split("|", 1)
            out.append((n.strip(), perm.strip()))
        else:
            out.append((t, ""))
    return out


def _join_subgroups(tokens):
    """(name,perm) のリストを、グループ名の昇順（大小無視）で文字列化。"""
    ts = sorted(tokens, key=lambda x: x[0].lower())
    return "; ".join(("%s|%s" % (n, p)) if p != "" else n for n, p in ts)


def _is_admin_member(tokens, email=None, admins=None):
    """管理者権限(admin)にすべきか。ADMIN_GROUPS タグ所属、または admins 集合に含まれる。"""
    admins = admins or set()
    if email and email in admins:
        return True
    names = {n for n, _ in tokens}
    return any(g in names for g in ADMIN_GROUPS)


def load_members_snapshot(path):
    """現行メンバースナップショットを import 列の DataFrame として読み込む。
    - CSV（action/email/.../subgroup_assignments 列）… そのまま
    - xlsx（メンバーエクスポート: email,first,last,prof,active,gperm,subg,created,last）… 変換
    """
    ext = os.path.splitext(str(path))[1].lower()
    if ext in (".xlsx", ".xls"):
        raw = pd.read_excel(path, dtype=str)
        cols = list(raw.columns)
        # 先頭7列を想定順にマップ（エクスポート仕様準拠）
        m = raw.rename(columns={
            cols[0]: "email", cols[1]: "first_name", cols[2]: "last_name",
            cols[3]: "profession", cols[4]: "is_active", cols[5]: "group_permission",
            cols[6]: "subgroup_assignments"})
        return m[["email", "first_name", "last_name", "profession",
                  "is_active", "group_permission", "subgroup_assignments"]]
    imp = None
    for enc in ("utf-8-sig", "cp932", "utf-8"):
        try:
            imp = pd.read_csv(path, encoding=enc, dtype=str)
            break
        except Exception:
            imp = None
    if imp is None:
        raise ValueError("メンバースナップショットが読めません: %s" % path)
    return imp


def build_import_csv(result_df, snapshot_path, output_path, admins=None):
    """グループ分け結果と現行メンバースナップショットから、管理ツール取込CSVを生成。

    - 突合: メールアドレス（小文字化）
    - subgroup_assignments の管理タグ（user/light-user/core-user）をグループで置換。
      権限は原則 member、ADMIN_GROUPS 所属者/admins は admin。他タグ（部署等）は保持。
    - action: 管理タグが変わった既存→update / 変化なし既存→skip /
              結果にのみ居る新規→create / スナップショットのみ→skip。
    """
    admins = admins or set()
    imp = load_members_snapshot(snapshot_path)

    def key(e):
        return str(e).strip().lower()

    grp_map = {key(e): g for e, g in zip(result_df["メールアドレス"], result_df["グループ"])}
    name_map = {key(e): ("" if pd.isna(n) else str(n))
                for e, n in zip(result_df["メールアドレス"], result_df.get("氏名", ""))}
    state_map = {key(e): str(s) for e, s in
                 zip(result_df["メールアドレス"], result_df.get("アカウント状態", ""))}

    rows, seen = [], set()
    for _, r in imp.iterrows():
        email = r.get("email", "")
        ek = key(email)
        seen.add(ek)
        tokens = _parse_subgroups(r.get("subgroup_assignments", ""))
        perm = "admin" if _is_admin_member(tokens, ek, admins) else "member"
        if ek in grp_map:
            new_name = GROUP_TO_SUBGROUP[grp_map[ek]]
            others = [(n, p) for n, p in tokens if n not in MANAGED_SUBGROUPS]
            new_sub = _join_subgroups(others + [(new_name, perm)])
            old_sub = _join_subgroups(tokens)
            action = "update" if new_sub != old_sub else "skip"
        else:
            new_sub = _join_subgroups(tokens)
            action = "skip"
        rows.append({"action": action, "email": email,
                     "first_name": r.get("first_name", ""), "last_name": r.get("last_name", ""),
                     "profession": r.get("profession", ""), "is_active": r.get("is_active", ""),
                     "group_permission": r.get("group_permission", ""),
                     "subgroup_assignments": new_sub})

    # 結果にのみ存在＝新規 create
    for ek, g in grp_map.items():
        if ek in seen:
            continue
        nm = (name_map.get(ek, "") or "").strip()
        parts = nm.split()
        last = parts[0] if len(parts) >= 1 else ""
        first = parts[1] if len(parts) >= 2 else ""
        is_active = "True" if state_map.get(ek, "") == "アクティブ" else "False"
        perm = "admin" if ek in admins else "member"
        rows.append({"action": "create", "email": ek, "first_name": first, "last_name": last,
                     "profession": "", "is_active": is_active, "group_permission": "メンバー",
                     "subgroup_assignments": "%s|%s" % (GROUP_TO_SUBGROUP[g], perm)})

    out = pd.DataFrame(rows, columns=IMPORT_COLUMNS)
    if output_path:
        out.to_csv(output_path, index=False, encoding="utf-8-sig")
    return out


# ==========================================================================
# 社内イベント出欠（Event-Attendance-Management の SQLite）
# --------------------------------------------------------------------------
#  email 突合でユーザーごとの出欠指標を算出する。表示・相関のみに用い、
#  グループ配分（エンゲージメント）には算入しない。今後イベントが増えても
#  そのまま累積集計される。
# ==========================================================================
ATTEND_PRESENT = ("present", "partial")  # 出席とみなすステータス


def _ekey(e):
    return str(e or "").strip().lower()


def load_event_metrics(db_path):
    """attendance.db から email→出欠指標 と 全体サマリーを返す。
    戻り値: (metrics_by_email, summary)
      metrics_by_email[email] = {
        ev_reg, ev_att, ev_present, ev_partial, ev_noshow, ev_unreg_att,
        ev_rate(0..1 or None), ev_channels(str), ev_last(YYYY-MM-DD)}
      summary = {events_total, attendees_total, registrations_total, db}
    """
    empty = ({}, {"events_total": 0, "attendees_total": 0, "registrations_total": 0, "db": db_path})
    if not db_path or not os.path.exists(db_path):
        return empty
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    try:
        emp = {r[0]: _ekey(r[1]) for r in cur.execute("SELECT id, email FROM employees").fetchall()}
        events = {r[0]: r[1] for r in cur.execute(
            "SELECT id, starts_at FROM events WHERE status!='draft'").fetchall()}
        regs = cur.execute("SELECT employee_id, event_id FROM registrations").fetchall()
        atts = cur.execute(
            "SELECT employee_id, event_id, status, channels FROM attendance_current").fetchall()
    except Exception:
        con.close()
        return empty
    con.close()

    from collections import defaultdict
    reg = defaultdict(set)          # email -> {event_id}
    att = defaultdict(set)          # email -> {event_id}（present/partial）
    present = defaultdict(set)
    partial = defaultdict(set)
    channels = defaultdict(set)
    last_dt = defaultdict(str)

    for eid_emp, ev in regs:
        em = emp.get(eid_emp)
        if em and ev in events:
            reg[em].add(ev)
    for eid_emp, ev, status, chans in atts:
        em = emp.get(eid_emp)
        if not em or ev not in events:
            continue
        if str(status) in ATTEND_PRESENT:
            att[em].add(ev)
            (present if str(status) == "present" else partial)[em].add(ev)
            try:
                for ch in json.loads(chans or "[]"):
                    channels[em].add(str(ch))
            except Exception:
                pass
            d = str(events.get(ev) or "")[:10]
            if d and d > last_dt[em]:
                last_dt[em] = d

    metrics = {}
    for em in set(list(reg) + list(att)):
        rg = reg[em]
        at = att[em]
        n_reg, n_att = len(rg), len(at)
        noshow = len(rg - at)                 # 申込したが未出席
        unreg_att = len(at - rg)              # 申込なしで出席（飛び込み）
        rate = (len(rg & at) / n_reg) if n_reg else None   # 申込に対する出席率
        metrics[em] = {
            "ev_reg": n_reg, "ev_att": n_att,
            "ev_present": len(present[em]), "ev_partial": len(partial[em]),
            "ev_noshow": noshow, "ev_unreg_att": unreg_att,
            "ev_rate": (round(rate, 3) if rate is not None else None),
            "ev_channels": "/".join(sorted(channels[em])),
            "ev_last": last_dt[em],
        }
    summary = {
        "events_total": len(events),
        "attendees_total": sum(1 for m in metrics.values() if m["ev_att"] > 0),
        "registrations_total": sum(len(v) for v in reg.values()),
        "db": db_path,
    }
    return metrics, summary


def event_group_correlation(grouping_df, event_metrics):
    """グループ × 出欠 の相関サマリーを返す（表示用）。
    グループごとに: 人数, 出席者数(≥1), 出席者率, 平均参加数, 申込者数, 平均出席率。
    """
    rows = []
    for g in (GROUP_CORE, GROUP_LIGHT, GROUP_USER):
        sub = grouping_df[grouping_df["グループ"] == g]
        n = len(sub)
        attn = 0
        att_counts = []
        reg_members = 0
        rates = []
        for em in sub["メールアドレス"].map(_ekey):
            m = event_metrics.get(em)
            if not m:
                continue
            if m["ev_att"] > 0:
                attn += 1
                att_counts.append(m["ev_att"])
            if m["ev_reg"] > 0:
                reg_members += 1
                if m["ev_rate"] is not None:
                    rates.append(m["ev_rate"])
        rows.append({
            "グループ": g,
            "人数": n,
            "出席者数": attn,
            "出席者率%": round(attn / n * 100, 1) if n else 0,
            "平均参加イベント数": round(sum(att_counts) / attn, 2) if attn else 0,
            "申込者数": reg_members,
            "平均出席率%": round(sum(rates) / len(rates) * 100, 1) if rates else 0,
        })
    return pd.DataFrame(rows)
