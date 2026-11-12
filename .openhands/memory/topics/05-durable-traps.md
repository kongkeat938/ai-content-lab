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
- **A long hook kills retention:** `content/hooks/dharma.md` was 361 chars → **40.3 s** (edge-tts
  Thai ≈ 9 chars/s) matching 28.9%@2:00; now 171 chars (~19 s). Cap in `test_hook_concrete.py`
  (220). ⚠️ the fingerprint does NOT include the hook file → a hook edit alone won't rebuild.
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
  `kongkeat.938@gmail.com` → dharma/kongkeat-story inboxes NOT read yet (report names them).
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
