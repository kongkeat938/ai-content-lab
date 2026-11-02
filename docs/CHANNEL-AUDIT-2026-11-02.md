# CHANNEL AUDIT — 2026-11-02

Measured against the live channels with each channel's own token
(`scripts/audit_channels.py`). Numbers, not impressions.

## Defects found and fixed

### 1. Every channel answered as ch1 (tool bug, fixed)
`yt_auth.load_credentials()` reused whatever token file was already on disk and
never checked the channel afterwards, and all channels share one path. Auditing
the three channels reported `ตาต้า GenX` three times. `publish_youtube.py` was
safe only because it calls `assert_channel()` separately.

Fixed in `scripts/yt_auth.py`: when an expected channel is given, the token file's
channel is checked first, and the matching refresh token is picked from the
environment when the file belongs to a different one. `audit_channels.py` now
fails loudly if a token answers as the wrong channel.

### 2. Wrong-channel metadata on 13 live videos (root cause, fixed)
`ax_make_episode.step_meta()` called `episode_meta.build()` **without** a channel,
so `build()` used its `ch2` default and every ch1/ch4 episode shipped ch2's intro,
chapter headings and tags verbatim. Confirmed live:

| channel | video | carries |
|---|---|---|
| ch1 | `uKJCdBRZtBg` | ch2's intro |
| ch4 | `n0k_tUNXFtw` | ch2's intro |

Fixed on branch `fix/per-channel-meta` in `ax-workspace`:
`step_meta` passes `--ch`, `build()` now requires a channel (a `# CHANNEL:` line
still wins) and raises on an unknown one. Guarded by `ops/test_channel_meta.py`
(16 checks). **Needs K's word to merge** — it lives on a branch.

### 3. No funnel from any video (fixed)
- **33 of 40 Shorts** name a channel in words but link no video.
- **64 of 64 long-form** videos link neither a sibling channel nor a playlist.
- The ch1 long-form CTA reads "ฟังคลิปอื่นในช่องได้เลย" — with no link.

`scripts/promote_channels.py` appended one idempotent block (sibling channel +
channel home) to every description missing it. Applied to the live channels and
verified: **tags changed 0, category changed 0, no description shrank, 61/64 now
carry the block.** 3 were skipped because their description was already at
YouTube's 5,000-character limit.

## Defects found, not yet fixed (need K or are K's own)

- **Wrong playlists on ch1 and ch2.** ch1 has `ตาต้า Music` and `หนังสั้น เรื่องสั้น
  วีดีโอ ละคร`; ch2 has `Lanternwild — Shorts/Songs/Episodes`. These are not this
  project's names, `Lanternwild — Songs` is empty, and the naming is not the
  "ช่องนี้" pattern. Playlist titles are editable in Studio; I did not rename them
  without asking.
- **No playlists on ch1 for its own series**, and `genx` playlists hold only 4 of
  37 videos.
- **ch2 has 2 videos titled `ปล่อยวาง แล้วใจจะเบา`** — a near-duplicate title is a
  throttle signal.
- **8 ch1 videos have no description at all.**

## Free promotion channels that are real

The winning format in this niche is the long file (a competitor, *Wisdom Woven*,
ships 1 h 34 m). On-platform, the highest-leverage free levers are the ones above:
the funnel, end screens, pinned comments, and the Community tab. Off-platform,
free and legitimate (no view-buying — it violates ToS and damages reach):

- **Cross-post the Shorts to Facebook/Instagram/TikTok Reels** with a link back.
  This is the cheapest way to borrow an audience that already exists.
- **Thai-language Facebook groups** (dharma / ธรรมะ / นอนไม่หลับ / ปรัชญาชีวิต).
  Share a clip, not an advert, and follow each group's rules.
- **Pinterest** — sleep/dharma quote images with a link; evergreen, free.
- **YouTube's own free tools**: Analytics, Test & Compare (thumbnail A/B), the
  Inspiration tab. No subscription needed.

Do **not** use "promotion" services that sell views or subscribers.
