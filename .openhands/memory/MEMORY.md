# Project Memory — ak (ai-content-lab)

**Agent `ak`**. Owner **K**: Thai replies, **measured evidence, not claims**; ak decides via the
**panel** (`advise.py`), not K. **This file is a MAP** (injected each session, tail truncated):
keep <6,000 chars (`test_memory_budget.py`); detail in `topics/`, logs, `docs/`.

## 🎯 What gates the business (`docs/DECISION-2026-11-09.md`)
- **YPP watch-hours = long-form ONLY** (Shorts do not count). Steer by long-form
  watch-hours/week + `retention@2min`, never raw views. **dharma = 96% of long-form watch
  time → concentrate there.**
- **The first 2 minutes is the binding constraint, not volume** (dharma 28.9%@2%, target ≥40%).
  **Fade-in 4s→1s** = **+12 dB** in the opening second — the hook is the lever.
- **Watch-time/view rises with length:** dharma 120-min ≈ **6.0 min/view** vs 17-min ≈ 4.6 — keep
  videos long; completion % is a distraction. **kongkeat PAUSED** via `content/PAUSED` →
  rails skipped; `test_paused_channel.py`.

## 🔑 Durable principles (K)
- **PCSEV = Problem→Cause→Solution→Execute→Verify.** Verify **live** — trust order:
  **live API > real output file (ffprobe/ebur128) > a test that can FAIL > a committed doc**.
  Best = a **counter with an invariant** (`scripts/counter_ledger.py`).
- **Times to K = Thai (UTC+7), 24-hour `HH:MM`** (never raw UTC, never 12-hour) — AGENTS.md.
- **"แยกไม่ได้" ≠ "ผิด":** a Data-API identity check dies on a spent quota → use **per-channel
  secret = identity** (`YT_CH{1,2,4}_REFRESH_TOKEN`; `test_channel_identity.py`).
- **An LLM is not a primary source** — read the vendor's rule or measure live. Panel `advise.py`
  (≥5, multi-vendor). Do NOT retry ChatGPT/PC1/DeepSeek/Devin/HF.
- **A guard must be able to FAIL;** never hardcode the set a guard sweeps; a generator that can
  drop a piece must FAIL. `.get()+continue` on a config key is a silent killer.
- **Repo hygiene** (`test_repo_hygiene.py`): pushing rails run `git pull --rebase`; a shared-ledger
  writer needs a guard; health thresholds must exceed the REAL cadence; every foreman rail watched.

## 🧭 Traps still true (one line each; detail in `topics/05-durable-traps.md` + daily logs)
- **Rogue upload stream (NOT our code):** clips no manifest names, `en-US`/cat 27/old brand at
  `:21` (ours: `th`/cat 22–24 at `:44`) = external leaked token. `rogue-guard` hides each live
  one (private, reversible); `private-delete` clears the parked set after the reset. Root = the
  token: revoke + re-consent — **Option B (2026-11-13) lets the team do it with no K**.
- **A guard that only marks SUCCESS cannot end a loop it will never satisfy** (`remove-bad-cut`
  ×37/day). Prefer **reversible (private)** over delete; mark the skip path (`delete_video.py
  --unpublish`).
- **A PUT to `brandingSettings.channel` REPLACES the whole object** → read live, merge.
- **`--minutes` is a FLOOR** (under-N set is heard twice). **`publish_at=slot` uploads PRIVATE**
  (YouTube flips it public at the slot) — intended, not stranded.
- **Quota:** `videos.insert` has its own pool; Data API resets **08:00 UTC**. GITHUB_TOKEN push
  does NOT trigger a workflow → dispatch explicitly.
- **Racing jobs lose records** → one concurrency group per channel + a union merge driver
  (`git_union_merge.py`) for append-only ledgers.
- **Night rail:** `skip` ≠ `skip_pub`; empty receipt ≠ bad video; gate before queue; a long hook
  kills retention (cap 220); never downgrade a LIVE entry (`--forget`). `test_night_*.py`.
- **Every new mechanism seeds a false alarm until the sweep learns it** (2026-11-12): qa_gate
  graded 120-min files B; counter_ledger read a same-day dip as DOWN; health flagged paused rails.
- **We were blind to a YouTube take-down** (2026-11-13): the audit only diffed
  channel→manifest, so a REMOVED video vanished silently — genx carried an active
  community-guidelines **warning** (content removed; expires 1 Feb) while a doc claimed "no
  strike". `find_removed` now diffs manifest→uploads (`test_audit_removed`). Panel 3/3: do
  NOT pause genx (fastest grower, +183 subs/28 d); keep clips low-risk.
- **Mail on the cloud, not PC1** (dead — don't retry); `IMAP_ACCOUNTS` = kongkeat.938 only.
- **ch4 subs flat:** Shorts work, long-form dead (subs/1,000 = 1.93); a Short must not promise a
  "full clip" (`test_ch4_cta.py`); trailer wired (after 08:00Z).

## 🗺️ Topic map (read on demand)
- `topics/00-..05-*.md` · `docs/DECISION-*`/`PANEL-*`/`CONSULT-*`/`HEALTH.md`/`CHANNEL-AUDIT-LATEST.md`
  · logs `2026-11-DD.md`.
- **Automation:** GH Actions only (watchdog → foreman → rails); kill switch `content/STOP`.
  **Publishing:** `content/<ch>_publish.json`/`_shorts.json`, `DAILY_CAP=3`. Pages:
  kongkeat938.github.io/ai-content-lab/.
- **Accounts (2026-11-12):** 1 channel = 1 Google account — genx `kongkeat.938`, dharma
  `farmmer.938`, kongkeat-story `kongkeat.p3` (own 19/day pool each); `test_channel_accounts.py`.
  Manager invite = **Studio → การตั้งค่า → สิทธิ์**; the reauth wall needs K on VNC once.
- **Delegation (Option B, 2026-11-13):** genx = `aerismusic8@gmail.com` **Manager** +
  `YT_CH1_ALT_REFRESH_TOKEN`; `delegate_ready.py` = `READY genx`. **A refresh token is bound to the
  client that minted it:** alt is on client **B** (`YT_ALT_CLIENT_ID/SECRET`) — 200s there, `401
  unauthorized_client` on the primary; check each alt token with its own client. dharma/ch4 need
  their OWNER to invite (K on VNC).
- **Pod env:** recycled often → reinstall `ffmpeg` + `pip install -r requirements.txt`; export
  `GH_TOKEN=$KONGKEAT_GH_TOKEN`. Suite: `for t in scripts/test_*.py; do python3 "$t"; done`.
- **VNC remote-in (2026-11-12):** ak drives headful chromium over CDP :9222; K types passwords
  on noVNC (`start_novnc.sh`). Thai fonts (`fonts-thai-tlwg`) or text is boxes.
- **Comment writes need `force-ssl`** (`yt_auth.py --scopes force-ssl --slug <ch>`). **Text must fit
  its frame** (`test_short_caption`, `test_poster_fit`). Conversion lever = pinned CTA comment
  (`test_shorts_cta_comment`).
