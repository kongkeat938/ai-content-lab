# MONITORING — how far the channel runs itself, and what watches it

Written 2026-11-03. Every claim here was measured, not assumed. Where a number
comes from a run, the run is named.

## The honest answer in one line

The **content and publishing rails are automatic**; the **timer that starts them
was not** — GitHub's scheduler never fired for this repo — so a self-chaining
watchdog now drives them instead, and a health check reports whether each rail is
still alive. There is no 24/7 process *inside* the sandbox: the pod is recycled
when idle, so the automation lives in GitHub Actions, not in the pod.

## The measurement that changed the design

```
event=schedule runs for this repo: total_count = 0
```

Every `schedule:` cron in every workflow had **never fired**, while every `push`
ran. So "the cron will do it" was false. Two consequences:

1. Nothing may depend on a `schedule` alone. A job that is **dispatched** always
   runs, so the reliable primitive is *dispatch*, not *cron*.
2. A rail that is silent looks exactly like a rail that is working. Without a
   health check, a stopped channel is invisible.

## The three layers

```
watchdog  ──dispatch──▶  foreman  ──dispatch──▶  the rails
(timer,                   (decides what is         publish-batch / publish-shorts /
 self-chaining)            due, from the ledgers)   grow-shorts-pool / set-thumbnails /
                                                    night-compilation
```

- **watchdog** (`scripts/watchdog.py`, `watchdog.yml`) — a self-chaining timer. It
  ticks the foreman every 2 h, then **dispatches a fresh copy of itself** before it
  ends, so the timer never stops and never needed cron. Public repo → Actions
  minutes are free. Kill switch: create `content/STOP`. One `concurrency` group
  means two chains cannot coexist.
- **foreman** (`scripts/foreman.py`, `foreman.yml`) — reads the ledgers
  (`ch2_publish.json`, `ch2_shorts.json`, `ch2_thumbnails.json`, `upload_limit.json`)
  and dispatches **only what is due**. It is idempotent: it reads the same ledgers
  the rails write, so a second run in a row dispatches nothing. It also **revives
  the watchdog** if the chain has gone quiet.
- **the rails** — each owns its own ledger and its own double-post guard, so the
  foreman never has to reason about content, only about timing.

## What is automatic right now

| rail | does | trigger |
|---|---|---|
| `publish-batch` | upload a long video from the manifest, one per day | foreman / push / dispatch |
| `publish-shorts` | build + upload 2 Shorts per run | foreman / push / dispatch |
| `grow-shorts-pool` | ask Gemini for 6–8 new scripts | foreman / dispatch |
| `set-thumbnails` | install covers, skipping any already live | foreman / push / dispatch |
| `night-compilation` | build a 2-hour video from the content sets | foreman (weekly) |
| `foreman` | decide + dispatch the above | push / watchdog |
| `watchdog` | keep the timer alive | self-chaining, one manual start |

## What still needs a human or the pod

- **The pod work** (rendering, measurement) cannot run in the pod 24/7 — the pod
  is recycled ~20 min after the session goes idle. Anything long must run in CI
  or be committed in stages. This is a platform limit, not a choice.
- **The chain has to be started once** after a `content/STOP`, or if the chain is
  fully dead: dispatch `watchdog` with `chain=true`. The foreman also revives it on
  any push.

## The health check (this is the "monitoring")

`scripts/health.py` — run by the foreman on every tick and committed to
`docs/HEALTH.md`. It reports, per rail, the age of the **last successful** run and
marks a rail **STALE** if it is older than that rail's own interval. A rail that
has *never* succeeded is stale, not fine — silence is the failure.

```
python3 scripts/health.py          # report, exit 1 if anything is stale
python3 scripts/health.py --json   # machine-readable
```

## Failure modes that are handled, and how

| failure | what happens |
|---|---|
| GitHub scheduler does not fire | the watchdog does not use it |
| a rail is slow | `busy()` sees an in-progress run and does not double-start it |
| channel hits its daily upload ceiling | the rail records `content/upload_limit.json`; the foreman skips uploads until the 08:00 UTC reset |
| the daily API quota is spent | `thumbnails`/reads defer, do not fail; uploads have their own bucket |
| the pod is recycled | nothing in the pod is load-bearing; all automation is in CI |
| a run dies after uploading | the id was committed inside the script, so the next run does not re-upload |
| the chain dies | the next push runs the foreman, which revives the watchdog |

## What this is NOT

- Not a promise that every rail runs at a fixed time. GitHub also delays and drops
  dispatched jobs under load; the design tolerates that by being idempotent.
- Not monitoring *content quality* — only whether the machine is running. A Short
  that ships on time and gets no views is a content problem, not a rail problem
  (see `REVENUE-PLAN.md`).
- Not a guarantee of no double-post under a *simultaneous* double-dispatch race.
  The window is small (the ledger commit happens right after the upload) and the
  `concurrency` groups remove the common case, but a true race is not impossible.
