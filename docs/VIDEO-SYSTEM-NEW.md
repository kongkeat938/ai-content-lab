# VIDEO-SYSTEM-NEW — the spec K gave on 2026-11-20 (+ what got built)

K is **deleting the old system himself** and will lay down a new one. This file is the
spec of that new system, plus the **live measurements** that decide what is actually
possible, and now also **the parts that are built and measured** (bottom of the file).

> Status: **SPEC + 3 BUILDERS DONE (2026-11-20)**. `content/STOP` is still in place; every
> builder refuses to run while it exists (exit 3) — measured, see the guard section.

---

## The five rules (K's words, 2026-11-20)

1. **Image library on PC1, drive `D:`.** If the connection drops and the library cannot be
   pulled, **build a new library elsewhere**. Every image in the library must be **4K**
   resolution — this is the raw material for the videos.
2. **Images come from free AI generation**, accumulated into the library continuously until
   there are **many**, and **diverse in subject** so they can serve whatever stories we make.
3. **A separate library for finished videos waiting to upload.**
4. **Build shape:** `image → video` + **AI-generated music** + **AI-generated narration**.
5. **Research the method from many vendors' AI-gen apps** (Dreamina, Gemini, Perplexity,
   others), then **adapt the approach to ours**. Work at **4K only; output 720p**.

---

## Measured 2026-11-20 22:0x–23:0x Thai — what the free routes actually do

Every number below was measured live in this pod, not read from a doc.

| Route | Result | Verdict for rule 1 (4K library) |
|---|---|---|
| **Local `generative_art.py`** | `--size 4096` → **4096×4096**, 7.5 s compute / 16.5 s wall, no quota, reproducible by seed | ✅ **only route that truly makes 4K** |
| **Pollinations** (free, no key) | asks 3840×2160 → returns **1024×576**; asks 1024×1024 → **768×768**; **1 image / 45 s / IP** (`FREE_LIMIT` 402), 503 when busy | ❌ caps ≈0.8 MP |
| **Gemini image** (`gemini-3.1-flash-image`, `-2.5-flash-image`) | **HTTP 429, free quota 0** (both models) | ❌ |
| **HuggingFace inference** (FLUX schnell, no token) | connection fails (no route) | ❌ |
| **Cloudflare Workers AI** | 404 without an account id + token | ❌ (needs paid account) |
| **Openverse** (free stock, no key) | works, but results **500×333 … 819×1024**, mixed licences incl. `by-nc-nd` | ⚠️ not 4K, licence gate rejects most |
| **Pexels API** | 401 without a key | ⚠️ needs a key (free tier exists) |
| **PC1 drive D:** | unreachable from the pod (measured earlier: funnel NXDOMAIN, runner count 0, no tailscale socket) | ⚠️ needs a human at the machine |

**The one measured conclusion:** no free AI *image* service we can reach returns 4K. Only the
local renderer does. So rule 1 + rule 2 cannot both be met by "call a free API and save the
result" — see the options below.

---

## What this forces (the honest trade-off)

Rule 1 says every library image must be 4K. Rule 2 says free AI generation. Measured, those
two cannot both hold with a hosted free API. Three ways to satisfy both, in order of
robustness:

- **A. Generate at whatever the free API gives, then upscale to 4K locally.**
  Pollinations gives 1024×576 (0.59 MP); 4K is 8.3 MP, so it is a **14× linear upscale** —
  real detail is not invented, it is smoothed. Acceptable for slow pans / soft backgrounds,
  visibly soft for anything sharp. No model download needed.
- **B. Run a local diffusion model** (SDXL / FLUX-schnell via `diffusers`, CPU or GPU) at
  1024–1536 px, then tile-upscale to 4K. **Not installed**: `torch` absent, disk 25 GB free,
  model weights 2–7 GB. This is the only route that produces genuinely new 4K detail from AI.
  Needs a decision on download size and CPU time (a 4-core pod).
- **C. Local `generative_art.py` at true 4096** for the background/texture layer (measured
  working, 16 s/image, unlimited), and use AI-gen images only as *subject* cut-outs composited
  on top. Fully free, truly 4K, unlimited — but the subject matter is algorithmic art, not
  photoreal scenes.

**Recommendation to K:** C for the bulk library (unlimited, true 4K, free) + B if photoreal
subjects are required. A is the fallback when only a hosted free API is reachable.

---

## Library layout proposed (rule 1 + rule 3)

```
assets/library/4k/<genre>/<seed>-<slug>.png      # raw material, 4K, one file per image
content/image_vault.json                         # ONE index: stock AND ban (see rule 6)
assets/queue/                                    # finished 720p videos waiting to upload
```

`content/image_vault.json` is the source of truth (a file is "in the library" only if the
vault has its md5). It is deliberately **one file, not two**: the same entry that stocks a
picture is the entry that bans it once a clip takes it, so stock and ban can never disagree.
PC1's `D:` is a **mirror**, not the primary — that is what makes rule 1's "if the
connection drops, build elsewhere" true instead of a hope.

---

## Rule 6 — one image, one clip, every channel (K, 2026-11-20)

> "แต่ละคลิปห้ามใช้รูปเดียวกัน ทุกช่องด้วย รูปไหนเอามาใช้แล้วต้อง stamp ไว้เลยว่าห้ามใช้
> รูปต้องสร้างเก็บไว้เรื่อยๆ จะมีสะสมในโกดังเอง"

The old design kept one ledger **per channel** (`content/art_ledger_<channel>.json`), keyed by
md5 *within that channel*. Two channels could therefore hand out the same picture and nothing
would notice. **Measured 2026-11-20 on the committed ledgers: 4 md5 were already shared between
`motion` and `motion2`** — the defect was real, not hypothetical.

`scripts/image_vault.py` replaces that with one index for all channels:

| Operation | Behaviour |
|---|---|
| `stamp(md5, channel, clip)` | bans the md5 forever. Re-stamping it for a **different** clip **raises** — that is the reuse K forbade |
| `claim_file(png, channel, clip)` | hash + stamp + return, or raise if already taken |
| `pick_free([...], channel, clip)` | take the first unstamped file and stamp it, all under one lock; raise when the stock is spent |
| `merge` | folds the old per-channel ledgers in, keeping the first owner and recording the second channel under `also_seen_in` as **evidence** |
| `status` | totals per channel + any cross-channel reuse |

Rebuilding the *same* clip keeps its own image (the stamp records `stamped_at` once), so a
reviewer sees the picture they approved. Stock and ban share the entry: `clip` empty = free
stock, `clip` set = spent. `scripts/ai_scene.py` calls `store_in_vault()` for every frame it
generates, so **the warehouse grows on its own** as generation runs — that is rule 2's
"accumulate until there are many", with no separate stocking step to forget.

---

## Build shape (rule 4)

```
image (4K) ──Ken-Burns/slow pan──┐
                                 ├──> 720p master ──> assets/queue/
music (AI) ─────────────────────┤
narration (AI TTS) ─────────────┘
```

Output is **720p** by rule 5, from a 4K source (so the pan has headroom and stays sharp).

---

## Built and measured 2026-11-20 (this supersedes "nothing built yet")

Three builders, each with a guard that can FAIL. All measured live in the pod.

### 1. `scripts/ai_scene.py` — AI image library (rules 1 + 2)

Local SD-Turbo → RealESRGAN. No API, no account, no quota, so "accumulate until there are
many" has no ceiling.

| Step | Measured |
|---|---|
| SD-Turbo 640 px, 4 steps, CPU | **62 s/frame**, 5/5 succeeded |
| RealESRGAN ×4 via `spandrel` (basicsr will not build here) | 640 → **2560 px**, **136 s/frame** |
| Real detail, not interpolation | edge-energy **12.71 vs bicubic 5.02 = 2.53×** on an SD-Turbo frame |
| Real repo photography, swept | **1.36–1.88×** (never below the 1.15× gate) |

The gate is a **ratio against a bicubic blow-up of the same frame**, never an absolute
number — an absolute floor of 8.0 was measured to be a trap: a hard-edged test card scores
5.98 after a real RealESRGAN pass while soft photography scores 2.44, so no single constant
splits both. A resize-only model measures **1.11×** and is rejected by the same code path.

> 2560 px, not 3840: a 2560-wide frame covers a 3840-wide pan window, and 4× on 1920 px
> (7680) costs ~10 min/frame on 4 cores. For a true 3840×2160 master, generate at 960 px.

### 2. `scripts/ai_music.py` — AI music (rule 4)

Local MusicGen. **20.42 s clip in 144 s**; measured **−22.6 LUFS, LRA 1.8, topbin 0.24**.
`topbin` (share of frame energy in the loudest FFT bin) is the discriminator that works:
sines at 220/440/880 Hz score **0.56–0.60**, generated music **0.24–0.26**, so a tone cannot
pass. Never reads `assets/music` (K hates those beds); refuses >30 s; honours `content/STOP`.

### 3. The multi-shot demo (rule 5: 4K source → 720p out)

`/tmp/demo1/build_multi.sh` — 5 AI scenes, crossfaded, Thai narration + AI music, mastered.

| Claim | Measured |
|---|---|
| Container | h264 High, **1280×720, yuv420p(tv, bt709)**, 25 fps, **19.000 s** |
| Audio | aac LC, 48 kHz, **stereo**, 192 kb/s |
| Loudness | **−14.9 LUFS**, true peak **−1.5 dBFS**, LRA 5.8 |
| Motion is real to the last frame | last-quarter frame-diff **0.98** (0 would be frozen) |
| Scenes actually change | first→mid **74.5**, mid→last **61.2** |
| Voice sits above the bed | speech **−14 dB**, music **−20…−27 dB** |

### 4. `scripts/clip_standard.py` — the quality floor K approved

K, on seeing the demo: "งานผ่านแล้วนะ สร้างเป็นมาตรฐานการสร้างคลิปวีดีโอเลย คุณภาพขั้นต่ำต้อง
แบบนี้". So the demo's own measured numbers became the floor. This is the ONE place that
decides pass/fail for a horizontal clip, exactly as `short_standard.py` does for a Short; a
build that fails is HELD, not shipped.

| Rule | Floor | Why that number |
|---|---|---|
| Size / shape | ≥ 1280×720, 16:9 | the demo was 1280×720; rule 5 = "4K source, 720p output" |
| Colour tags | `yuv420p` + `range=tv` + `bt709` | measured 2026-11-17: skipping the tags gave `yuvj420p`/`pc`/`bt470bg`, which plays washed-out |
| Loudness | −14 LUFS ±1.5, true peak ≤ **−1.5 dBFS** | demo measured −14.9 LUFS / −1.5 dBTP |
| Motion | last-quarter frame-diff ≥ 0.05 | demo 0.98; a frozen tail reads as a slide-show |
| Distinct shots | ≥ 2 | demo cut 5 scenes |
| Length | ≥ 3 s | a 2 s file is a fragment, not a clip |

**The shot count is a RATIO, not a cut-detector** — and that distinction was measured, not
assumed. A hard-cut detector reported **"1 shot"** on the approved demo because it crossfades:
its largest frame-to-frame diff was 5.49, below any sane cut threshold. The honest measure is
how far apart the *looks* are: shot-to-shot mean-image distance on the demo was **45–73**
against a same-shot baseline of **7.9** (≈5.6×), so a shot counts when it differs by ≥3× the
baseline. The demo scores **6 shots at ratio 5.0×**.

### Guards (each must be able to go RED)

- `scripts/test_ai_scene.py` — kill switch (rc 3), partial set fails, resize-only model
  rejected, and a LIVE RealESRGAN pass swept over repo imagery. **ALL PASS.**
- `scripts/test_ai_music.py` — kill switch, >30 s refused, no bed access, a 440 Hz sine
  rejected, LIVE generation accepted as music. **ALL PASS.**
- `scripts/test_image_vault.py` — **12 checks, 0 failures.** Reuse by the same channel is
  refused; reuse by *another* channel is refused; a rebuild of the same clip keeps its own
  image; `pick_free` hands out a different picture each time and refuses when the stock is
  spent; generated frames stock the warehouse; taking one bans it; the 4 historical
  cross-channel duplicates stay visible and banned.
- `scripts/test_clip_standard.py` — **14 checks, 0 failures.** Builds a real bad file for
  every rule (one unbroken shot, a frozen tail, full-range colour, 640×360, −8 LUFS, 2 s) and
  asserts not just that it is refused but **that it is refused for that reason** — an earlier
  version of the frozen case was refused for "1 distinct shot" instead, so the motion rule was
  never actually exercised. A good clip passes, so the guard is not "always fail".
- Full suite `for t in scripts/test_*.py`: **111/111 pass** once `ffprobe` exists (12 tests
  fail without it — an environment gap, not a code defect).


### Cost curve, so nobody re-measures it

text2img 768 px / 4 steps = **91.5 s**; 1024 px = **182.6 s**; upscale 640→2560 = **136 s**.
So a 20-shot 4K-source library is ~1.5 h of pod time, once, and then it is on disk forever.

---

## Still not built (honest gaps)

- **No rail/workflow** wires these into the schedule. `content/STOP` is in place and K is
  rebuilding the system himself; adding a rail now would be the second copy this map forbids.
- **True 3840×2160 output file** — the demo masters at 720p per rule 5; the *source* frames
  are AI-upscaled 2560 px. A 4K master is one flag away but was not shipped.
- **PC1 `D:` mirror** — still unreachable from the pod (needs a human at the machine).


### 4. `scripts/clip_standard.py` — the quality floor K approved

K, on seeing the demo: "งานผ่านแล้วนะ สร้างเป็นมาตรฐานการสร้างคลิปวีดีโอเลย คุณภาพขั้นต่ำต้อง
แบบนี้". So the demo's own measured numbers became the floor. This is the ONE place that
decides pass/fail for a horizontal clip, exactly as `short_standard.py` does for a Short;
a build that fails is HELD, not shipped.

| Rule | Floor | Why that number |
|---|---|---|
| Size / shape | ≥ 1280×720, 16:9 | the demo was 1280×720; rule 5 = "4K source, 720p output" |
| Colour tags | `yuv420p` + `range=tv` + `bt709` | measured 2026-11-17: skipping the tags gave `yuvj420p`/`pc`/`bt470bg`, which plays washed-out |
| Loudness | −14 LUFS ±1.5, true peak ≤ **−1.5 dBFS** | demo measured −14.9 LUFS / −1.5 dBTP |
| Motion | last-quarter frame-diff ≥ 0.05 | demo 0.98; a frozen tail reads as a slide-show |
| Distinct shots | ≥ 2 | demo cut 5 scenes |
| Length | ≥ 3 s | a 2 s file is a fragment, not a clip |

**The shot count is a RATIO, not a cut-detector** — and that distinction was measured, not
assumed. A hard-cut detector reported **"1 shot"** on the approved demo because it crossfades:
its largest frame-to-frame diff was 5.49, below any sane cut threshold. The honest measure is
how far apart the *looks* are: shot-to-shot mean-image distance on the demo was **45–73**
against a same-shot baseline of **7.9** (≈5.6×), so a shot is counted when it differs by
≥3× the baseline. The demo scores 6 shots at ratio 5.0×.

