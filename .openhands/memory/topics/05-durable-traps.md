# 05 — durable traps (the long form)

Detail behind the one-liners in `MEMORY.md`. Read on demand; do not paste back into the
index. Newest first. Every item here was measured, not assumed.

## Rogue upload stream (2026-11-11) — NOT in-repo code
- Videos appear on the channels that **no manifest names**, carrying
  `defaultAudioLanguage=en-US`, category **27**, the old brand `เรื่องเล่าการ์ตูน`, at a fixed
  **`:21`** minute. Our rails run at `:44`, write `th`, categories 22–24. Confirmed on all 3.
- `git log -S 'en-US'` / `-S 'เรื่องเล่าการ์ตูน'` over `scripts/`: our code never wrote either.
- Panel (4 valid advisors, unanimous): the source is **external** — a legacy/leaked OAuth
  token on another publisher, or a forgotten third-party auto-publish (Zapier/Make/Buffer).
- `audit_channels.py --alert` opens/self-clears a GitHub issue (#22) and splits the **live**
  rogue stream (unrecorded, published ≤ `RECENT_DAYS`=3) from the **historical pre-manifest
  backlog** — a take-down must never hide legitimate old videos.
- `--hide-live-rogue` sets each LIVE rogue clip to `privacyStatus=private` (reversible), records
  it in `content/rogue_hidden.json` (idempotent), comments the take-down on #22. Never deletes.
- Our tokens hold the full `youtube` scope, so they *could* do this; rotation of the refresh
  token would stop the rogue stream **and** every one of our own rails until K re-consents.
- Two silent CI failures made the alert "open nothing": a missing `GH_TOKEN` on the step, and a
  missing `google-api-python-client` install (`ModuleNotFoundError: googleapiclient`). Guards:
  `test_audit_unrecorded.py`, `test_hide_rogue.py`. Also: `alert_live_rogue` must NOT close the
  issue when **nothing was measured** (a spent read-quota looks like "no rogue stream").

## The delete loop (2026-11-11)
- `remove-bad-cut.yml` tried to delete the 57-min dharma cut `HkbSguA53ro` (~37×/day) and failed
  every time: the guarded delete refuses `views > --max-views 5`, the views kept rising
  (0→25→31→44→53), and `.done` was written **only on a successful delete** → a refused delete
  looked identical to a pending one, so it retried forever.
- Fix: `delete_video.py --unpublish` sets `privacyStatus=private` (reversible, not gated on
  views) and writes `.done` on the skip path too. `remove-bad-cut.yml` calls it.
- Lesson: a guard that only marks success cannot terminate a loop it will never satisfy — a
  skip/refuse path must also mark itself done. Prefer reversible over irreversible.
- Guard `test_delete_unpublish.py` (proven FAIL both ways). Decision: `docs/DECISION-2026-11-11d.md`.

## Branding (2026-11-11)
- A PUT to `brandingSettings.channel` **replaces the whole object** — writing only the trailer
  wiped description/keywords/defaultLanguage. `channel_overhaul.set_trailer` now reads the live
  object and merges. `channel-branding.yml` keeps it a standing invariant (foreman-driven).
- `brandingSettings.channel.country` is **not writable** (PUT returns 200, value stays null).

## Night rail traps (2026-11-09)
1. **`skip` ≠ `skip_pub`** — "the release exists" is not "the video is queued";
   `scripts/night_built_queued.py` splits them.
2. **`qa_gate` vetoed every 120-min build** (old `LEN_WARN_MAX=90`) — the rail vetoed its own
   format; raised to 150.
3. **Ordering** in `add_release_to_manifest.py`: `hit.update(entry)` merged BEFORE `apply_qa_gate`
   → the fresh verdict never reached the manifest. Gate first, then `queue_entry()`.
- **An empty receipt is not a bad video** (`grade({})=blocked` = false veto); the build uploads
  `receipt.json` to the Release and the hand-off downloads it.
- **A transient empty run list is not a dead rail** (2026-11-12): `health.py` read
  set-thumbnails as "never succeeded" while it had 29 successes — a proxy/rate blip returned an
  empty page. Now a workflow whose runs-page comes back empty is retried, then marked
  `unreadable` (a gap, exit 0) — never "never succeeded". Guard `test_health_blind.py`.
- **A long hook kills retention:** `content/hooks/dharma.md` was 361 chars → **40.3 s** (edge-tts
  Thai ≈ 9 chars/s) matching 28.9%@2:00; now 171 chars (~19 s). Cap in `test_hook_concrete.py`
  (220). **CORRECTED 2026-11-12:** the fingerprint DOES include the hook file
  (`night-compilation.yml` hashes `content/hooks/dharma.md`; genx/ch4 likewise), so a hook edit
  DOES trigger a rebuild — the earlier note claiming otherwise was stale.
- **`publish_at=slot` uploads PRIVATE**; YouTube flips it public at 19:30 Bangkok (12:30Z).

## 2026-11-09 defects fixed
- Progress report inflated YPP hours up to 92× (compared channel totals to the long-form bar);
  `analytics.py` now splits by `creatorContentType` (`shorts`/`videoOnDemand`).
- Learning loop went blind on a spent `videos.list` quota → titles from committed manifests then
  YouTube **oEmbed** (no auth/quota), cache `content/titles/<ch>.json`.
- Health cried wolf + 6 foreman rails invisible (one dead: `fetch-music` missing `numpy`).
- Foreman DOWN ~6 h from raw git-conflict markers in `content/upload_log.json` → union-resolved.

## 2026-11-08
- The killer was a **single static card** for a 120-min file (AVD 5.2%) → `make_chapter_video.py`
  (one card per piece, `MAX_CARDS=30`) + a spoken hook + 20–30 min length.
- Search blocker = packaging → `make_cover_youtube.py` + `apply-packaging.yml`.

## 2026-11-07
- genx long-form rail; a playlist id must be written into the manifest entry **and** inserted by
  `publish_batch.py` (writing the entry is not enough).

## Mail / PC1
- `account-watch.yml` reads IMAP from the `IMAP_ACCOUNTS` secret; measured it holds only
  `ch1@example.invalid` → dharma/kongkeat-story inboxes NOT read yet (report names them).
- PC1 is dead (Smart App Control blocks the unsigned runner; tailnet NXDOMAIN) → do NOT retry;
  route around it. `docs/PC1-*.md`.

## Quota
- `videos.insert` has its own pool (an upload can succeed while reads 403 all day); Data API
  resets **08:00 UTC**; Analytics has its own quota. GITHUB_TOKEN push does NOT trigger a
  workflow → dispatch explicitly (`KONGKEAT_GH_TOKEN` can).

## Racing jobs lose records (2026-11-09)
- publish-shorts and remake-shorts for one channel pushed at once; `--autostash` + `check=True`
  hid a conflict in `content/upload_log.json`, a live remake id was never recorded, and a 403'd
  privacy move vanished. Fix = one **shared concurrency group per channel** +
  `scripts/git_union_merge.py` (`.gitattributes merge=unionjson`). Guard `test_union_merge.py`.

## Silent config-key misses (2026-11-11)
- `advise.ADVISORS` had no plain `"gemini"` key, but 4 scripts asked for it and each did
  `.get(name)` + `continue` → the light panel ran on pollinations alone (or nothing) for days.
  Fixed: `"gemini"` alias, one shared `advise.LIGHT` team, `advise.advisor()` that **raises** on
  an unknown name. Same class: `studio_ai.TOPICS_HINT` keyed `"kongkeat"` but called with `"ch4"`
  → the tension hint never reached the panel. Lesson: a guard that checks only the output file
  misses the wiring; `.get()+continue` on a config key is a silent killer — make it loud.

## ch4 (kongkeat-story) — subs flat (2026-11-09)
- Shorts work, long-form dead: 28 d top Shorts 1,083/40%, 1,079/104% loop, 461/115%; every
  120-min long-form gets 1–3 views. **subs/1,000 views = 1.93** (dharma 2.92, genx 5.36).
- A Short must not promise a "full clip" it cannot deliver (12/71 CTAs did); `gen_short_scripts`
  has a per-channel `forbid_cta`; `test_ch4_cta.py` locks it.
- `unsubscribedTrailer` was never wired (`channel_overhaul.py --only playlists` everywhere); now
  ch2/ch4 run the full overhaul, ch1's trailer lives in publish-ch1; `test_repo_hygiene` forbids
  `--only playlists`. Must run **after** the 08:00 UTC reset (ch1 08:07, ch4 08:05, ch2 08:40).

## A rebuild of a LIVE key must not un-publish it (2026-11-12)
- The night rail keys a weekly build by ISO week (`night_auto_<YYWW>`); the fingerprint
  includes the rail's own scripts, so ANY rail edit (e.g. the fade-in fix) forces a rebuild of
  the same key. If that key is already published, the hand-off must NOT reset `state=ready`
  beside the live `video_id` — one `--forget` away from a duplicate upload. Fix:
  `apply_qa_gate`/`queue_entry` never downgrade a live entry; only `--forget` clears the id.
  publish-batch's `video_id` guard is the backstop (measured: "already live … skipping").
- Corollary: a guard that hardcodes a set goes stale. `test_qa_gate` now sweeps `LEN_OK_BANDS`.

## Two false-alarm classes fixed the same day (2026-11-12)
- **qa_gate** flagged every intended 120-min file ("outside the 15-35 min band") → grade B
  forever. The intended formats are 15-40 AND 110-130 min. Text/constant must match the code.
- **counter_ledger** read a same-UTC-day dip (YouTube revises today's row) as "counter went
  DOWN". Skip the monotonic check only within one UTC day; a cross-day drop is still a violation.
- **health** flagged paused rails (`publish-ch4`/`ch4-longform`) as "never succeeded". It now
  reads `content/PAUSED` and reports them as "paused (quiet on purpose)".

## Shorts visuals had no guard; the "strange image" was the Commons fallback (2026-11-12)
- Shorts art = Pollinations AI (seeded per clip) -> when rate-limited it fell back to a
  RANDOM Wikimedia Commons photo unrelated to the script. Panel: drop it, use a branded
  gradient (`from_procedural`). Commons is out of `gen_cover_image.generate()` now.
- The Shorts caption hook sat at 0.42H while the backdrop scrim starts at 0.55H -> the one
  line that must read landed on bright art (~1.4:1). Fixed with a dark panel (6.5:1).
  Guards: `test_short_caption.py` (in-frame sweep + contrast over the brightest art),
  `test_cover_image_source.py` (no Commons fallback). Long-form had qa_gate; Shorts had
  none -- a format with no guard drifts.

## Delegation detail (Option B, 2026-11-13)
- genx + dharma: `ch3@example.invalid` is **Manager** (accepted); `YT_CH1/CH2_ALT_REFRESH_TOKEN`
  set. kongkeat-story: **BLOCKED** -- its owner is `ch4@example.invalid`, the pod's Chrome is
  signed in ONLY as `ch2` (AccountChooser lists just that), there is NO login secret, and
  K forbids asking K to log in. Measured: ch2 has NO Brand Account; dharma/genx are direct
  channels, not Brand Accounts.
- **`READY` needs TWO legs** (`delegate_ready.py`): the token **exchanges** AND a probe **upload**
  succeeds (~1.4 KB private video, deleted in the same run). Measured 2026-11-13 in CI:
  `LIMITED genx` and `LIMITED dharma` -- both exchange, both `400 uploadLimitExceeded`. A credential
  that only exchanges reads **LIMITED**, never READY.
- The alt refresh token is bound to the OAuth **client B** (`YT_ALT_CLIENT_ID/SECRET`); exchanging
  it with the primary client gives `401 unauthorized_client`.
- `mine=true` lists only the account's own channel (`AERIS Music`), never a managed target.
- No rail uses any `*_ALT_*` token; `publish_batch.py` has a `WRONG_CHANNEL` guard.
- Adding a Manager needs the OWNER password (Google "ยืนยันว่าเป็นคุณ"); the pending row vanishes on
  reload if the save failed -> verify by reloading สิทธิ์.
- `uploadLimitExceeded` on a fresh manager is a YouTube gate on the delegate's OWN account, not our
  code: `aerismusic8` must clear its upload eligibility (channel verify / terms / daily cap) before
  the probe passes. Until then K is still the only one who can change a rogue grant.

## Browser Live View detail (2026-11-13)
- `scripts/browser_live.py` on port 12000 (work-1): CDP `Page.startScreencast` out +
  `Input.dispatchMouseEvent`/`KeyEvent` back, over one aiohttp websocket. No X/RFB.
- Cannot show OS-level dialogs (native file picker, basic-auth) → keep noVNC (12001) as fallback.
- Guard `scripts/test_browser_live.py` (fake CDP; proves the guard can FAIL). Panel 4/5 ranked
  CDP > VNC > Xpra > Guacamole > WebRTC for a non-root, no-GPU, recycled pod.

## Repo hygiene: the mess K complained about (2026-11-13)
K (2026-11-13): *"อย่ามั่ว — อะไรที่เคยทำได้อยู่แล้วไม่ควรทำซ้ำ; ค้นความจำก่อนตัดสิน; อย่าเก็บทับด้วยชื่อใหม่"*.
Whole-repo audit anchored to the ONE project goal `yt938-2` (YPP). Measured, then fixed:
- **5 orphan scripts** (zero references anywhere): `pod_mail_login`, `backfill_short_links`,
  `gen_branding_art`, `probe_advisors`, `studio_drive` -> moved to `scripts/legacy/` (archive, not
  delete). `pod_mail_login` was a **duplicate login path**; the ONE path is
  `pod_account_login.py --from-secret` + `fetch_secret.py`.
- **`docs/AGENTS.md`** was a stale copy (last touched 2026-11-10; root is live) -> deleted; root
  `AGENTS.md` is the only one.
- **The login churn had a cause ak had missed:** `pod_account_login.py --from-secret` reads the repo
  secret **`OWNER_LOGIN_PASSWORDS`**, which did NOT exist -> ak typed the password by hand. Fixed:
  set the secret (JSON map of owner email -> password). `fetch_secret.py OWNER_LOGIN_PASSWORDS`
  now decrypts it on the pod (146 chars measured), so a recycle can be re-logged-in with no K.
  The ONLY unavoidable human step is the Google 2FA "tap Yes" on a NEW device.
- **Guard added:** `test_project_map.py` — fails if a `scripts/*.py` (non-test, non-legacy) is
  referenced nowhere, or if `docs/PROJECT-MAP.md` is missing. It must be able to FAIL.
- **The map:** `docs/PROJECT-MAP.md` = the single anchor (goal, live rails, one login path, where
  truth lives, conventions, archive list). Read it before creating anything.

## Rogue watcher false pass: a dead RSS feed read as "clean" (2026-11-16)
`scripts/rogue_watch_rss.py` (the no-quota step of `rogue-guard.yml`, the safety net
during the quota-blind window) read each channel's public RSS feed and printed
"no live rogue upload on any channel feed" -- but `https://www.youtube.com/feeds/
videos.xml?channel_id=...` returned **404 for EVERY channel** (measured from the
pod proxy, from CI, and from a residential IP on PC1). A scan that measured nothing
was indistinguishable from a clean scan: the classic **false pass**.
- **Fix 1 -- a working no-quota source:** fall back to the uploads playlist page
  `https://www.youtube.com/playlist?list=UU<id>` (swap `UC` -> `UU`). It still
  returns 200 with up to 100 uploads; parse `ytInitialData` -> `lockupViewModel`
  (`contentId`, `metadata.lockupMetadataViewModel.title.content`, and a relative age
  in `metadataRows[].metadataParts[].text.content` like `"2d ago"`). Force
  `Accept-Language: en-US` + `&hl=en` -- the age labels are LOCALIZED, so a Thai
  response makes every age unparseable and drops a fresh rogue silently.
  (`/videos` and `/shorts` tabs also work but the Shorts tab carries NO age; the
  `UU` playlist is the closest replacement for the old feed.)
- **Fix 2 -- no silent blind:** `scan()` returns `(rogue, blind)`. A channel no
  source can answer for -- or a source that answers with ZERO entries (broken
  selector) -- is BLIND. `main()` exits **2 (BLIND)**, distinct from 0 (clean) and
  1 (rogue); `rogue-guard.yml` fails the step on 2 as well as 1. `continue-on-error`
  was REMOVED from the scan step (it hid the false pass); the pausing step keeps it.
- **Guard:** `scripts/test_rogue_rss.py` covers the fallback parse, the age labels,
  the blind path, the empty-source path and the source fallthrough; mutation-tested
  (ignoring the `d` unit, returning `[]` for a blind page, ignoring `age_days`, and
  not recording blind channels are each caught).
- **Verify (live):** `rogue-guard` run 43810752542 on commit `959c673b` = success,
  log "no live rogue upload on any channel feed" (NOT "BLIND") = the fallback
  measured every channel.


## PII lives in HISTORY too (2026-11-16)
`test_no_committed_pii.py` scans the tree only. Real addresses were committed in CONTENT **and
commit MESSAGES**; a tree-only scrub leaves them in history on a PUBLIC repo. Fix = git-filter-repo
with BOTH `--replace-text` and `--replace-message`. Non-interactive gotcha: delete
`.git/filter-repo/` before re-running (the stale `already_ran` file makes filter-repo call
`input()`, which dies with `OSError: Bad file descriptor`). Freeze CI first (disable workflows +
cancel runs) so the self-chaining rails cannot clobber the rewrite, then force-with-lease.
A FORK keeps the old history and cannot be fixed without the fork owner's admin rights.


## A take-down claim needs a 2nd source (2026-11-17)
`audit_channels.find_removed` diffed the manifest against ONE `playlistItems.list` read. That read
can come back short (genx 2026-11-17: `uploads=154` while yt-dlp `--flat-playlist` = 147; the count
wobbled 149/150/154 across runs) → every recorded clip the short read missed was reported as
"removed by YouTube". Six such false take-downs (lyaxLTHyITY, zRZURbXEpuE, l5hkDGVIYXE, L8OQn6RTVaY,
12RT8zATxuo, 9Okw0yYB97A) -- all oEmbed 200, all in the public uploads playlist; the flags ROTATED
run-to-run (same id never twice in a row) = a flaky read, not a removal. Fix: `oembed_alive()`
(quota-free): 200/401/403 = exists, 404 = gone, else unconfirmed; `find_removed(..., still_live=)`
vetoes a live clip and marks an unconfirmed one as unconfirmed. Control ids: `AAAAAAAAAAA`=404,
`NlxhKLTuQp4`=403. Same class as the `rogue_watch_rss` "dead source read as clean" trap: a single
source is never proof -- diff it against a second one.
