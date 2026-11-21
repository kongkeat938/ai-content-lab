# recovered/VIDEO-SYSTEM-NEW — the new system, recovered from a prior chat (2026-11-21)

**What this is.** K's new video system was built over ~16 h in the previous OpenHands
conversation (`2bf1440…`, 2026-11-20 13:18 → 2026-11-21 05:47). That session **never
committed or pushed** its work, so when the pod was recycled for the next chat the code was
gone from the repo. It was recovered here by replaying the `file_editor` operations from the
conversation's event trajectory.

**Status: RECOVERED DRAFT — not wired, not fully consistent.** Do NOT drop these into
`scripts/` as-is. The replay captured the *new* files but not every edit the session made to
*existing* files (e.g. the kill-switch checks it was adding to `publish_shorts.py`,
`publish_batch.py`, `publish_motion.py`, `remake_shorts.py`, `delegate_ready.py`,
`publish_youtube.py`). So the recovered tests are newer than the recovered modules and several
fail (measured 2026-11-21): `test_kill_switch` (NameError), `test_image_vault` (NameError),
`test_cap_freshness` (`root=` kwarg), `test_render_clip_stability` (`vault` arg),
`test_no_pending_uploads` (uploaders missing kill-switch). `test_clip_standard` passes.

## What K asked (the spec — `docs/VIDEO-SYSTEM-NEW.md`)
1. Image library on PC1 `D:`, **4K only**; if the link drops, build a library elsewhere.
2. Images from **free AI generation**, accumulate many + diverse.
3. A **separate library/queue for finished videos waiting to upload**.
4. Build shape: `image → video` + **AI music** + **AI narration**.
5. Research many vendors' AI-gen apps, adapt; **work 4K, output 720p**.
Plus (2026-11-21): each clip must not reuse a picture (stamp used pictures; per channel);
send finished clips to K first; **auto-upload stays PAUSED — K orders uploads**.

## What is recovered here (scripts/)
- `ai_scene.py` — local SD-Turbo 640 → RealESRGAN ×4 = 2560 (needs torch/diffusers/spandrel).
- `ai_music.py` — MusicGen (needs torch/audiocraft).
- `image_vault.py` — the warehouse: take_free/release, stamp (ban used pictures).
- `clip_standard.py` — the clip gate (loudness/geometry/shots).
- `render_clip.py` — image(s) → Ken-Burns clip + music + TTS.
- `produce.py` — one story JSON → one clip → `assets/queue/index.json`.
- `kill_switch.py`, `channel_token.py`, `ops/find_mv_mp4.ps1` (+ their tests).

## What is still MISSING (the honest gaps)
- **Posting system** that reads `assets/queue/index.json` and uploads (K's "next link").
- **kill_switch wired into every uploader** (the recovered `test_no_pending_uploads` proves
  it is not, yet).
- **4K master** (renderer currently emits 1080p; rule 5 wants 720p output from 4K source).
- **PC1 `D:` mirror** (unreachable from the pod: tailnet NXDOMAIN, no `PC1_MCP_TOKEN`).
- `torch`/`diffusers`/`spandrel` are **not installed** in the pod → the AI scene/music
  builders cannot run here without installing them.

## Docs kept live (not quarantined)
- `docs/VIDEO-SYSTEM-NEW.md` — the spec + measured routes.
- `.openhands/memory/topics/08-production-rail.md` — how `produce.py` works + its refusals.
- `.openhands/memory/topics/06-local-ai-image-music.md` — local AI gen notes.
- `.openhands/memory/2026-11-20.md` — that session's log.

> Next step is K's call: finish integrating this recovered base into `scripts/` (add the
> missing kill-switch wiring + posting system, make every recovered test pass), or K lays the
> system down himself. Auto-upload stays paused until K orders otherwise.
