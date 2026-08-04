#!/usr/bin/env bash
# ============================================================
# gitsafe — Cowork/Claude のマウント制約に対応した git ラッパー
#
# このフォルダは Windows フォルダのマウントで「rename は可・unlink は不可」。
# そのため git は commit/merge 自体は正常に行えるが、処理後に残る *.lock を
# git が削除できず、次の git コマンドが「index.lock: File exists」で止まる。
#
# 本ラッパーは、git 実行の前に残留 *.lock を .git/_locktrash/ へ退避(rename)し、
# そのうえで git を実行する。これによりチャット/Claude Code から git が回せる。
#
# 使い方:  bash tools/gitsafe.sh <git引数...>
#   例:    bash tools/gitsafe.sh add -A
#          bash tools/gitsafe.sh commit -m "feat: ..." -m "- 変更点"
#          bash tools/gitsafe.sh switch -c feature/xxxx
#          bash tools/gitsafe.sh merge --no-ff feature/xxxx -m "Merge ..."
#
# 注意:
#  - push は行わない（GitHub 認証なし）。push はお手元(GitHub Desktop)で。
#  - 退避ロックは .git/_locktrash/ に溜まる（unlink不可のため消せないが無害）。
#    気になれば Windows 側で .git/_locktrash を削除。
#  - git gc / branch -D 等は unlink を多用し stuck lock を残しやすいので多用しない。
# ============================================================
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

TRASH=".git/_locktrash"
mkdir -p "$TRASH" 2>/dev/null || true

# 残留ロックを退避（rename のみ。unlink は不可のため使わない）
if [ -d .git ]; then
  while IFS= read -r f; do
    [ -e "$f" ] && mv "$f" "$TRASH/$(basename "$f").$$.$RANDOM" 2>/dev/null || true
  done < <(find .git -name '*.lock' -not -path '*/_locktrash/*' 2>/dev/null)
fi

# 実行（tmp_obj の無害な unlink 警告は抑制）
git "$@" 2> >(grep -v "unable to unlink '.git/objects.*tmp_obj" >&2)
