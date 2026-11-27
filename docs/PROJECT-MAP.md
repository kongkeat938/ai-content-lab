# PROJECT-MAP — yt938-2 (the one map; read this before creating anything)

**Project:** `yt938-2` — run 3 Thai YouTube channels toward monetisation (YPP).
**Goal:** YPP = **1,000 subscribers + 4,000 long-form watch-hours / 12 months**.
**Steer by:** long-form watch-hours/week + `retention@2min` (Shorts do NOT count toward YPP).
**Focus:** **dharma** (96% of long-form watch time). **genx** = Shorts engine + subs.
**PCSEV** = ch4 (internal slug `kongkeat-story`), **LIVE** (@PCSEV). Paused 2026-11-12,
**UNPAUSED 2026-11-13** on K's order — `content/PAUSED` has no active line.
**Direction (measured live 2026-11-21):** เกร็ดความรู้/วิทยาศาสตร์ "ทำไม…" — the 5-step
P/C/S/E/V explainer, Shorts-first (12/12 newest uploads are `#Shorts`); the family/story genre
is retired (its 4 long-forms are published and the queue is closed).

> Rule (K, 2026-11-13): **search this map first. If a thing already exists, use it —
> do not create a second one under a new name.** New file? add it here in the same commit.

> **STATUS 2026-11-21 (measured, not a doc claim) — there is NO `content/STOP` file (removed at
> `eec3d78` on K's order), but **29 workflows are `disabled_manually`** (9 active), so no rail
> produces or uploads on its own. Standing shape: **manual production by ak; K orders every
> upload**; a deliberate manual run passes `CONTENT_STOP_PATH=/tmp/nostop`. Do NOT re-enable the
> rails without K. The NEW system K is building = VIDEO-SYSTEM-NEW (spec
> `docs/VIDEO-SYSTEM-NEW.md`; recovered code + gaps in `recovered/VIDEO-SYSTEM-NEW/`, see its
> README).**

> **Durability (K, 2026-11-21 — the pod is recycled, so loose work is lost):** a session MUST
> leave the repo pushed. `scripts/durability_guard.py` FAILS on an uncommitted/unpushed tree or
> an untracked vault/queue; `scripts/restore_env.sh` reinstalls the AI libs after a recycle
> (weights download on first use, so nothing big lives only in the pod). Test proves it can fail.

> **GitHub push needs no human (2026-11-22):** `scripts/gh_auth.py status|setup|push` restores the
> credential from the KV vault (`ak.github.token`) with `OPENHANDS_API_KEY` alone — `GITHUB_TOKEN`
> is read-only and the classic PAT was revoked. Push through it, not raw `git push`: `gh` hands
> git the read-only env token first (403 "denied to kongkeat938"). Revoke the grant at GitHub →
> Settings → Applications → Authorized OAuth Apps → gh CLI.

---

## 1) The rails that matter (34 workflows; the ones driving the goal)

| Workflow | When (UTC) | Does | Goal link |
|---|---|---|---|
| `foreman.yml` | `*/30` | dispatches every due rail | the driver |
| `watchdog.yml` | `45 */4` | self-chaining keeper | keeps rails alive |
| `publish-batch.yml` | `17 */3` | uploads ready long-form | the long-form pipeline |
| `night-compilation.yml` | Mon 02:17 | builds 120-min dharma compilations | **watch-hours engine** |
| `publish-shorts.yml` | 01/09/17:30 | uploads Shorts | reach + subs |
| `studio-ai.yml` | 21:45 | Analytics → panel → insights | the learning loop |
| `counter-ledger.yml` | 04:43 | invariant counter | **the proof meter** |
| `account-watch.yml` | 08:42 | delegated-credential probe | guard (delegate publish) |
| `rogue-guard.yml` | `*/30` | hides live rogue uploads | containment |
| `progress.yml` / `watch-hours.yml` | 07:12 / Mon 06:17 | YPP progress | the scoreboard |
| `channel-branding.yml` / `ch2-playlists.yml` / `set-thumbnails.yml` | after 08:00 | packaging | search + conversion |
| `link-shorts.yml` | driven by the foreman | appends the long-form playlist link to every Short's description (the reach → watch-hours funnel) | **the funnel** |
| `publish-motion.yml` (`publish_motion.py`) | on demand (workflow_dispatch) | ships an animated-still Short through the SAME gates as publish-shorts: cap, gap, `short_standard` gate, bed ledger, `record_key` namespacing | a livelier Shorts shape (reach) that cannot dodge the Shorts rules |
| `make_motion_short.py` (the builder behind that rail) | called by the rail | layers match the story's `genre` -- dharma/genx = calm (twinkle + petals, no mascot, no glow disc), knowledge = a mascot dancing to the beat | the visual itself |
| `longform-standard.yml` (new 2026-11-21) | **manual dispatch only** (`spec`, `out`) | runs the approved `longform_clip.py` on a GitHub runner (not the pod: two pod runs died ~19 min in), gates it with `clip_standard.py`, and puts the MP4 on a Release + artifact for K. **Never uploads.** | the long-form watch-hours lever |
| `make_ambient_video.py` (a tool, not a rail) | by hand | stitches real b-roll (`fetch_broll.py`, Coverr) into one long 1080x1920 ambient video, looped to `--minutes`, bed at -14 LUFS | the "join clips + 3-min music" edit K wanted, done headless |

| `make_mv.py` + `mv_run.py` (MV series, new 2026-11-22) | by hand, repeatable | builds a music video: **fresh art per MV**, gated (-14 LUFS, TP<=-3.0, 1080p tv), published, and stamped image->MV->URL in `content/art_ledger_mv.json`. Art source chain: gemini image -> pollinations -> procedural `generative_art.py` (both AI routes were down 2026-11-22: 429 quota / 503). Guard `test_mv_fresh_art.py` FAILS on a reused image, a missing stamp, a missing file, or an unverified video | long-form watch-hours without narration |

| `content_ledger.py` (story no-repeat, new 2026-11-22) | checked by `build_night.py` before every render, stamped after a passing gate | `content/content_ledger.json` records each video's parts (text sha256), music bed, visual arc and title. A part that already aired makes the build exit 3. `check` fails on a shared part, a repeated title or a repeated bed on one channel; 18 older videos sit in `unverified` with the reason (no source field existed). Guard `test_content_no_repeat.py` | **the "new story every clip" rule** |
| `upload_gate.py` + `purge_sub4k.py` (K's 4K rule, new 2026-11-23) | called by `publish_shorts.py`, `publish_youtube.py`, `standard_clip.py` and `writers_room.py` before every upload; `purge_sub4k.py --dry-run --dirs` sweeps the disk | **4K only** (a Short ≥2160x3840, a long ≥3840x2160; a 1080p file is refused, not "almost 4K") **and nothing repeated**: md5 picture, music-bed id, script n-gram ≥45%. A cached sub-4K build is rebuilt, never re-uploaded. `purge_sub4k.py` exits **2 BLIND** without ffprobe. Guards `test_upload_gate.py`, `test_all_builders_4k.py` (every builder renders 4K), `test_no_repeat_paths.py` | **the upload bar** |

All rails are GitHub Actions only (the pod is recycled when idle). Kill switch = `content/STOP`.

## 2) The one login path (do NOT add a second)

- **Headless (no human, the normal path):** `scripts/yt_auth.py` — refresh token in a repo
  secret. `scripts/fetch_secret.py NAME` pulls any repo secret onto the pod (encrypted transit,
  `.github/workflows/cred-transport.yml`). `scripts/revoke_token.py SLUG` proves a leaked token is
  dead (tri-state: "not measured" never reads as "dead").
- **K's phone — the ONLY path that asks K (new 2026-11-22):** `scripts/yt_auth_device.py` — Google
  device flow. ak prints `https://www.google.com/device` + an 8-character code; K types it on the
  phone and taps Allow (the phone's autofill and biometrics do the rest). **Never** ask K to log in
  through noVNC/PC1: on a phone the remote screen cannot be scrolled or zoomed and reaching the
  password field is a fight (K, 2026-11-22). Guard `scripts/test_yt_auth_device.py`.
- **Pod browser login (only when Studio needs it):** `scripts/pod_account_login.py`
  (`--from-secret` reads `OWNER_LOGIN_PASSWORDS`). Password is **never** typed by hand or by K.
- **Do not** add another login script. `scripts/legacy/pod_mail_login.py` was a duplicate → archived.

## 3) Where the truth lives (do not duplicate these)

- Goal + rules: `docs/GOAL.md`, `AGENTS.md` (root only), `docs/DECISION-*.md`.
- Money math + the four income paths ranked: `docs/DECISION-2026-11-27-money-math.md`
  (live subs/views per channel, distance to YPP, why the bottleneck is sending the offer).
- The one sales step left: `docs/FASTWORK-LISTING-2026-11-27.md` — paste-ready gig fields, prices
  generated from `content/packages.json`, the delivery runbook, guarded by `test_portfolio_prices.py`.
- Goal consults / panels: `docs/CONSULT-*.md` (the brief + the answer, incl. the measured numbers)
  and `docs/PANEL-*.md`. `docs/GROWTH-PLAN-*.md` is the plan that follows a consult. The latest
  goal consult is `docs/CONSULT-2026-11-18-goal.md` (Gemini alone) — it also records where
  Gemini's advice **conflicts with the measured data** (genx subs).
- Client offer + outreach pack: `docs/OFFER-2026-11-25.md` (packages, prices, paste-ready Thai
  message, 12 measured prospect channels, the send-it-yourself constraint, 30-day stop rule).
  Demo assets: releases `demo-shorts-2026-11-25`, `demo-story-2026-11-25`.
- Customer demand: `prospect_discover.py` reads public request pages (freelancer.com,
  craigslist, freelancermap, HN Algolia), honours robots.txt, keeps the URL + found/checked
  dates, dedupes, and expires 404s → `content/prospects_external.json`. Guard
  `test_prospect_discover.py`. Daily rail `.github/workflows/prospect-daily.yml` (02:00 UTC =
  09:00 Thai).
- Offers: `proposal_draft.py` scores each request (budget, format fit, volume, verified
  payment, deadline), refuses work we cannot do (animation/avatar/3D), quotes the canonical
  price and writes `content/proposals/<id>.md` with status **draft** — no send path. Guard
  `test_proposal_draft.py`.
- Price: `content/packages.json` is the only source (A 490/5, B 750/10, C 1590/20).
  `net_revenue.py`, `build_portfolio.py` and every draft read it; `test_portfolio_prices.py`
  fails when the doc or the page drifts.
- Portfolio: `docs/portfolio/index.html` (generated, GitHub Pages → /portfolio/) with three
  self-made samples in `docs/portfolio/media/`. `make_samples.py` renders and then gates them
  (1080x1920, 15-60s, audio present, -14 LUFS); guard `test_make_samples_gate.py` feeds it a
  bad file. Thai font `assets/fonts/NotoSansThai.ttf` (OFL) is committed so rendering does
  not depend on apt.
- Sales rail: `prospect_score.py` (0-100, writes `content/prospects.json` — these are
  **prospects, not verified buyers**), `outreach_log.py` (status + 14-day cooldown that also
  covers `declined`; orders go created→paid→delivered→approved/refunded, and `report` counts
  only money received), `net_revenue.py` (fees → net → orders needed for 5,200).
- Delivery: `deliver.py` packs clips+thumbs+`manifest.json` (sha256 each) into `<order>.zip`
  and reads the zip back to verify. Guard `test_deliver.py` (truncated clip must be refused).
- Durability: `restore_verify.py` exports the committed tree and checks the business state is
  in it (guard `test_restore_verify.py`); `run_tests.py` + `.github/workflows/tests.yml` run
  the whole suite on every push/PR. Guards `test_workflow_tag_safe.py` (tag push ≠ rail).
- Channel facts: `channels.json`, `.openhands/memory/topics/00-*.md`.
- Channel NAMES: a channel's main title is **not API-settable** — K sets it in Studio, so the
  repo *follows* the live name (verified quota-free from RSS / channel page / oEmbed). Single
  writer `scripts/set_channel_name.py` (`TARGET`); ch4 = **PCSEV** (@PCSEV). The bare genre word
  ("เกร็ดความรู้รอบตัว") stays in keywords/SEO — only the channel-name labels/phrases are PCSEV.
  Guard `scripts/test_ch4_channel_name.py` (fails if a rail would write the retired name back).
- Measured history: `docs/STATUS-<date>.md`, `docs/counters.jsonl` (the counter), `docs/HEALTH.md`.
  Latest: `docs/STATUS-2026-11-22.md` (live counters, 28-day LF watch-hours 82.7, the two new
  long clips got 4 and 2 views in 11 h = distribution is the bottleneck).
- **THE NEW SYSTEM — A/B generative-art → parallel-pipeline (2026-11-19; the newest production
  system — search here first, do NOT rebuild it under a new name).**
  - **A (render):** `python3 scripts/parallel_pipeline.py art --pool work/pool --count N` →
    `scripts/generative_art.py` (SD-Turbo 640→RealESRGAN×4 via `spandrel`) writes PNGs into the pool.
    Runs on PC1 **or** this pod (needs `torch`/`diffusers`/`spandrel`).
  - **B (build):** `python3 scripts/parallel_pipeline.py clips --pool work/pool --stories content/motion/*.json`
    → claims a picture (never twice; `make_short.ledger_lock`) and builds a clip via `make_short` **with
    music**, gated through `short_standard.verify_short` (the same gate as upload). Reads `library_art`
    over HTTP (`ART_LIBRARY_URL`) when the pool is empty.
  - **Upload:** `publish-motion.yml` (`publish_motion.py`) ships an animated-still Short through the same
    gates (cap, gap, `short_standard`, bed ledger, `motion-<id>` namespacing).
  - **Proof it is decoupled:** `test_parallel_pipeline.py` blocks the renderer import → clips still build 4/4.
  - **Live state (2026-11-21):** pool empty; `torch`/`diffusers`/`spandrel` NOT installed in this pod;
    PC1 not drivable from the pod (tailnet NXDOMAIN, no `PC1_MCP_TOKEN`); `ART_LIBRARY_URL` unset.
    → to build clips now: install the renderer deps here, bring PC1 up, or supply `ART_LIBRARY_URL`.
    Stories ready: `content/motion/01-04.json` (dharma×2, genx, knowledge).
- The living index: `.openhands/memory/MEMORY.md` (<6,000 chars) → `topics/` → daily logs.
- **What already exists:** `docs/INVENTORY-2026-11-22.md` (repo/workflows/releases/issues,
  OpenHands conversations, and the capability map that names the owner of every job). Read it
  before creating anything — K, 2026-11-22: "เราเคยทำทุกอย่างมาหมดแล้ว".
- **How work runs now:** `docs/SYSTEM-STRUCTURE-2026-11-22.md` (L0 CEO → L1 council3 → L2 build
  → L3 gate → L4 publish → L5 counter; the six rules; the loop stages and their preconditions).
- **ak's own identity:** `docs/AK-IDENTITY.md` + `scripts/ak_mail.py` (ak's mailbox, KV vault).
- **ak's team of workers:** `scripts/team.py` (`list|run|all`); roles = researcher, scriptwriter,
  packager, critic, analyst (fast) + engineer (Cloud). Advisors registry: `scripts/advise.py`
  (camps: gemini, pollinations, kilocode, g4fspace, yqcloud — the last three via g4f, keyless);
  3-layer council `scripts/council3.py`.
- **Quality = measured gates only** (K, 2026-11-21: Gemini ออกจากระบบตรวจแล้ว). No review
  ledger, no panel verdict, no auto-fix. A gate that can FAIL + a live measurement is the
  whole bar. **ak publishes on its own** (K, 2026-11-21: "ยกเลิกกฏรอ K อนุมัติอัพออกเลย
  อัพได้ตลอดเวลาเลย แล้วแต่ ak บริหาร") — guard `scripts/test_upload_autonomy.py`.
  `scripts/advise.py`/`team.py` = optional drafting help, never an approval step.
- **Long clip → Short with a link (K, 2026-11-21):** `scripts/shorts_from_long.py` cuts a
  45-46 s vertical from a finished long clip (16:9 floats on its own blurred copy; Thai text
  burned through **libass** — this ffmpeg has no `drawtext`), gates it with `short_standard`,
  then `--upload` posts it public with the **long URL in the description** (a Short has no
  clickable link) and records it in `content/<ch>_shorts.json` + `upload_log.json`.
- **Content research → story spec (K, 2026-11-21):** `scripts/research_niche.py` measures the
  niche live (`search.list` + `videos.list`, 100 quota units per query) and our own uploads
  (`Analytics` avg view %), writing `docs/RESEARCH-<date>-niche.md`. Its numbers set the story
  rules: winners' **median length 85.7 min**, title = problem + promised time + outcome.
  A story ships as `content/standard/<ch>_story_NN.json` with `"kind": "story"` + `chapters`
  + `loop_note` (the 90-min version is `make_compilation.py --minutes 90`, no re-cut).
  Guard `scripts/test_story_specs.py` (schema, 120-400 lines, ≤80 chars/line, Thai-only
  narration, unique live title) — it feeds a broken copy through itself to prove it can FAIL.
- **Vision quality check (manual, NEVER gates CI):** `scripts/grade_video_vision.py` samples N
  frames across a finished file and asks Gemini for a 0-10 rubric score. It is non-deterministic
  (measured 2026-11-17: the same cut scored 9 then 5/10), so a human/agent reads it — no workflow
  calls it (guard `scripts/test_vision_grader.py` fails if a rail wires it in).
- **No reviewer in the loop (K, 2026-11-21):** *"Gemini ลบไปเลย ไม่ต้องใช้ระบบนี้มาตรวจแล้ว"* —
  the review ledger, its `docs/reviews/` evidence and the Gemini auto-fix are **deleted**.
  A gate that can FAIL + a live measurement is the bar; **ak publishes on its own**.
- **Not a place for truth:** a new file with a `b/c/d` suffix. Extend the dated file instead.

## 4) Conventions (K's rules, measured)

- **PCSEV** every problem: Problem → Cause → Solution → Execute → Verify (verify LIVE).
- Times to K: **Asia/Bangkok, 24h**. Reply in **Thai**. Decisions go to the **3-layer council**
  (`scripts/council3.py`, K 2026-11-22): L1 ทุกค่ายคิดขนาน → L2 ค่ายอื่นวิจารณ์ร่าง →
  L3 ตัดสิน (ห้ามอ้างตัวเลขที่ไม่มีใน FACTS). `advise.py` = ถามเร็วค่ายเดียว (Gemini, K 2026-11-18).
- A guard must be able to FAIL; never hardcode the set a guard sweeps; a generator that can
  drop a piece must FAIL.
- **A rail that cannot do its job must not report success** (measured 2026-11-18: the shared
  Data-API pool was spent every day, `link-shorts` ran the funnel as `... || true` and went
  GREEN while the funnel stayed unwired; `set-thumbnails --check` called an unreadable API
  "auto/other" and showed 12 live covers as unset). A spent quota is a **deferral (exit 2)**,
  an unreadable state is **unknown, not "not ours"**. Guard `scripts/test_no_silent_funnel.py`.
- **Archive, don't delete** (`scripts/legacy/`): keep history, cut noise. Delete only true duplicates.
- **Shorts quality is gated before upload** (`scripts/publish_shorts.py`): aspect/colour/thumbnail
  (`short_standard.py`, `test_short_standard.py`) and loudness (measured, not a fixed gain —
  `test_short_loudness.py`). A build that misses the standard is HELD, not uploaded.
- **The queue knows a clip's length before it is built** (`predicted_seconds` in
  `publish_shorts.py`, fitted on 241 published Shorts: `content/duration_calibration.json`,
  5.49 s + 0.0837 s/char, R²=0.956). Measured 2026-11-27 over 333 Shorts on both live channels,
  controlled for theme: the **>48 s bucket has a median of 8 lifetime views** against 142–201 at
  33–48 s, and the effect holds inside one theme (วิธี: 0.19 vs 7.17 views/day). So dharma and genx
  set `"prefer_short": True` and publish the short end of the pool first — a sort, not a gate, so
  a long clip still goes out when the short ones run out. Guard `test_prefer_short.py` (fails when
  the order is reversed; 11 dharma / 18 genx unpublished clips are predicted over 48 s).
  **Era-controlled (2026-11-28):** inside the last 21 days the gap is 1.9x pooled (14.69 vs 7.63 v/day),
  3.4x on dharma, **thin on genx (1.25x)** — the direction holds, the lifetime 8-vs-142 figure overstates it.
- **The daily cap counts every ledger key that belongs to a channel** (`_ledger_keys`: channel id
  *and* slug). Measured 2026-11-24: `publish_motion.py`/`remake_shorts.py` recorded under the slug,
  so `uploads_in_last_24h()` read 0 with three dharma uploads inside 24 h — another rail could
  push a channel past `DAILY_CAP`. Guard `test_publish_shorts_cap.py` fails if the slug is ignored.
- One project, one goal. A task that does not serve YPP is out of scope — say so, don't build it.

## 5) Archived (kept for history, no live references)

`scripts/legacy/pod_mail_login.py` (superseded by `pod_account_login.py`),
`scripts/legacy/backfill_short_links.py`, `scripts/legacy/gen_branding_art.py`,
`scripts/legacy/probe_advisors.py`, `scripts/legacy/studio_drive.py`.

---
_Last audited: 2026-11-18 (ak, whole-repo pass anchored to the yt938-2 goal)._
