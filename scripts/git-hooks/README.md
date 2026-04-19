# Git hooks

Repo-tracked hooks that protect critical workflows. Activate them in
your local clone with a single config command:

```bash
git config core.hooksPath scripts/git-hooks
```

That points Git at this directory for *every* hook (pre-commit,
pre-push, …) so the team gets the same protection without symlinking
individual files.

## What's in here

### `pre-push`

Blocks any push to the `hf-streamlit` remote whose tip doesn't match
`origin/dev`. The HF Space has no native branch protection, and on
2026-04-20 a stray force-push reverted `main` to a much older state
(dropping ~7 300 lines). This hook makes the deploy contract explicit:

1. Merge to `origin/dev` (via PR + CI).
2. `git fetch origin`.
3. `git push hf-streamlit dev:main`.

Any other push to the Space's `main` branch is refused with a
diagnostic explaining how to fix it.

**Bypass** (intentional, e.g. emergency hotfix from a feature branch):

```bash
git push --no-verify hf-streamlit <sha>:main
```

The `--no-verify` flag is the standard Git escape hatch — use it
sparingly and document why in the deploy commit message.

## Verifying the install

After running the `git config core.hooksPath …` command:

```bash
git config --get core.hooksPath
# → scripts/git-hooks
```

A push to `origin` (any branch) should be unaffected. A push to
`hf-streamlit refs/heads/main` of any SHA other than `origin/dev`'s
tip should be refused with the diagnostic.
