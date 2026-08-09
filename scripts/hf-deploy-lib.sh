#!/usr/bin/env bash
# Shared helpers for the HuggingFace Space deploy path.
#
# Sourced by both `scripts/sync_to_hf.sh` (which builds the deploy commit)
# and `scripts/git-hooks/pre-push` (which decides whether to allow it).
# They must agree on what "this commit is main" means, or the guard blocks
# the very deploys the sync script is designed to produce — which is exactly
# how the two ended up incompatible before.
#
# Deliberately POSIX-ish bash: no `mapfile`, no associative arrays, so this
# still runs under the bash 3.2 that ships with macOS.

# Absolute path to the excludes list, resolved from the repo root so this
# works no matter which directory the caller ran from (git hooks run at the
# top level; a developer may run the sync script from anywhere).
hf_deploy_excludes_file() {
  printf '%s/scripts/hf-deploy-excludes.txt' "$(git rev-parse --show-toplevel)"
}

# Print each exclude glob on its own line, comments and blanks stripped.
hf_deploy_patterns() {
  local file
  file="$(hf_deploy_excludes_file)"
  [[ -f "$file" ]] || return 1
  # Strip comments/blank lines. `|| true` keeps `set -e` callers alive when
  # the list is legitimately empty.
  grep -vE '^[[:space:]]*(#|$)' "$file" || true
}

# True when $1 matches any exclude glob.
hf_deploy_is_excluded() {
  local path="$1" pattern
  while IFS= read -r pattern; do
    [[ -n "$pattern" ]] || continue
    # Unquoted RHS: bash glob matching, where `*` spans `/` too.
    # shellcheck disable=SC2053
    if [[ "$path" == $pattern ]]; then
      return 0
    fi
  done <<EOF
$(hf_deploy_patterns)
EOF
  return 1
}

# Print the paths that differ between two commits, ignoring excluded ones.
# Empty output means the trees are equivalent for deploy purposes — the
# commits may have different SHAs and unrelated histories, which is normal:
# the Space's history is not, and need not be, a descendant of main's.
hf_deploy_unexpected_diff() {
  local a="$1" b="$2" path
  while IFS= read -r path; do
    [[ -n "$path" ]] || continue
    if ! hf_deploy_is_excluded "$path"; then
      printf '%s\n' "$path"
    fi
  done <<EOF
$(git diff --name-only "$a" "$b")
EOF
}
