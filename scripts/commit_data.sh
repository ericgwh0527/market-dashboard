#!/usr/bin/env bash
# Commit generated files from a workflow job, with guard rails.
# Usage: commit_data.sh <label>   (needs GH_TOKEN in the environment)
set -euo pipefail
label="${1:-data}"

git add docs/data

# Never commit anything outside docs/data, and never a plaintext holdings file.
if git diff --cached --name-only | grep -Ev '^docs/data/'; then
  echo "Refusing: unexpected paths staged"; exit 1
fi
if git diff --cached --name-only | grep -qi 'holdings'; then
  echo "Refusing: holdings file staged"; exit 1
fi
if git diff --cached --quiet; then
  echo "No changes"; exit 0
fi

git -c user.name="market-data-bot" -c user.email="41898282+github-actions[bot]@users.noreply.github.com" \
    commit -q -m "${label}: $(TZ=Asia/Kuala_Lumpur date '+%Y-%m-%d %H:%M MYT')"

# The token is passed per command (not stored in .git/config).
auth="AUTHORIZATION: basic $(printf 'x-access-token:%s' "$GH_TOKEN" | base64 -w0)"
# If another run committed data in the meantime, both touched the same generated
# JSON files. Our files are the freshest, so on conflict keep ours
# (during a rebase, "theirs" = the commit being replayed = this run's data).
for attempt in 1 2 3; do
  if git -c http.https://github.com/.extraheader="$auth" pull -q --rebase -X theirs --autostash; then
    git -c http.https://github.com/.extraheader="$auth" push -q && exit 0
  else
    git rebase --abort 2>/dev/null || true
  fi
  sleep $((attempt * 5))
done
echo "Push failed"; exit 1
