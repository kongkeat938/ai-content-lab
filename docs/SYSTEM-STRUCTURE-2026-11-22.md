# SYSTEM-STRUCTURE-2026-11-22 — the way work runs from now on (K, 2026-11-22)

K: "ต่อจากนี้ให้ทำงานตามระบบโครงสร้างใหม่ด้วย". This is that structure. It is built from
parts that already exist (see `INVENTORY-2026-11-22.md`); nothing here is a second copy.

## 0) One sentence
ak (CEO) decides → the **3-layer council** checks the thinking → a **worker** makes the
artifact → a **gate that can FAIL** decides ship-or-hold → the **publisher** ships and records
it → a **counter** proves it moved.

## 1) The layers, and who owns each

| layer | owner | job | must hold |
|---|---|---|---|
| **L0 CEO** | ak (this conversation, or a cron conversation) | order the facts, choose the move, execute, verify live | every claim carries a measurement |
| **L1 THINK** | `scripts/council3.py` (5 camps) | L1 drafts in parallel → L2 cross-critique (critic ≠ author) → L3 decide in a fixed shape | quorum, every draft critiqued, no number outside FACTS |
| **L2 BUILD** | `scripts/team.py` workers + the builders (`make_short.py`, `make_compilation.py`, `make_night_video.py`, `longform-standard.yml`) | produce one artifact per decision | a generator that drops a piece FAILS, never writes a partial set |
| **L3 GATE** | `short_standard.py` · `clip_standard.py` · `verify_night.py` · `qa_gate.py` | pass / hold, one owner per format | the gate can FAIL and is never moved to let a build through |
| **L4 PUBLISH** | `publish_shorts.py` · `publish_batch.py` · `publish_motion.py` | upload + thumbnail + record | receipt written before the next step; cap 3/day/channel |
| **L5 MEASURE** | `counter_ledger.py` · `analytics.py` → `watch_hours.json` → `PROGRESS.md` | prove the number moved | counters must not fall and must not sit still |

## 2) The six rules that make it a system
1. **ค้นก่อนสร้าง** — read `INVENTORY-2026-11-22.md` first. If the row exists, extend it; never
   a second copy under a new name.
2. **One owner per gate.** No second opinion may drift (the Gemini panel was removed 2026-11-21).
3. **A gate must be able to FAIL.** When a build fails a gate, change the **build**, never the gate
   (today: `--bed-headroom` fixed a 31.7 dB bed instead of raising the 30 dB ceiling).
4. **Numbers are measured, not remembered.** The council's numbers are checked against FACTS;
   a doc tells you *where* to measure, not *what* the answer is.
5. **Record before the next step.** A loop that cannot persist its manifest must not run
   (otherwise it re-posts the same video — measured failure `night_auto_202647_r23`).
6. **Times to K are Thai `HH:MM`.**

## 3) Cadence
| when (Thai) | job | trigger |
|---|---|---|
| 09:00 daily | measure: `counter_ledger.py`, `analytics.py` → `watch_hours.json` | cron (monitor, active) |
| when K speaks, or once a day | decide → build → gate → publish | ak |
| 20:00-22:00 | publish window for sleep-format clips (dharma) | ak |
| step up, don't jump | a new rail runs 1 day beside the old one before it replaces it | ak |

## 4) What the council may and may not do
- **May:** choose what to build/fix next, rank options, name the risk and the `NOT`.
- **May not:** approve a build, override a gate, or publish. There is no panel verdict to wait for.
  ak executes; the gate decides; the counter proves.

## 5) From turn-based to a real loop
| stage | what runs | precondition |
|---|---|---|
| **1 (now)** | turn-based: ak runs the whole loop when K speaks | none |
| **2** | an OpenHands cron conversation (no automations REST API — create in the UI) that runs §1 every N hours | **push must work**, else the manifest never persists |
| **3** | the repo's own rails: `watchdog → foreman → rails` (29 disabled today) | PAT with `contents:write` + `workflow`; re-enable step by step |

Measured blocker (2026-11-22): `push` returns **403** → stage 2 and 3 are unsafe today.
Enabling them now would re-post videos, which is worse than being manual.

## 6) Escalation and stop rules
- A genuine human-at-a-browser unknown (a phone number ak cannot own) → ask K. **A Google login is
NOT one of these any more:** `scripts/yt_auth_device.py` gives K an 8-character code for
`google.com/device` on the phone (K works from a phone; noVNC is unusable there, 2026-11-22).
- Prefer the reversible move (private / draft / hold) over the irreversible (delete).
- A rail that fails twice → stop it, write PCSEV with the measured cause, fix, then re-enable.
- `content/STOP` still halts everything; it does not exist today (measured).
