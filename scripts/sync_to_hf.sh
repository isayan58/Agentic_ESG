#!/usr/bin/env bash
# Push the current `main` to the HuggingFace Space, stripping the binary
# files (PNGs under docs/, client decks, archives) that the Space won't take.
#
# Why this exists:
#   GitHub mirror keeps the docs/ PNGs and any client decks.
#   HF Space cannot accept those blobs without xet/LFS.
#   This script builds a deploy commit whose tree is exactly `main` minus
#   the excluded paths, stacked on the Space's current tip, and pushes it.
#
# Why it is a tree-sync and not a cherry-pick replay:
#   It used to recreate a branch from the Space's tip and cherry-pick every
#   commit `git cherry` reported as missing. That silently assumed the Space
#   shared history with main. It does not — the Space has its own root
#   commit and no merge base with main — so `git cherry` degenerated into
#   replaying the entire history from "Initial commit" and hit an add/add
#   conflict on the first one, every time. Since the Space only ever needs
#   main's *files*, syncing the tree in one commit sidesteps the whole
#   problem and works whether or not the histories are related.
#
# Usage:
#   scripts/sync_to_hf.sh            # deploy
#   scripts/sync_to_hf.sh --dry-run  # show what would deploy, push nothing
#
# Prerequisites:
#   - `hf-streamlit` remote pointing at the HuggingFace Space.
#   - `main` is what you want deployed (clean working tree).

set -euo pipefail

# HF_REMOTE exists so the script can be exercised end-to-end against a
# throwaway remote instead of the live Space. Leave it unset in normal use.
REMOTE_HF="${HF_REMOTE:-hf-streamlit}"
DEPLOY_BRANCH="hf-deploy"
SOURCE_BRANCH="main"

DRY_RUN=0
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
fi

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
# shellcheck source=hf-deploy-lib.sh
. "$repo_root/scripts/hf-deploy-lib.sh"

# Block on modified or staged *tracked* files — those represent work that
# isn't in the commit being deployed, and the checkout below would discard
# them. Untracked files are a different matter: this syncs main's tree, so
# a local editor config or scratch file cannot affect what ships, and
# failing on them is a false positive that blocks legitimate deploys.
if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo "✗ Tracked files are modified. Commit or stash before syncing." >&2
  git status --short --untracked-files=no >&2
  exit 1
fi

# The one untracked case that does matter: a file that main tracks would be
# overwritten by `read-tree -u` below, silently destroying local content.
_collisions=""
while IFS= read -r _untracked; do
  [[ -n "$_untracked" ]] || continue
  if git cat-file -e "main:$_untracked" 2>/dev/null; then
    _collisions+="  $_untracked"$'\n'
  fi
done < <(git ls-files --others --exclude-standard)
if [[ -n "$_collisions" ]]; then
  echo "✗ Untracked files would be overwritten by the deploy checkout:" >&2
  printf '%s' "$_collisions" >&2
  echo "  Move or commit them first." >&2
  exit 1
fi

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$CURRENT_BRANCH" != "$SOURCE_BRANCH" ]]; then
  echo "✗ Run this from $SOURCE_BRANCH (currently on $CURRENT_BRANCH)." >&2
  exit 1
fi

# Always land back on the branch we started from, even on failure. Without
# this an aborted run strands you on the deploy branch with a rewritten
# working tree, which is alarming and easy to mistake for data loss.
cleanup() {
  local exit_code=$?
  if [[ "$(git rev-parse --abbrev-ref HEAD 2>/dev/null)" != "$CURRENT_BRANCH" ]]; then
    # -f because stripping the excluded files leaves them untracked, and
    # they'd otherwise block the checkout. Their content is identical to
    # what $CURRENT_BRANCH tracks, so nothing is lost.
    git checkout -f "$CURRENT_BRANCH" >/dev/null 2>&1 || true
  fi
  git branch -D "$DEPLOY_BRANCH" >/dev/null 2>&1 || true
  if [[ $exit_code -ne 0 ]]; then
    echo "" >&2
    echo "✗ Sync aborted — restored $CURRENT_BRANCH, no changes pushed." >&2
  fi
  return $exit_code
}
trap cleanup EXIT

echo "▶ Fetching $REMOTE_HF and origin..."
git fetch --quiet "$REMOTE_HF" main
git fetch --quiet origin "$SOURCE_BRANCH"

HF_TIP="$(git rev-parse "$REMOTE_HF/main")"
LOCAL_TIP="$(git rev-parse "$SOURCE_BRANCH")"
echo "  HF tip:    ${HF_TIP:0:12}  ($(git log -1 --format='%s' "$HF_TIP"))"
echo "  main tip:  ${LOCAL_TIP:0:12}  ($(git log -1 --format='%s' "$LOCAL_TIP"))"

# Deploy only what origin/main has: pushing unpushed local commits to a
# public Space would put code live that no one has reviewed.
if [[ "$(git rev-parse "origin/$SOURCE_BRANCH")" != "$LOCAL_TIP" ]]; then
  echo "" >&2
  echo "✗ Local $SOURCE_BRANCH differs from origin/$SOURCE_BRANCH." >&2
  echo "  Push to GitHub first so the Space only ever runs reviewed code." >&2
  exit 1
fi

# Is the Space already carrying main's files? Compare trees, not SHAs —
# the deploy commit necessarily has a different SHA every time.
PENDING="$(hf_deploy_unexpected_diff "$HF_TIP" "$LOCAL_TIP")"
if [[ -z "$PENDING" ]]; then
  echo "✓ Space already matches $SOURCE_BRANCH (excluding stripped binaries). Nothing to do."
  exit 0
fi

pending_count="$(printf '%s\n' "$PENDING" | grep -c .)"
echo "▶ $pending_count path(s) differ from the Space:"
printf '%s\n' "$PENDING" | head -20 | sed 's/^/    /'
if [[ "$pending_count" -gt 20 ]]; then
  echo "    … and $((pending_count - 20)) more"
fi

# Build the deploy commit: HEAD stays at the Space's tip (so the result is
# a fast-forward for the Space and needs no force push) while the index and
# working tree are replaced wholesale with main's tree.
echo "▶ Building deploy commit on top of ${HF_TIP:0:12}..."
git checkout -q -B "$DEPLOY_BRANCH" "$HF_TIP"
git read-tree --reset -u "$LOCAL_TIP"

# Strip the excluded paths from the index only. They stay in the working
# tree as untracked files and are restored by the cleanup checkout.
stripped=0
while IFS= read -r pattern; do
  [[ -n "$pattern" ]] || continue
  matched="$(git diff --cached --name-only -- "$pattern" 2>/dev/null || true)"
  if [[ -n "$matched" ]]; then
    echo "  Stripping: $(printf '%s' "$matched" | tr '\n' ' ')"
    printf '%s\n' "$matched" | xargs -I{} git rm -q --cached -f "{}" >/dev/null
    stripped=1
  fi
done <<EOF
$(hf_deploy_patterns)
EOF
[[ $stripped -eq 1 ]] || echo "  (nothing matched the exclude list)"

if git diff --cached --quiet; then
  echo "✓ Deploy tree is identical to the Space's tip after stripping. Nothing to do."
  exit 0
fi

git commit -q -m "deploy: sync Space to $SOURCE_BRANCH @ ${LOCAL_TIP:0:12} (excluded binaries stripped)"
DEPLOY_SHA="$(git rev-parse HEAD)"

# Belt and braces: prove the thing we're about to push really is main.
# This is the same check the pre-push guard runs, so a failure here means
# the script built something wrong, not that the guard is misconfigured.
VERIFY="$(hf_deploy_unexpected_diff "$DEPLOY_SHA" "$LOCAL_TIP")"
if [[ -n "$VERIFY" ]]; then
  echo "✗ Deploy tree does not match $SOURCE_BRANCH. Refusing to push. Offending paths:" >&2
  printf '%s\n' "$VERIFY" | sed 's/^/    /' >&2
  exit 1
fi
echo "✓ Verified: deploy tree matches $SOURCE_BRANCH (excluding stripped binaries)."

if [[ $DRY_RUN -eq 1 ]]; then
  echo "▶ --dry-run: would push ${DEPLOY_SHA:0:12} → $REMOTE_HF:main. Stopping here."
  exit 0
fi

echo "▶ Pushing ${DEPLOY_SHA:0:12} → $REMOTE_HF:main"
git push "$REMOTE_HF" "$DEPLOY_BRANCH:main"

echo "✓ Synced. Space tip is now ${DEPLOY_SHA:0:12}"
echo "  The Space will rebuild — watch it before calling the deploy done."
