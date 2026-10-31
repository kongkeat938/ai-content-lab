## PC1 is drivable; the C:->D: migration is done (2026-10-29)
- **`ops/check_pc1.py` was reporting FAIL against a healthy PC1.** Its reachability
  check sent an *unauthenticated* GET and read the resulting 401 as "the key
  differs". This server requires auth on every request, so 401 is what an anonymous
  probe always gets. Send `Authorization: Bearer $PC1_MCP_TOKEN` and a real
  `initialize`; only then does a 401 mean the key is wrong. Tier 3 needs the same:
  streamable-http rejects a bare `tools/list` with 400, so `initialize` first and
  reuse the `mcp-session-id` header on the follow-up. Fixed 2026-10-29.
- Registration is per-conversation state, not a file: `POST
  http://localhost:60000/api/settings/mcp/pc1-winremote` with the agent key from
  `/proc/1/environ` (`SESSION_API_KEY`). A conversation loads its tool list once at
  start, so a server restart mid-session makes the `pc1-winremote_*` tools vanish
  ("Unknown tool") until a new conversation -- drive PC1 over raw MCP instead.
- **Windows locks a running process's cwd, and that blocks `Remove-Item -Recurse`.**
  The winremote MCP server had been started with its cwd inside `C:\ax-work\_ax`,
  so the whole tree could not be deleted. Restart the server from `C:\` first
  (`ops/pc1_finish_move.ps1`). The same trap applies to any "directory in use"
  error on Windows: find the holder's cwd before blaming a file lock.
- T6 complete: `C:\ax-work` copied to `D:\ax-work` (8810 files, byte-for-byte
  verified), C: deleted, `C:\ax-work` left as a **junction** to `D:\ax-work`, and
  the library mirrored to `I:\My Drive\library`. All clip work now lives on D:.
## T6 PC1 storage → D: (2026-10-29) — prepared, not run
K wants all clip work on drive `D:`. **PC1 is unreachable from the sandbox again**
(funnel **502** with token / 401 without → backend down; 8090/3389/22 closed; the
agent server's own `/api/mcp/test` also 502). Only a human at the machine can
restart it: `ops/pc1_fix_remote.ps1 -Token <PC1_MCP_TOKEN> -Persist`.
So the move is a tested deliverable, not a done deal: **`tools/pc1_move_to_d.ps1`**
(manifest → robocopy → verify sha256 → *then* delete C: → mirror to
`I:\My Drive\library`; leaves a `C:\ax-work` junction). `-DryRun` first.
Served for PC1 to fetch (identical sha256 to the repo copy):
`https://work-1-aawbtzbmlbinnzlo.prod-runtime.all-hands.dev/pc1_move_to_d.ps1`.
Defaults now `D:\ax-work` in `pc1_setup`/`pc1_push`/`yt938_sync`/`pull_ch2_to_drive`.
- **You can test PowerShell here.** `~/pwsh/pwsh` (install: pwsh linux-x64 tar.gz
  → extract; run with `DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1`). `tools/test_pc1_move.ps1`
  loads the script's real functions **by AST** and asserts each failure mode —
  including **same-size sha256 corruption**, which a size-only check passes.
- **`Split-Path -Qualifier` THROWS** on a path with no drive letter (UNC/harness);
  read it in a `try`. **robocopy exit 0-7 = success**, only 8+ is failure.
## Daily logs
- `2026-10-30.md` — **competitor research + strategy + quality gate** (this repo,
  not yt938): the measured market per niche, the ch4-token/channel mismatch, the
  `quality_gate.py` + `measure.py` tools, and what remains (owner decision on ch4).
- `2026-10-27.md` — **the empty-pod audit above**: what was lost, the corrected
  YouTube state (ch2 12-min is public + a leftover private duplicate), the Gemini
  free-tier 429, and the push 403. Also covers the clip-standard defect fixes
  (badge, true peak, caption gaps) from the same day before the loss.
- `2026-10-26.md` — **automation system document** for ch4 + song-video
  (`docs/automation-system.md` + `docs/automation-pipeline.json`, commit 04b7906).
  Read it for the measured per-stage timings and the free-tool limits. Key find:
  edge-tts on a **cold** cache failed **7 of 8 job attempts** before completing all
  22 lines — the retry loop must be at job level, and the job is resumable because
  finished lines stay on disk. Foreground commands are capped at **1080 s**.
- `2026-10-25.md` — **three workstreams**: (a) AKATH multimodal learning in
  `aeris-drive-automation` — built the schema-driven validator + 18 fixtures +
  CI, verified against Ajv, found the push blocker; (b) ch4 — ep2 written,
  `series.py` added, then **round 7**: owner rejected on-screen characters, so
  both episodes were rebuilt as background slideshows (35 variants, 0 adjacent
  repeats) with the caption centred. Read the round-7 section for the trap list
  (`hash()` seeding, the missing `library` key, the amber-text centring artefact);
  (c) **song-video** — a short story cut to the owner's instrumental, web photos
  retouched per mood, audio preserved bit-for-bit; then **round 3** on owner
  feedback (narration clarity, picture fit, slide pacing) — read the
  "song-video round 2" section for the retrieval-measurement trick and the
  `--force` vs `--refetch` trap; then **round 4** made the music bed optional
  (Openverse fallback, fetched-bed re-levelling, attribution, `--no-music`).
- `2026-10-24.md` — Thai TTS quality lab (`tts_lab/`): 5-variant audible demo,
  text-prep recipe, number spelling, two-pass loudnorm. Note: this pod had an
  **empty** `/workspace/project` — the dharma-channel scripts were gone.
- `2026-10-20.md` — cold-start inspection, bootstrap, lunargo.net investigation,
  dharma-channel build (14 clips), GitHub/OAuth audit
- `2026-10-21.md` — YouTube OAuth solved; multi-channel refactor; genx channel
  (ปรัชญาชีวิต) content + 14 videos; first verified upload; **long-form (10-15 min)
  narration rolled out to all 28 episodes, then videos + shorts + previews rebuilt
  from it (rounds 4-6)**
## This sandbox - environment facts (verified)
- agent server: `http://localhost:60000`; auth header `X-Session-API-Key: $SESSION_API_KEY`.
- Secret store: `GET|PUT /api/settings/secrets`, `GET|DELETE /api/settings/secrets/{name}`.
  PUT body `{"name","value","description"}`. Use it to move credentials without chat.
- Preview URLs are **per-pod**: `work-1-<hash>...` -> 12000, `work-2-<hash>` ->
  12001, where `<hash>` changes on every restart. Read the current pair from the
  session's work_hosts block; never reuse a remembered one.
- No browser inside the sandbox: OAuth must use a public-callback server
  (see `dharma-channel/scripts/yt_auth.py`), never `run_local_server()`.
- `numpy` installed, used by the music synth.
- **ffmpeg is NOT preinstalled** and the sandbox is ephemeral: after a restart
  `ffmpeg`/`ffprobe` are missing. `sudo apt-get install -y ffmpeg` works
  (`openhands` is in the `sudo` group) but plain `apt-get` fails on the dpkg lock.
- **`ss`/`netstat`/`lsof` are NOT installed** — a `(ss ... || netstat ...) | grep`
  port check returns empty and looks like "port free" even when it is BUSY.
  Use a Python `socket.connect_ex` probe instead. This cost a real bug: a second
  `http.server` on 12000 failed silently and the old dharma page kept being served.
- **Nothing auto-starts in this sandbox.** PID 1 is `openhands-agent` (not init);
  `systemd` is `offline` and `cron` is NOT running, so there is no daemon to install
  that would bring a server back after a pod restart. Background processes die and
  every preview link 502s until something starts the server again. Fix that works:
  run `bash .agents/skills/ch4-video-production/scripts/ensure_review_server.sh`
  (idempotent, socket-probes the port, then verifies via real HTTP 200) as the FIRST
  action of a session. `AGENTS.md` at the repo root now says so, because an agent
  only reads a skill if it thinks to invoke it.
- Serve both channels from one port: `site/` holds symlinks `dharma -> ../output`
  and `genx -> ../output-genx`; `python3 -m http.server 12000 --directory site`.
## User preferences
- User is on **Windows (PowerShell)**, not Linux. Do NOT hand them `mkdir -p`,
  `chmod`, or `&&` one-liners -- PowerShell 5 rejects `&&` and has no `chmod`.
  Prefer UI steps, or give native PowerShell (New-Item / Move-Item / `;`).
- Communicates in Thai; wants concise Thai answers.
- Wants evidence and verified results, not claims.
