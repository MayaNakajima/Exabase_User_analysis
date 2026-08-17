"""STEP 19: 処理済み中間データのスナップショット保存／復元。

目的
----
毎月の分析は「20以上の月次エクスポート(生データ)＋社員CSV」を集め、10〜18の
重い工程（取込・重複排除・AI分類・分析・集計）を通して成果物(16 Excel / 17 HTML)を作る。
別担当や引き継ぎ先が「生データ一式を準備し直す」手間を省けるよう、ビルド工程 16/17 が
実際に読み込む処理済みJSON一式だけを、年月付きスナップショットとして保存する。

スナップショットを受け取った人は、生データを一切集めずに
    19_snapshot.py --restore <PATH>  →  16_build_xlsx.py  →  17_build_dashboard.py
を実行するだけで、保存時点と同一の最新Excel/ダッシュボードを再生成できる。

対象ファイル（16/17 の入力そのもの）
    aggregates_all.json / user_all.json / meta_all.json / employee_master.json(任意)

保存先とPII
    data/snapshots/ 配下（data/* はGit対象外）。氏名・部署等のPIIを含むため、
    共有は成果物(output/)と同様に Box 経由とし、Gitには載せない。

使い方
    python scripts/19_snapshot.py                 # 保存（フォルダ）: data/snapshots/snapshot_<最新月>/
    python scripts/19_snapshot.py --zip           # 保存 + 単一zip（Box共有用）
    python scripts/19_snapshot.py --list          # 保存済みスナップショット一覧
    python scripts/19_snapshot.py --restore PATH  # 復元: フォルダ/zip を data/ に展開
"""
import sys, json, shutil, hashlib, zipfile, argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DATA

SNAP_DIR = DATA / "snapshots"
# 16/17 が読み込む処理済みデータ（これだけで成果物を再生成できる最小集合）
REQUIRED = ["aggregates_all.json", "user_all.json", "meta_all.json"]
OPTIONAL = ["employee_master.json"]
BUILD_INPUTS = REQUIRED + OPTIONAL


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _data_month() -> str:
    """スナップショットのラベル＝データの最新月（例 2026-07）。生成日時ではなくデータ基準。"""
    try:
        agg = json.loads((DATA / "aggregates_all.json").read_text(encoding="utf-8"))
        months = agg.get("months") or []
        if months:
            return months[-1]
    except Exception:
        pass
    return datetime.now().strftime("%Y-%m")


def save(make_zip: bool):
    missing = [f for f in REQUIRED if not (DATA / f).exists()]
    if missing:
        sys.exit(f"[ERROR] 保存に必要なファイルがありません: {missing}\n"
                 f"  先に 15_aggregate.py（と 14/18）を実行してください。")
    label = _data_month()
    dest = SNAP_DIR / f"snapshot_{label}"
    dest.mkdir(parents=True, exist_ok=True)
    files_meta = []
    for f in BUILD_INPUTS:
        src = DATA / f
        if not src.exists():
            continue
        shutil.copy2(src, dest / f)
        files_meta.append({"name": f, "bytes": src.stat().st_size, "sha256": _sha256(src)})
    manifest = {
        "label": label,
        "data_latest_month": label,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "purpose": "生データなしで 16/17 を再生成するための処理済み中間データ一式",
        "restore": "python scripts/19_snapshot.py --restore <このフォルダ/zip> → 16 → 17",
        "files": files_meta,
    }
    (dest / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    total = sum(m["bytes"] for m in files_meta)
    print(f"[SAVE] {dest}  （{len(files_meta)}ファイル / {total/1024:.0f} KB）")
    for m in files_meta:
        print(f"   - {m['name']}  {m['bytes']/1024:.0f} KB")
    if make_zip:
        zpath = SNAP_DIR / f"exabase_processed_{label}.zip"
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            for p in sorted(dest.iterdir()):
                z.write(p, p.name)
        print(f"[ZIP ] {zpath}  （{zpath.stat().st_size/1024:.0f} KB）← Box共有用")
    print("復元: python scripts/19_snapshot.py --restore \"%s\"  → 16 → 17" % dest)


def list_snapshots():
    if not SNAP_DIR.exists():
        print("スナップショットはまだありません（data/snapshots/ 未作成）。")
        return
    items = sorted([p for p in SNAP_DIR.iterdir() if p.is_dir() or p.suffix == ".zip"])
    if not items:
        print("スナップショットはまだありません。")
        return
    print(f"保存済みスナップショット（{SNAP_DIR}）:")
    for p in items:
        if p.is_dir():
            mf = p / "manifest.json"
            when = ""
            if mf.exists():
                try:
                    when = json.loads(mf.read_text(encoding="utf-8")).get("generated_at", "")
                except Exception:
                    pass
            print(f"   [dir] {p.name}   生成 {when}")
        else:
            print(f"   [zip] {p.name}   {p.stat().st_size/1024:.0f} KB")


def restore(path_str: str):
    src = Path(path_str)
    if not src.exists():
        sys.exit(f"[ERROR] 見つかりません: {src}")
    tmp = None
    if src.is_file() and src.suffix == ".zip":
        tmp = SNAP_DIR / f"_restore_tmp"
        if tmp.exists():
            shutil.rmtree(tmp)
        tmp.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(src) as z:
            z.extractall(tmp)
        srcdir = tmp
    elif src.is_dir():
        srcdir = src
    else:
        sys.exit(f"[ERROR] フォルダかzipを指定してください: {src}")

    missing = [f for f in REQUIRED if not (srcdir / f).exists()]
    if missing:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
        sys.exit(f"[ERROR] スナップショットに必須ファイルがありません: {missing}")
    restored = []
    for f in BUILD_INPUTS:
        s = srcdir / f
        if s.exists():
            shutil.copy2(s, DATA / f)
            restored.append(f)
    if tmp:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"[RESTORE] data/ に展開しました: {restored}")
    print("続けて再生成: python scripts/16_build_xlsx.py  →  python scripts/17_build_dashboard.py")


def main():
    ap = argparse.ArgumentParser(description="処理済み中間データのスナップショット保存／復元")
    ap.add_argument("--zip", action="store_true", help="保存に加えて単一zipも作成（Box共有用）")
    ap.add_argument("--list", action="store_true", help="保存済みスナップショット一覧")
    ap.add_argument("--restore", metavar="PATH", help="スナップショット(フォルダ/zip)を data/ に復元")
    args = ap.parse_args()
    if args.list:
        list_snapshots()
    elif args.restore:
        restore(args.restore)
    else:
        save(args.zip)


if __name__ == "__main__":
    main()
