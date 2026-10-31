## A local record of a remote fact goes stale — verify before skipping (2026-10-29)
- **`ops/yt_publish.py` skipped any episode in `_audit/uploaded.json`.** That file
  is a *local claim*, not proof. A video deleted on YouTube leaves the record
  saying `"public"` forever, so `yt_deliver` skipped the episode on every tick and
  could never repair it. Found live: **ch4_ep01 `MBkSa_wG7sk` (ch4's only
  long-form clip) is deleted (404)**; 11 of 12 published videos are live. The skip
  is now gated on `recorded_id_is_live()`: `True` skip, `False` re-upload, `None`
  (no token / API error) keep the old skip so a transient failure cannot duplicate.
  Guarded by `ops/test_publish_record.py`.
- General rule: before skipping work because "the record says it is done",
  re-check the remote. Treat "cannot tell" as "keep the old behaviour", never as
  "do the work again". `ops/yt_audit.py` was already correct — the gap was that
  nothing compared its output to the record.
## Image sources: all three can be down at once (2026-10-29)
A *fresh* channel needs live renders; a *rebuilt* one does not — **Pollinations
serves previously-rendered prompts from its CDN cache (~0.4 s each)**, which is why
ch4's 132-still rebuild finished in 60 s. ch3_ep01 had no cached images (not in
git, not on PC1) so it stalled at image 0 while every source was unavailable:
**FLUX ZeroGPU** ("81 s left, try again in 7:11:17"), **Pollinations**
(`FREE_LIMIT` 402 + global 503 "Classic API is at its limit"), **Gemini API**
(`RESOURCE_EXHAUSTED`). Do not assume a rebuild proves the image path works.
## ⚠️ The pod can come back EMPTY — how to recover (2026-10-29)
Happened twice. `/workspace/project` holds only `.git` (0 commits, **no remote**)
and a stale `MEMORY.md`. The code is NOT gone: the previous conversation's
**sandbox** still holds it. Two sources, both needed:
1. `/tmp/archive.patch` (`git apply --binary`) = the tracked tree, one day stale
   (move `.openhands/memory/MEMORY.md` aside first or apply aborts).
2. The dead session's event archive (`event_*.json`) = the *missing day*. Replay
   its file ops **in event order**: `file_editor` create/str_replace/insert,
   shell heredocs (resolve relative paths against `cd /workspace/project`), and
   re-execute the recorded `python3 - <<'PY'` writers (skip any mentioning
   `git push|urllib|subprocess|rmtree`). `>` truncates, `>>` appends — get this
   wrong and logs come out truncated. Replays are **not idempotent**: reset to
   the archive state and run once.
Then **graft, don't re-root**: `_export/yt938-code.bundle` carries the real
**51-commit** history (tip ee6557e). `git fetch <bundle>
refs/heads/master:refs/heads/from-bundle && git reset --soft from-bundle`, commit.
**Durable push target is `kongkeat938/ax-workspace` (private)** with
`KONGKEAT_GH_TOKEN`; `main` (3109aaf) stays untouched. GitHub rejects >100 MB
files — `ch4-anime/output/*/*.mp4`, `yt938/library/*/ready/*.mp4` and
`song-video/build/*.mp4` are gitignored for that reason.
`kongkeat938/ai-content-lab` is a *different* project (story-video). Full detail
in `2026-10-29.md`.
## Key learnings
- The sandbox is ephemeral: on cold start the workspace was empty and no prior state existed anywhere. Persist important state to git (and eventually a remote) to survive restarts.
- Do not assume an integration is connected — probe it (curl / real call) and record the result.
- **`GITHUB_TOKEN` in this sandbox is a GitHub App token with READ-ONLY repo access**
  (`permissions: {admin:false, maintain:false, push:false, triage:false, pull:true}`).
  It cannot create repos (403) and cannot push (403). GitHub account `kongkeat938` (the
  token identity) has 0 repos. **Re-confirmed 2026-10-25 against
  `aerismusic8-alt/aeris-drive-automation`: `git push --dry-run` → 403 "Permission to
  ... denied to kongkeat938".** So clone-and-commit works, push never does. Do not plan
  GitHub push/create work without the user granting access first; commit locally and
  report the blocker instead.
- **YouTube upload pipeline is PARKED** (see above). The OAuth setup, the
  wrong-account hazard and the ~19-videos/day per-account upload cap are documented
  in `PARKED-channels.md` — read that before doing any YouTube work.
- Available MCP tools are only PR-creation (GitHub/GitLab/Bitbucket/Azure) + Tavily search.
  There is no Google/YouTube MCP server.
## Python tooling gotchas (reusable)
- `pip install faster-whisper` upgrades `click` to 8.5, which **breaks gtts**
  (`gtts` requires `click<8.2`). Re-pin `pip install "click<8.2"` afterwards.
- faster-whisper's `decode_audio` passes `metadata_errors=` that the installed
  PyAV rejects (`TypeError: open() got an unexpected keyword argument`). Bypass by
  decoding to f32le PCM with ffmpeg and passing the numpy array to
  `model.transcribe()`. Whisper models are a large download — run in background.
- **Do not force `language="en"` to decide whether audio has lyrics.** On Thai
  narration Whisper *translates* and emits fluent English, which looks exactly
  like detected lyrics. Detect the language first, or transcribe a music-only
  signal.
- **To check whether background music has vocals, test the music file or the
  ambient bed — never the mixed video.** Separating the `vocals` stem from a
  finished video with demucs also captures the narration, so it cannot
  distinguish a clean bed from a dirty one.
- Ephemeral sandbox: `pip install -r requirements-tools.txt` after every restart
  (edge-tts, faster-whisper, demucs + torch). `requirements.txt` alone is not
  enough.
## Recovering "lost" work (2026-10-27) — the sandbox is the backup
A new pod can come back empty while the work still exists: it lives in the
**previous conversation's sandbox**, which is `PAUSED`, not deleted.
- **Fastest, exact:** `POST /api/v1/sandboxes/{sandbox_id}/resume`, then poll
  `GET /api/v1/app-conversations?ids={conv_id}` until `sandbox_status: RUNNING`
  -> returns `conversation_url` + `session_api_key`. Read files with
  `GET {base}/api/file/download?path=<absolute>` (query param, not a path
  segment); `GET /api/file/archive?path=<dir>` returns a git-format patch of the
  whole tree. Works from a *different* conversation's key -- the sandbox is
  per-account. Do this FIRST, while the sandbox still exists.
- **Fallback:** `GET /api/v1/app-conversations/{id}/download` -> zip of
  `event_*.json`; replay `file_editor` ops in order, then terminal heredocs.
  Rebuilt 85 files with 0 syntax errors. Good enough to read, not authoritative.
- **The real defect: nothing was ever pushed.** `git remote -v` is empty; 50
  local commits. `permissions.push: true` from the API is **not** evidence of
  push ability -- only the push is (it was 403). Push somewhere real.
## Signed-in Google session (2026-10-28) — skill: google-session-browser
Gemini/Flow **API key is quota-dead** (429 everywhere). Use the
**`.agents/skills/google-session-browser`** skill: `bash .agents/skills/
google-session-browser/scripts/session.sh start` (reinstalls display stack +
playwright after a restart; reuses the persisted signed-in profile). Owner:
kongkeat.938@gmail.com — NEVER type their password; they sign in via the noVNC
link. Detail in `2026-10-28.md`.
## Two modules named `imgutil` — the art was never FLUX (2026-10-28)
`build.py` did `import imgutil`, but **`compose.py` inserts its own directory at
the front of `sys.path`**, so the name resolved to `ch4-anime/scripts/imgutil.py`
(the **Pollinations `sana` client, ~0.59 MP, upscaled**) instead of
`yt938/imgutil.py` (FLUX.1-merged). Silent -- no error, no log. Every still in
ch1/ch2/ch4 was 578x1020 or 627x940; **no 1088x1920 file existed**. Fixed by
loading the client by path (commit **24e7166**); guarded by
`ops/test_img_backend.py`, which reproduces the trap and asserts the FLUX client
loads. General rule: **never rely on `import <name>` when two dirs on sys.path
ship that basename -- load by path.**
Blockers for the rebuild (free tools only): **ZeroGPU quota is per-IP and shared**
-- all 4 FLUX spaces say "Try again in 20:xx:xx" (~20 h), and an `HF_TOKEN` is
what would raise it (none is set); **`GEMINI_API_KEY` is free-tier, 429 on
input tokens per minute**, and its images are the same 572x1024 = 0.59 MP the
owner rejected. The signed-in Gemini web UI is stuck on Flash-Lite (text-only);
the other models are `aria-disabled`. Detail in `2026-10-28.md`.
