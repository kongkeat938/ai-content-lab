# WORK ORDER — yt938-2 steering numbers: watch-hours/week + retention@2min per channel

_Issued by AF for K, live_

## What AF needs (one measurement, not a build)

The map steers yt938-2 by **long-form watch-hours/week** and **retention@2min**, and it says Shorts do
not count toward YPP. AF cannot read either number from outside: YouTube exposes views, not watch-hours.

Please report, as of today, one row per channel (`dharma`, `genx`, `PCSEV`):

| channel | long-form videos live | watch-hours last 7 days | retention@2min | subscribers |
|---|---|---|---|---|

Source each cell: YouTube Analytics if it is connected, otherwise write `UNKNOWN` — do not estimate.

Also state in one line each: which workflows are currently `disabled_manually` that would have to be
re-enabled for a scheduled upload, and whether `scripts/gh_auth.py status` currently reports a valid
credential.

## Why AF is asking instead of doing

AF holds write on this repository as of 2026-11-27 but has **no YouTube credential for these channels**
and no analytics access; the numbers live behind the login that `ak` already holds. Reading them from
outside gives views only, and views are not the steering metric.

## What AF will do with it

Convert the three rows into the required weekly rate to 4,000 watch-hours and say whether any channel
has ever hit that rate. That number decides whether the next action is content, packaging, or
distribution — the same question AF answered for the Lanternwild channel (there: 1,753 years at the
current rate).

## Acceptance test

A reply in this PR or a linked issue gives watch-hours (last 7 days) and retention@2min for dharma, genx and PCSEV, each with its source, or states UNKNOWN with the reason.
