"""STEP 11: メンバー一覧を整備 → data/members.json

data/raw_exports/ のメンバーエクスポートから、グループ(core/light/user)、
在籍状態(active)、作成日・最終ログイン、Claude併用フラグを抽出する。
"""
import json
import re

import openpyxl

from config import DATA, RAW_EXPORTS, MEMBERS_GLOB, CLAUDE_USERS


def group_of(subg):
    s = str(subg)
    if "core-user" in s:
        return "core"
    if "light-user" in s:
        return "light"
    if re.search(r"onward-cd_user\b", s):
        return "user"
    return "none"


def main():
    files = sorted(RAW_EXPORTS.glob(MEMBERS_GLOB))
    if not files:
        raise SystemExit(f"メンバー一覧なし: {RAW_EXPORTS}/{MEMBERS_GLOB}")
    src = files[-1]  # 最新
    wb = openpyxl.load_workbook(src, read_only=True)
    ws = wb.worksheets[0]
    members = {}
    for i, r in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue
        email, fn, ln, prof, act, gperm, subg, created, last = r[:9]
        if not email:
            continue
        email = str(email).strip()
        members[email] = {
            "email": email,
            "name": (str(ln) if ln else "") + (str(fn) if fn else ""),
            "active": (str(act) == "True"),
            "permission": str(gperm) if gperm else "",
            "group": group_of(subg),
            "created_at": str(created)[:10] if created else "",
            "last_login": str(last)[:10] if last else "",
            "claude": email in CLAUDE_USERS,
        }
    (DATA / "members.json").write_text(json.dumps(members, ensure_ascii=False), encoding="utf-8")
    from collections import Counter
    print(f"members={len(members)} (src={src.name})")
    print("group:", dict(Counter(m["group"] for m in members.values())))
    print("active:", dict(Counter(m["active"] for m in members.values())))
    print("claude:", [e for e, m in members.items() if m["claude"]])


if __name__ == "__main__":
    main()
