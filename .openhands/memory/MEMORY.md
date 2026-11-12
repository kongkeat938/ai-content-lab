# Project Memory — ak (ai-content-lab)

**Agent `ak`** (was AX, 2026-10-31). Owner **K**: Thai replies, **measured evidence, not claims**.
ak decides — take a decision to the **panel**, not to K (order events → causes → pros/cons vs
goal → panel → most-gain/least-harm → act). **This file is a MAP, not a log** (injected every
session, tail truncated). Keep under ~6,000 chars (guard `test_memory_budget.py`); detail in
`topics/`, logs, `docs/`.

## 🎯 What gates the business (`docs/DECISION-2026-11-09.md`)
- **YPP watch-hours = long-form ONLY** (Shorts do not count). Steer by long-form
  watch-hours/week + `retention@2min`, never raw views. **dharma = 96% of long-form watch
  time → concentrate there.** Review 2026-11-16.
- **The first 2 minutes is the binding constraint, not volume** (dharma 102%@1% → **28.9%@2%**,
  target ≥40%). **Fade-in 4s→1s** measured **+12 dB** in the opening second — the hook is the
  lever, not the loop seam.
- **Watch-time/view rises with length:** dharma's 120-min (5% completion) ≈ **6.0 min/view** vs
  its 17-min (27%) ≈ 4.6 — keep videos long; the completion % is a distraction. **kongkeat is
  PAUSED** (2026-11-12: +3 views/day, 0 subs, 0.5 watch-hours in 28 d) via `content/PAUSED` (both
  names) → its rails skipped; guard `test_paused_channel.py`; reverse = empty the file.

## 🔑 Durable principles (K)
- **PCSEV = Problem→Cause→Solution→Execute→Verify.** Verify **live** — trust order:
  **live API > real output file (ffprobe/ebur128) > a test that can FAIL > a committed doc**.
  Best = a **counter with an invariant** (`scripts/counter_ledger.py`).
- **Times to K = Thai (UTC+7), 24-hour `HH:MM`** (never raw UTC, never 12-hour) — AGENTS.md.
- **"แยกไม่ได้" ≠ "ผิด":** a Data-API identity check dies silently on a spent quota → use
  **per-channel secret = identity** (`YT_CH{1,2,4}_REFRESH_TOKEN`; `test_channel_identity.py`).
- **An LLM is not a primary source** — read the vendor's rule or measure live. Advisor panel:
  `scripts/advise.py` (≥5, multi-vendor). Do NOT retry ChatGPT/PC1/DeepSeek/Devin/HF.
- **A guard must be able to FAIL;** never hardcode the set a guard sweeps; a generator that can
  drop a piece must FAIL. `.get()+continue` on a config key is a silent killer — make it loud.
- **Repo hygiene** (failing test `test_repo_hygiene.py`): rails that push run `git pull --rebase`;
  a shared-ledger writer needs a guard; health thresholds must exceed the REAL cadence; every
  foreman-dispatched rail must be watched + every new scheduled rail needs a foreman rule.

## 🧭 Traps still true (one line each; detail in `topics/05-durable-traps.md` + daily logs)
- **Rogue upload stream (NOT our code):** clips no manifest names, `en-US`/cat 27/old brand at
  `:21` (ours: `th`/cat 22–24 at `:44`) = external leaked token. `audit_channels.py --alert`
  splits **live** (≤3 d) vs **backlog**; `--hide-live-rogue` pauses live (private, reversible).
  Delete parked-**private** only — never unlisted (a live shared link; `private-delete.yml`
  @08:14Z, needs the reset). The root is the token: K must revoke + re-consent.
- **A guard that only marks SUCCESS cannot end a loop it will never satisfy** (`remove-bad-cut`
  ×37/day on a `views>5` skip). Prefer **reversible (private)** over delete; mark the skip path
  too (`delete_video.py --unpublish`).
- **A PUT to `brandingSettings.channel` REPLACES the whole object** (wipes description/keywords)
  → read live, merge. `country` is NOT writable.
- **`--minutes` is a FLOOR:** an under-N set is heard twice. **`publish_at=slot` uploads
  PRIVATE** (YouTube flips it public at the slot) — intended, not stranded.
- **Quota:** `videos.insert` has its own pool; Data API resets **08:00 UTC**; a pod 403 before
  then is expected. GITHUB_TOKEN push does NOT trigger a workflow → dispatch explicitly.
- **Racing jobs lose records** → one concurrency group per channel + union merge driver
  (`git_union_merge.py`, `.gitattributes merge=unionjson`) for append-only ledgers.
- **Night rail:** `skip` ≠ `skip_pub`; an empty receipt is not a bad video; gate before queue
  (`test_manifest_qa.py`, `test_night_queued.py`). **A long hook kills retention** (cap 220).
  **A rebuild of a LIVE key must not un-publish it** (a rail edit changes the fingerprint →
  rebuild of the same week key reset a published entry to `ready`; now a live entry's state is
  never downgraded, only `--forget` re-uploads).
- **Every new mechanism seeds a false alarm until the sweep learns it** (2026-11-12): qa_gate
  graded every 120-min file B (two bands 15-40 & 110-130); counter_ledger read a same-day dip as
  DOWN (skip same-UTC-day); health flagged paused rails (now reads `PAUSED`).
- **Mail on the cloud, not PC1** (PC1 dead — don't retry); `IMAP_ACCOUNTS` = kongkeat.938 only.
- **ch4 subs flat:** Shorts work, long-form dead (subs/1,000 = 1.93); a Short must not promise a
  "full clip" (`test_ch4_cta.py`); `unsubscribedTrailer` wired (after 08:00Z).

## 🗺️ Topic map (read on demand)
- `topics/00-..05-*.md` · `docs/DECISION-*`/`PANEL-*`/`CONSULT-*`/`HEALTH.md`/`CHANNEL-AUDIT-LATEST.md`
  · logs `.openhands/memory/2026-11-DD.md`.
- **Automation:** GH Actions only (watchdog → foreman → rails); kill switch `content/STOP`.
  **Publishing:** `content/<ch>_publish.json`/`_shorts.json`, `DAILY_CAP=3`. Pages:
  kongkeat938.github.io/ai-content-lab/.
- **Pod env:** recycled often → reinstall `ffmpeg` + `pip install -r requirements.txt`; export
  `GH_TOKEN=$KONGKEAT_GH_TOKEN`. Full suite: `for t in scripts/test_*.py; do python3 "$t"; done`.
- **Comment writes need `force-ssl`** (all 3 tokens = `youtube` scope only → `commentThreads.insert`
  403s; owner fix `yt_auth.py --scopes force-ssl --slug <ch>`). **Text must fit its frame:**
  Shorts captions safe box L0.06/R0.84/T0.10/B0.88 (centred hit 0.93W under the button rail,
  `test_short_caption`); poster titles wrap+shrink to 130px ≤3 lines (`test_poster_fit`).
  Conversion lever = pinned CTA comment (`test_shorts_cta_comment`).
