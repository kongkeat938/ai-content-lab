# The no-browser path — YouTube Data API from CI

Measured 2026-11-03. The rule: **when Studio UI needs a human and the pod's
browser login is gone, do not ask K to log in — use the Data API.** A refresh
token in a repo secret does the same job unattended and survives every recycle.

## What dies on a pod recycle
- `$HOME` is reset: `~/.chromium-profile` (the Studio login) and `~/.config/`
  token files go. `scripts/start_novnc.sh` restarts the desktop but NOT the login.
- The workspace/repo survives. `work/` survives (it is gitignored but on disk).

## Quota facts
- API daily quota resets at **midnight Pacific = 08:00 UTC**.
- `thumbnails.set` has its **own** 100/day quota, separate from the 10,000 units
  the rest of the API shares — but a fully-spent project quota still returns
  `403 quotaExceeded` for it too. Treat that as a **deferral, not a failure**.

## The rail (ch2, reusable for any channel)
- `scripts/set_thumbnails.py` — sets every entry of `content/ch2_thumbnails.json`
  (`video_id -> image`). `--dry-run` / `--check` / `--only`. Reads creds from
  `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_CH2_REFRESH_TOKEN`.
- `.github/workflows/set-thumbnails.yml` — runs at 08:07/09:07/10:07/11:07 UTC
  (retry window after the reset) and on manifest/image change. Idempotent.
- Repo secrets set via the Actions secrets API, sealed-box encrypted. PyNaCl:
  use `nacl.public.SealedBox(pub).encrypt(...)`. `SecretBox` does not exist and
  `Box(pub, priv)` needs a real keypair.
- `publish_youtube.py` already had `thumbnails.set`; this rail is the same call
  without needing the whole upload path.

## Traps
- **Do not trust old video-id lists.** `9bytRcx7SaY` 404s at every thumbnail
  size; `Mv0jl7KhxIE` 401/403s on oEmbed. Verify with oEmbed or the thumbnail
  sizes before adding an id to a manifest.
- **YouTube throttles the pod IP**: after a few fetches the RSS feed 404s and
  oEmbed 401/403s for a while. Space the calls, or fetch from PC1.
- Thumbnails are 1280x720 JPG, dark-blue + gold, 3-5 Thai words — built by
  `scripts/make_thumbnail.py` from an art PNG in `work/ch2_branding/`.
