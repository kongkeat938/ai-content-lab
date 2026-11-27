#!/usr/bin/env bash
# Push main, retrying when a concurrent rail commits between our pull and push.
#
# A single `git pull --rebase; git push` is a race: if any other rail (there are
# ~20) commits in that window, the push is rejected with "cannot lock ref ...
# is at X but expected Y". Measured 2026-11-09: that failure broke the
# night-compilation workflow and stranded a built video (issue #21). Every rail
# writes to the same branch, so the race is the norm, not an edge case.
#
# Call it after committing, from any workflow's run step:
#     bash scripts/git_push_retry.sh              # fail the step if it cannot push
#     bash scripts/git_push_retry.sh --best-effort  # exit 0; a later tick refreshes
set -u

best_effort=0
[ "${1:-}" = "--best-effort" ] && best_effort=1

# The append-only JSON ledgers carry `merge=unionjson` in .gitattributes, but git
# only uses a custom merge driver when it is registered in THIS repo's config.
# Each workflow that commits a ledger registered it by hand; the ones that did not
# (ch4-longform, measured 2026-11-13) fell back to a plain text merge, hit a
# CONFLICT on content/bed_ledger_kongkeat.json, and stranded a finished video that
# was already on a Release. Register it here, once, so every caller is covered.
git config merge.unionjson.name "union json ledgers"
git config merge.unionjson.driver "python3 scripts/git_union_merge.py %O %A %B"

# A `fetch-depth: 1` checkout cannot rebase -- `git pull --rebase` exits 128 with
# no merge base, and every retry repeats it. Measured 2026-11-27: publish-shorts
# published three Shorts and lost all three ids this way. Deepen once, up front.
if [ "$(git rev-parse --is-shallow-repository 2>/dev/null)" = "true" ]; then
  git fetch --unshallow origin main || git fetch --deepen=100 origin main || true
fi

attempts=5
for i in $(seq 1 "$attempts"); do
  if ! git pull --rebase --autostash origin main; then
    # A conflicted rebase on a generated artifact must not wedge the loop; the
    # next tick regenerates it. Abort and try again.
    git rebase --abort || true
  fi
  if git push; then
    echo "pushed on attempt $i"
    exit 0
  fi
  echo "push attempt $i lost the race; retrying"
  sleep 5
done

if [ "$best_effort" = 1 ]; then
  echo "could not push after $attempts attempts; a later tick will refresh it"
  exit 0
fi
echo "could not push after $attempts attempts" >&2
exit 1
