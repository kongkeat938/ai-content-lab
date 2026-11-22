# INVENTORY — what already exists (measured 2026-11-22 09:50 Thai)

K: "ไปไล่ดูใน github openhand ให้หมด เราเคยทำทุกอย่างมาหมดแล้ว" — this is the measured
answer. Read this **before** building anything: if a row exists, extend it, do not copy it.

## 1) The repo
| | |
|---|---|
| name / visibility | `kongkeat938/ai-content-lab` — **public** (private halts the rails) |
| default branch | `main` · last push 2026-11-21 22:51 Thai |
| size | 151 MB (API) / 3.7 GB on this pod (`.git` 115 MB) |
| branches | 6 — `main` + 5 stale feature branches (`feat/night-compilation-rail`, `feat/ch4-kinetic-knowledge-video`, `af/channel-report-analytics-unlocked`, `docs/ch4-demo-preview`, `research/competitor-strategy`) |
| releases | **32**, one asset set each, 132-443 MB per release (night packs carry 3 assets) |
| PRs | 3 total — 2 merged (#38 ch4 b-roll, #39 pages preview), **0 open** |
| issues | 49 total, **6 open** (below) |

Open issues (backlog that already exists — do not re-file):
- #49 rail health: an automation has gone quiet (2026-11-21 13:26 Thai)
- #48 Night compilation — review before publishing (2026-11-20 10:04)
- #46 / #45 night-compilation run failed (2026-11-20 04:06 / 02:14)
- #43 ch4-longform run failed (2026-11-19 19:11)
- #6 ความคืบหน้าถึงเป้า $500/เดือน (2026-11-07)

## 2) Workflows — 38 files, 39 registered: **10 active / 29 disabled_manually**
28 carry a cron. The 29 disabled are the **production** rails; the 10 active are monitors.

| group | examples | state |
|---|---|---|
| monitors (cron) | `rogue-guard` (every ~6 h), `progress`, `counter-ledger`, `selftest`, `cred-transport`, `fetch music`, `longform-standard` | **active** |
| production (cron, disabled) | `foreman`, `watchdog`, `publish-shorts`, `publish-batch`, `publish-ch1`, `publish-ch4`, `genx-longform`, `ch4-longform`, `night-compilation`, `link-shorts`, `set-thumbnails`, `remake-shorts`, `studio-ai`, `ch2-playlists`, `grow-shorts-pool`, `short-doors`, `polish-all`, … | **disabled_manually** |

7-day run table (measured): pages build 49 (13 failed), rogue-guard 10 (0), remake shorts 5,
publish-shorts 4, counter-ledger / foreman / progress / selftest 3 each, watchdog 3
(**all cancelled**, not failed — a newer run or a manual cancel superseded them),
longform-standard 2, account-watch 2, ch2-playlists 2 (1 failed), everything else ≤1.
**Trigger mix:** every production run in 24 h was `workflow_dispatch`; only monitors were
`schedule`. So production has been manual since the rails were disabled.

## 3) OpenHands Cloud — 127 conversations on this project
- 100 most recent: **73 `openhands_api`, 27 `gui`**, dates 2026-10-29 → 2026-11-22.
- models: `deepseek-v4.1-flash` 59, `claude-sonnet-4-5` 20, `gpt-5` 18, `o3` 1, `gemini-3-pro` 1, `claude-opus-4-5` 1.
- Titles are mostly continuation prompts ("อัพเดท", "ทำงานต่อจากเซสชั่นล่าสุด", "ak advisor panel",
  "ak rogue-*") — i.e. the work has been **turn-driven**, not cron-driven. No automations API is
  exposed (`/api/v1/automations*` returns the SPA), so any cron loop must be built explicitly.

## 4) Content that is already built and live
| channel | shorts published | long-form published | notes |
|---|---|---|---|
| genx (ch1) | 103 | 7 / 7 | 53 unused short scripts left |
| dharma (ch2) | 126 | 15 / 15 | 65 unused; +90-min night comp live today (`Is-VYMhhPvc`) |
| kongkeat (ch4) | 74 | 4 / 4 | 92 unused |

Assets: 55 music beds, art ledgers per channel (`content/art_ledger_*.json`), bed ledgers,
`assets/art/{ch1,ch2,ch4}` stills, `assets/branding/farmmer/thumbs/*` (long-form thumbs).

## 5) Capability map — the owner of each job (do NOT write a second copy)
| need | owner |
|---|---|
| Short build (TTS → captions → 1080x1920 + 9:16 thumb → self-gate) | `make_short.py` |
| Short gate / long-form gate / night gate | `short_standard.py` · `clip_standard.py` · `verify_night.py` |
| critic gate on a build receipt | `qa_gate.py` |
| long-form render (CI only, never uploads) | `longform-standard.yml` |
| night/sleep compilation audio | `make_compilation.py` (+ `--minutes`, `--bed-headroom`) |
| night video (60 s loop + `-stream_loop` copy) | `make_night_video.py` |
| poster / thumbnail art | `make_poster.py`, `make_short_thumbnail.py`, `gen_cover_image` |
| publish: shorts / long / motion | `publish_shorts.py` · `publish_batch.py` · `publish_motion.py` |
| publish state, cap, receipts | `publish_state.py` (`DAILY_CAP=3`), `content/*_{shorts,publish}.json` |
| rail orchestration | `foreman.py` (watchdog → foreman → rails) |
| health / counters | `counter_ledger.py`, `analytics.py`, `verify_claims.py`, `durability_guard.py` |
| thinking: 1 camp / 3 layers | `advise.py` · `council3.py` |
| workers | `team.py` (researcher, scriptwriter, packager, critic, analyst, engineer) |
| identity / mailbox | `docs/AK-IDENTITY.md`, `ak_mail.py` |
| PC1 hands | `winremote`, `pc1-task.yml` |
| story specs / research | `research_niche.py`, `content/standard/*.json` |

## 6) Gaps that are real (measured today)
1. **push 403** → 6 local commits + the 374 MB night asset cannot leave the pod.
2. 29 production rails disabled → no production loop (see `SYSTEM-STRUCTURE-2026-11-22.md` §5).
3. Pages builds fail 13/49 — a docs/report writer is racing itself.
4. 4 open issues are unowned failure reports (#43, #45, #46, #49).

## 7) Advisors — measured live 2026-11-22 10:05 Thai
| system | what it is | measured today |
|---|---|---|
| `scripts/council3.py` | 3-layer council, `DEFAULT_VENDORS` = 5 camps, L3 judge = gemini | **OK 132.5 s** — L1 2/5 answered, L2 2/2 critiqued, L3 decision 9/10 |
| `scripts/advise.py` | flat panel, 10 advisors (`--broad`, `--deep`) | **OK** — `--only gemini` answered 1/1 |
| `scripts/team.py` | workers (researcher/scriptwriter/packager/critic/analyst/engineer) | available |

Camp status (measured, not assumed):
- **answer:** `gemini` (GEMINI_API_KEY, model ids `gemini-3.5-flash-lite` / `gemini-3.1-flash-lite` both return 200) · `pollinations`
- **on demand:** `openhands`, `openhands-claude`, `openhands-gpt` (OPENHANDS_API_KEY)
- **dead in this pod:** `kilocode`, `g4fspace`, `yqcloud` — no route env here; a run with the default
  five camps can fail quorum (first attempt: 1/2 answered). A retry passed, so treat a failed
  quorum as **transient**, retry once, then run `--vendors gemini,pollinations`.
