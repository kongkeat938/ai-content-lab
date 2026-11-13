# Project Memory — ak (ai-content-lab)

**Agent `ak`**. Owner **K**: Thai replies, **measured evidence, not claims**; ak decides via the
**panel** (`advise.py`), not K. **This file is a MAP** (injected each session, tail truncated):
keep <6,000 chars (`test_memory_budget.py`); detail in `topics/`, logs, `docs/`.
**Project = `yt938-2`; read `docs/PROJECT-MAP.md` first. Search before creating — never make a
second copy under a new name (K, 2026-11-13; `test_project_map.py`).**

## 🪪 ak's identity & team (K, 2026-11-13)
ak **owns a mailbox** (`ak_mail.py`): use it, never K's; **never sign up as K**; a phone ak can't
own → **ask K**. **Workers** (`team.py run <role>`: researcher/scriptwriter/packager/critic/analyst
+ engineer) DO the work; the panel (`advise.py`) only advises.

## 🎯 What gates the business (`docs/DECISION-2026-11-09.md`)
- **YPP watch-hours = long-form ONLY** (Shorts don't count). Steer by long-form watch-hours/week +
  `retention@2min`, never raw views. **dharma = 96% of long-form watch time → concentrate there.**
- **The first 2 minutes is the binding constraint** (dharma 28.9%@2%, target ≥40%). **Fade-in 4s→1s**
  = **+12 dB** in the opening second — the hook is the lever.
- **Watch-time/view rises with length:** 120-min ≈ **6.0 min/view** vs 17-min ≈ 4.6 — keep videos
  long. **`content/PAUSED`** pauses a channel's rails (mechanism proven by `test_paused_channel.py`).

## 🔑 Durable principles (K)
- **PCSEV = Problem→Cause→Solution→Execute→Verify.** Verify **live** — trust order:
  **live API > real output file (ffprobe/ebur128) > a test that can FAIL > a committed doc**.
  Best = a **counter with an invariant** (`scripts/counter_ledger.py`).
- **Times to K = Thai (UTC+7), 24-hour `HH:MM`** (never raw UTC).
- **"แยกไม่ได้" ≠ "ผิด":** a Data-API identity check dies on a spent quota → use **per-channel
  secret = identity** (`YT_CH{1,2,4}_REFRESH_TOKEN`; `test_channel_identity.py`).
- **An LLM is not a primary source** — read the vendor's rule or measure live. Panel `advise.py`
  (≥5). Do NOT retry ChatGPT/PC1/DeepSeek/Devin/HF.
- **A guard must be able to FAIL;** never hardcode the set a guard sweeps; a generator that can
  drop a piece must FAIL. `.get()+continue` on a config key is a silent killer.
- **Repo hygiene** (`test_repo_hygiene.py`): pushing rails run `git pull --rebase`; a shared-ledger
  writer needs a guard; health thresholds must exceed the REAL cadence; every rail watched.

## 🧭 Traps still true (one line each; detail in `topics/05-durable-traps.md` + daily logs)
- **Rogue upload stream (NOT ours):** clips no manifest names (`en-US`/cat 27) = leaked token;
  `rogue-guard` hides each, root = revoke + re-consent.
- **A guard that only marks SUCCESS can't end a loop it never satisfies**; prefer reversible
  (private) over delete, and mark the skip path.
- **A PUT to `brandingSettings.channel` REPLACES the whole object** → read live, merge.
- **`--minutes` is a FLOOR** (under-N set is heard twice). **`publish_at=slot` uploads PRIVATE**
  (YouTube flips it public at the slot) — intended, not stranded.
- **Quota:** `videos.insert` has its own pool; Data API resets **08:00 UTC**. GITHUB_TOKEN push
  does NOT trigger a workflow → dispatch explicitly.
- **Racing jobs lose records** → one concurrency group per channel + a union merge driver
  (`git_union_merge.py`) for append-only ledgers.
- **Night rail:** `skip` ≠ `skip_pub`; empty receipt ≠ bad video; gate before queue; a long hook
  kills retention (cap 220); never downgrade a LIVE entry (`--forget`). `test_night_*.py`.
- **Every new mechanism seeds a false alarm until the sweep learns it** (2026-11-12): qa_gate graded
  120-min files B; counter_ledger read a same-day dip as DOWN; health flagged paused rails.
- **Pause is per channel** — prove the mechanism with a synthetic PAUSED (`test_paused_channel.py`),
  so it passes whether or not a channel is paused today.
- **We were blind to a take-down** (2026-11-13): the audit diffed only channel→manifest → `find_removed`
  (`test_audit_removed`). **Mail is on the cloud, not PC1** (dead); `IMAP_ACCOUNTS` = kongkeat.938 only.
- **ch4 UNPAUSED 2026-11-13** (K: "ลุย ch4"): the flat-scene hook that killed it (13.7% mid-retention)
  → a tension hook is **enforced** (`test_hook_concrete`) for the long-form hook AND the Shorts pool;
  new scripts in `ch4_shorts/scripts.json`; no "full clip" CTA (`test_ch4_cta.py`).

## 🗺️ Topic map (read on demand)
- `topics/*.md` · `docs/DECISION-*`/`PANEL-*`/`HEALTH.md` · daily logs.
- **Automation:** GH Actions only (watchdog → foreman → rails); kill switch `content/STOP`.
  **Publishing:** `content/<ch>_publish.json`/`_shorts.json`, `DAILY_CAP=3`.
- **Accounts:** 1 channel = 1 Google account — genx `kongkeat.938`, dharma `farmmer.938`, ch4
  `kongkeat.p3` (own 19/day pool each); `test_channel_accounts.py`. Invite = **Studio → การตั้งค่า →
  สิทธิ์ → เชิญ**.
- **Delegation:** genx+dharma → `aerismusic8@gmail.com` Manager; `delegate_ready.py` needs a token
  AND a probe upload — 2026-11-13 LIMITED (`uploadLimitExceeded`, API path only; web Studio works).
  kongkeat-story BLOCKED. Login `pod_account_login.py --from-secret`; never ask K. → `topics/05`.
- **Inviting needs the OWNER's password** (K): **บันทึก** triggers Google "ยืนยันว่าเป็นคุณ"; a pending
  row **vanishes** on reload if the save failed → verify by reloading สิทธิ์. **Studio: CDP
  `Input.dispatchMouseEvent` works; JS `.click()`/XTest do not.**
- **Pod env:** recycled often → reinstall `ffmpeg` + `pip install -r requirements.txt`; export
  `GH_TOKEN=$KONGKEAT_GH_TOKEN`. Suite: `for t in scripts/test_*.py; do python3 "$t"; done`.
- **Remote-in:** **Browser Live View** (`browser_live.py`, 12000) = tab over CDP (no OS dialogs);
  **noVNC** (`start_novnc.sh`, 12001) = fallback. → `topics/05`.
- **Comment writes need `force-ssl`** (`yt_auth.py --scopes force-ssl`); text must fit its frame
  (`test_short_caption`, `test_poster_fit`); pinned CTA comment = the conversion lever.
