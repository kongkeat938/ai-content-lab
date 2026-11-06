# Organic discovery — the only growth path left (2026-11-06)

K: if we cannot push the channel, the only way is for people to find it
themselves; and it is okay if that does not work. This records what is actually
available for that, measured, so the effort is honest.

## What is blocked

- **Comment automation** needs `youtube.force-ssl`; the token grant does not have
  it, and the OAuth re-consent is blocked by a `redirect_uri_mismatch` (the
  registered URI points at a dead pod). Until the owner re-registers a redirect
  URI, read/reply cannot run.
- **Pinned comments** are Studio-only; no API exists. Never automatable.
- So no "push" via comments, and no automated outreach. Correct.

## What still works with no new consent

- **Titles and hooks** — the single biggest free lever on discovery. The advisor
  panel (measured KEEP: gemini 100/100, pollinations 100/100) can rewrite a title
  for search and click-through, and the effect is measurable in views-per-day via
  `scripts/report_reach.py`.
- **Description + tags** — `scripts/set_channel_seo.py` already writes them; the
  advisors can propose better keyword sets from the channel's own winning videos.
- **Upload cadence** — the rail already posts; consistency is itself a discovery
  signal.
- **The scorecard itself** — it proves the advisors are worth using before we
  spend effort on their suggestions.

## How we will know it worked (not a claim)

`scripts/report_reach.py` gives views-per-day per video. A title change is judged
by whether views-per-day rises in the week after it, against the same channel's
baseline. No rise, revert. That is the whole test.

## Honest expectation

The channels are tiny (106 / 29 / 9 subs). Organic discovery at this size is slow
and may not move much. K has accepted that: the work is to make each upload as
findable as it can be with free tools, and to measure whether it helped -- not to
promise growth we cannot cause.
