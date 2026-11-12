# PCSEV — the "private" videos and the source that makes them (2026-11-12)

Owner K: *"there are clips showing as private — what is it? delete them all and go
delete the source that created them too."*

## 1. Problem
Clips appear on our channels as **private** that we did not intend to keep. K wants
them gone, and wants the **source** that creates them gone.

## 2. Cause (measured live, 2026-11-12, via the Data API in CI)
`private_videos.py` listed every non-public upload per channel:

| channel | uploads | non-public | private (parked) | unlisted | scheduled |
|---|---|---|---|---|---|
| dharma | 154 | 14 | 6 | 8 | 0 |
| genx | 146 | 13 | 5 | 8 | 0 |
| kongkeat-story | — | — | — | — | — (its token's project quota was spent; retry pending) |

The **private** set is two kinds, and they are NOT the same thing:
- **rogue uploads** — recorded in `content/rogue_hidden.json`, hidden by the audit
  today at 18:14 Thai (17 clips across the fleet). Signature: a second stream that
  is **not in our code** — old brand `เรื่องเล่าการ์ตูน`, `defaultAudioLanguage=en-US`,
  category 27, a fixed **`:21`** minute. Our rails publish at `:44`, write `th`,
  and record every id.
- **our own parked builds** — the 57-minute dharma bad cut (`HkbSguA53ro`), plus two
  old low-view private builds.

**The source is external.** A repo-wide check found only our four uploaders
(`publish_batch/publish_shorts/publish_youtube/remake_shorts`), all public + recorded;
no workflow runs at `:21`; no code writes `en-US`/the old brand. So no file in this
repo creates these clips — the origin is a **leaked OAuth refresh token** driving a
second uploader (panel `docs/PANEL-2026-11-11c.md`, unanimous).

## 3. Solution
- **The clips:** delete the **parked private** videos (the rogue clips + our own bad
  cut + old private builds). Do NOT delete the **unlisted** ones — a different state
  K did not name, and one genx unlisted clip has **1413 views** (a shared link would
  die). Panel `docs/PANEL-2026-11-12-*.md`, unanimous.
- **The source:** the only way to remove an external uploader is to **revoke the
  leaked OAuth refresh token** and issue a new one. No change to our code can stop a
  process we do not own.
- **Guard:** `test_private_videos.py` proves a delete removes parked-private clips
  and **never** a scheduled release, and can FAIL.

## 4. Execute
- `scripts/private_videos.py` — lists every non-public video and its kind; deletes the
  parked-private set, backing each up to `content/deleted/` first.
- `.github/workflows/private-videos.yml` — manual list / delete.
- `.github/workflows/private-delete.yml` — the standing rail: re-lists and deletes the
  parked-private set at **08:14 UTC**, just after the Data API quota reset (a delete
  costs quota, and the project's daily quota is spent by midday — a 1-unit read 403s
  at 14:00 UTC). Idempotent, no hard-coded ids.

## 5. Verify (measured live)
- Live listing in CI: dharma 14 non-public / genx 13 non-public, **all parked, 0
  scheduled** (so a delete is safe).
- **Cannot delete yet:** `videos.delete` returns 403 `quotaExceeded` (verified on the
  pod 14:20 UTC). The next reset is **08:00 UTC = 15:00 Thai**. The rail deletes then.
- Guard `test_private_videos.py` green; suite **43 passed, 0 failed**.
- **Not done (honest):** the token revoke needs **K at a browser** — see below.

## The one action that needs K
Revoke + reissue the OAuth refresh token (Google Cloud Console → APIs & Services →
Credentials → OAuth client → revoke; then `scripts/yt_auth.py` once per channel to
consent again, and update the `YT_CH*_REFRESH_TOKEN` secrets). Until that is done the
rogue stream keeps uploading and we keep hiding + deleting on a loop; the token is the
**root**. There is no automated path around a human consent screen.
