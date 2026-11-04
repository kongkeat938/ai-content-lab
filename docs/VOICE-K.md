# Using K's own voice (optional)

The channels default to the house edge-tts voice (`th-TH-NiwatNeural`). This
adds a second option: K's real voice, cloned, so a channel can sound like a
person. Nothing here is required for the rail to run -- if the two variables are
unset, everything falls back to edge-tts.

## Why a cloud service and not a local model

Measured 2026-11-03:

| option | Thai? | free? | hardware |
|---|---|---|---|
| XTTS v2, GPT-SoVITS, F5-TTS | **no Thai** | yes | CPU 30-50x slower than real time |
| ThonburianTTS / JaiTTS / Qwen3-TTS | Thai | no easy free clone | needs GPU |
| **Fish Audio `s2.1-pro-free`** | **Thai (83 langs)** | **yes, fair use** | none, it is an API |

Both the pod and PC1 have no GPU (4 CPU cores each), so a local clone is not
usable: a 120-minute night video would take 60-100 hours. Fish Audio clones from
a short sample and speaks Thai on the free tier.

## Setup (K, once)

1. Record 30-60 seconds of clean speech in a quiet room. A phone voice memo is
   fine. Read something calm and steady -- this becomes the channel's narrator.
2. Go to fish.audio, sign in, open **Voices**, and create a voice from that
   recording (Instant clone).
3. Copy the **API key** (account settings) and the **voice id** (the new voice).
4. Put them where ak can read them. Either:
   - add repository secrets `FISH_API_KEY` and `FISH_REFERENCE_ID`
     (GitHub -> repo -> Settings -> Secrets and variables -> Actions), or
   - hand them to ak to register as environment secrets.

Nothing else changes: the mastering chain still normalises to -14 LUFS / -3 dBTP.

## What it affects once set

- Shorts: `make_short.py` writes the line as `voice.mp3` with K's voice.
- Long night videos: `make_audio.build()` uses K's voice; the exact per-line
  timing path (`build_with_timing`) stays on edge-tts, because Fish Audio does
  not return word boundaries here. The night videos use the estimated timing.
- The build fingerprint includes the voice, so switching voice forces a rebuild
  instead of silently reusing the old edge-tts release.

## Try it without committing

    FISH_API_KEY=... FISH_REFERENCE_ID=... \
      python3 scripts/tts_fish.py --text "สวัสดีครับ ผมชื่อเก่ง" --out /tmp/k.mp3

## Check before trusting it on the long videos

A 2-hour read is the hard case. Build one night video with K's voice and measure
it before switching the channel over; a short sample can drift over a long read.

## Sending the recording to ak (K, pick one)

K has no way to attach audio in the chat, and PC1 has **no microphone**
(measured: the only audio endpoint is "Speakers"). Record on the phone, then:

**Option 1 — upload page (easiest, nothing to install).**
Open this on the phone, pick the file, press send:

    https://work-2-zmmehfjlyrrhipvr.prod-runtime.all-hands.dev/

The file lands in `work/k_voice/inbox/` on the pod. ak starts the page with
`scripts/voice_inbox.py`. The page dies when the pod recycles, so ask ak to
restart it if it does not load.

**Option 2 — Google Drive (works even while the pod is down).**
PC1 already syncs three Drive accounts:

| drive | account |
|---|---|
| G: | kongkeat.938@gmail.com |
| H: | aerismusic8@gmail.com |
| I: | farmmer.938@gmail.com |

A folder `K_VOICE` exists in each. Drop the file into any of them from the phone
app; it appears on PC1 within a minute and ak reads it from there.

Uploads are capped at 200 MB and limited to audio/zip extensions.

## Tone clone on the pod (measured 2026-11-03)

`scripts/tts_openvoice.py` narrates in K's tone with no key, no GPU and no fee.
edge-tts writes the Thai words; OpenVoice v2's tone-colour converter repaints
them with K's timbre, taken from the recording he sent. Because it is a tone
converter, not a text-to-speech clone, it never sees Thai phonemes -- it works on
any language, which is why Thai is possible at all here.

    python3 scripts/tts_openvoice.py --build-se work/k_voice/k_raw.wav
    python3 scripts/tts_openvoice.py --text "สวัสดีครับ" --out /tmp/a.mp3
    python3 scripts/tts_openvoice.py --script content/ch2_shorts/scripts.json \
        --index 32 --out work/ch2_shorts/32/voice.mp3

Measured on this pod's 4-core CPU:

| check | result |
|---|---|
| speaker similarity to K (cosine) | 0.56 (edge-tts) -> **0.88** (converted) |
| F0 median | 141.6 Hz -> **111.1 Hz** (K = 117.6 Hz) |
| Thai intelligibility | re-transcribed word-perfect |
| conversion speed | 9.4 s for a 10 s clip |
| Short built end to end | 25.4 s, **-14.8 LUFS / -2.9 dBTP** |

Setup lives at `/workspace/OpenVoice` (repo + `checkpoints_v2/converter`) and
`work/k_voice/k_se.pth` (K's speaker embedding). Both are outside the repo and
die with the pod; re-run the setup block in the script's docstring to rebuild.
`tau=0.5` measured best (0.8898 vs 0.878-0.888 for 0.1-0.9).
