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

Guards the HuggingFace Space. The Space has no native branch protection,
and on 2026-04-20 a stray push reverted its `main` to a much older state
(dropping ~7 300 lines).

The hook refuses any push to `hf-streamlit`'s `main` whose **tree**
differs from `origin/main`, ignoring the paths in
[`../hf-deploy-excludes.txt`](../hf-deploy-excludes.txt). The contract is
"what lands on the Space must be `main`".

It compares trees rather than SHAs on purpose. A deploy commit can never
share a SHA with `origin/main`:

* it strips binaries the Space won't accept, so its tree differs; and
* the Space's history is unrelated to `main`'s — its own root commit,
  no merge base — so the deploy commit is built on the Space's tip.

An earlier version required `local_sha == origin/main`, which no real
deploy could satisfy. Every legitimate push had to be forced through with
`--no-verify`, so the guard was bypassed as a matter of routine and
protected nothing. The tree check keeps the 2026-04-20 scenario blocked
(a stale or reverted tree differs in tracked source files) while letting
correct deploys through untouched.

The deploy path is therefore just:

1. Merge to `origin/main` (via PR + CI).
2. `git fetch origin`.
3. `scripts/sync_to_hf.sh`.

**Bypass** (intentional — only when you mean to deploy something that is
*not* `main`):

```bash
git push --no-verify hf-streamlit <sha>:main
```

Document why in the deploy commit message.

## Verifying the install

After running the `git config core.hooksPath …` command:

```bash
git config --get core.hooksPath
# → scripts/git-hooks
```

You can exercise the hook without pushing anything by feeding it the
stdin format Git uses (`<local-ref> <local-sha> <remote-ref> <remote-sha>`):

```bash
# Should be ALLOWED — origin/main's own tree.
echo "refs/heads/x $(git rev-parse origin/main) refs/heads/main $(printf '0%.0s' {1..40})" \
  | scripts/git-hooks/pre-push hf-streamlit https://huggingface.co/spaces/isayan58/ESG-CoPilot-Dashboard
echo "exit=$?"

# Should be BLOCKED — an older tree.
echo "refs/heads/x $(git rev-parse origin/main~5) refs/heads/main $(printf '0%.0s' {1..40})" \
  | scripts/git-hooks/pre-push hf-streamlit https://huggingface.co/spaces/isayan58/ESG-CoPilot-Dashboard
echo "exit=$?"
```

Pushes to `origin` (any branch), to any Space ref other than
`refs/heads/main`, and branch deletions are all out of scope and pass
straight through.

## A note on `.gitignore`

`.gitignore` ignores `scripts/` wholesale. The files in here are tracked
because they were added with `git add -f`. If you add another script that
the team needs, it will be silently skipped by a plain `git add` — force
it, or it will exist only on your machine. That is exactly what happened
to `sync_to_hf.sh`, which the README documented as the deploy tool for
months while being present on a single laptop.
