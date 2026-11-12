# Project Memory — ak (ai-content-lab)

**Agent `ak`** (was AX, 2026-10-31). Owner **K**: Thai replies, **measured evidence, not
claims**. ak decides — take a decision to the **panel**, not to K (order: presence of mind →
order the events → causes → pros/cons vs the goal → panel → most-gain/least-harm → act).
**This file is a MAP, not a log** — injected every session and the tail is truncated. Keep it
under ~6,000 chars (guard `scripts/test_memory_budget.py`); full detail lives in `topics/`,
`.openhands/memory/2026-11-DD.md`, `docs/`.

## 🎯 What gates the business (`docs/DECISION-2026-11-09.md`)
- **YPP watch-hours = long-form ONLY** (Shorts do not count). Steer by long-form
  watch-hours/week + `retention@2min`, never raw views. **dharma = 96% of long-form watch
  time → concentrate there.** Review 2026-11-16.
- **The first 2 minutes is the binding constraint, not volume** (dharma keeps 102%@1% then
  **28.9%@2%**, target ≥40%). More volume is noise; content must be specific + actionable.
- **Watch-time/view rises with length:** dharma's 120-min (5% completion) ≈ **6.0 min/view** vs
  its 17-min (27%) ≈ 4.6 — keep videos long; the completion % is a distraction. **kongkeat is
  dead** (+3 views/day, 0 subs) → pause candidate. Plan: `docs/GROWTH-PLAN-2026-11-12.md`.

## 🔑 Durable principles (K)
- **PCSEV = Problem→Cause→Solution→Execute→Verify.** Verify **live** — trust order:
  **live API > real output file (ffprobe/ebur128) > a test that can FAIL > a committed doc**.
  Best = a **counter with an invariant** (`scripts/counter_ledger.py`).
- **"แยกไม่ได้" ≠ "ผิด":** a Data-API identity check dies silently on a spent quota → use
  **per-channel secret = identity** (`YT_CH{1,2,4}_REFRESH_TOKEN`; `test_channel_identity.py`).
- **An LLM is not a primary source** — read the vendor's rule or measure live. Advisor panel:
  `scripts/advise.py` (≥5, multi-vendor). Do NOT retry ChatGPT/PC1/DeepSeek/Devin/HF.
- **A guard must be able to FAIL;** never hardcode the set a guard sweeps; a generator that can
  drop a piece must FAIL. `.get()+continue` on a config key is a silent killer — make it loud.
- **Repo hygiene** (each has a failing test, `test_repo_hygiene.py`): every rail that pushes to
  main runs `git pull --rebase` first; any file two workflows commit needs a writer-side guard;
  every health threshold must exceed the REAL cadence; every foreman-dispatched rail must be
  watched; every new scheduled rail needs a foreman rule.

## 🧭 Traps still true (one line each; detail in `topics/05-durable-traps.md` + daily logs)
- **Rogue upload stream (NOT our code):** clips no manifest names, `en-US`/cat 27/old brand
  `เรื่องเล่าการ์ตูน` at `:21` (our rails: `th`/cat 22–24 at `:44`). Source = external leaked
  token. `audit_channels.py --alert` opens/clears issue #22, splits **live** (≤3 d) vs
  **historical backlog**; `--hide-live-rogue` pauses live ones (private, reversible). Never
  delete/hide the backlog.
- **A guard that only marks SUCCESS cannot end a loop it will never satisfy** (`remove-bad-cut`
  ×37/day on a `views>5` skip). Prefer **reversible (private)** over delete; mark the skip path
  too (`delete_video.py --unpublish`).
- **A PUT to `brandingSettings.channel` REPLACES the whole object** (wipes description/keywords/
  language) → read live, merge. `country` is NOT writable.
- **`--minutes` is a FLOOR:** an under-N set is heard twice. **`publish_at=slot` uploads
  PRIVATE** (YouTube flips it public at the slot) — intended, not stranded.
- **Quota:** `videos.insert` has its own pool; Data API resets **08:00 UTC**; a pod 403 before
  then is expected. GITHUB_TOKEN push does NOT trigger a workflow → dispatch explicitly.
- **Racing jobs lose records** → one concurrency group per channel + union merge driver
  (`git_union_merge.py`, `.gitattributes merge=unionjson`) for append-only ledgers.
- **Night rail:** `skip` ≠ `skip_pub`; an empty receipt is not a bad video; gate before queue
  (`test_manifest_qa.py`, `test_night_queued.py`). **A long hook kills retention** (cap 220).
- **Mail is on the cloud, not PC1** (PC1 dead — do NOT retry). `IMAP_ACCOUNTS` holds only
  kongkeat.938@gmail.com.
- **ch4 subs are flat:** Shorts work, long-form dead (subs/1,000 = 1.93); a Short must not
  promise a "full clip" (`test_ch4_cta.py`); `unsubscribedTrailer` now wired (after 08:00Z).

## 🗺️ Topic map (read on demand)
- `topics/00-pipeline-and-channel-facts.md`, `01-pipeline-build-and-measure.md`,
  `02-gates-and-traps.md`, `03-pc1-and-storage.md`, `04-no-browser-api-path.md`,
  `05-durable-traps.md` — the deep set.
- `docs/DECISION-*.md` (goals), `docs/PANEL-*.md`+`docs/CONSULT-*.md` (decisions),
  `docs/HEALTH.md`, `docs/CHANNEL-AUDIT-LATEST.md`. Daily logs: `.openhands/memory/2026-11-DD.md`.
- **Automation:** GitHub Actions only (watchdog → foreman → rails); `scripts/health.py`; kill
  switch `content/STOP`. **Publishing:** `content/<ch>_publish.json`+`_shorts.json`,
  `DAILY_CAP=3`, `content/upload_log.json`. Pages: kongkeat938.github.io/ai-content-lab/.
- **Pod env:** recycled often → reinstall `ffmpeg` + `pip install -r requirements.txt`; export
  `GH_TOKEN=$KONGKEAT_GH_TOKEN`. Full suite: `for t in scripts/test_*.py; do python3 "$t"; done`.
