# Channel admin — what actually runs the channels (2026-11-06)

K: "เอาไปเป็นแอดมิน คุมช่องเลย … ดันโพสต์ ตอบโพสต์". Aider is a *code* tool — it
cannot log in to YouTube. The real admin is **the YouTube Data API plus the tokens
already in the environment**, wrapped in `scripts/channel_admin.py`.

## Commands

    python3 scripts/channel_admin.py status                  # live numbers, all channels
    python3 scripts/channel_admin.py latest --limit 5        # newest uploads per channel
    python3 scripts/channel_admin.py comments                # comment threads
    python3 scripts/channel_admin.py draft <channel> "text"  # draft a Thai reply (free advisor)
    python3 scripts/channel_admin.py reply <commentId> "text"  # post a reply

`--channel genx|dharma|kongkeat` narrows any command to one channel.

## Measured 2026-11-06

- `status` works on all three channels today — no new consent needed.
- `latest` works; verified against dharma (newest 5 uploads with date + views).
- `comments` / `reply` return **403 insufficient authentication scopes**. The
  tokens were granted `youtube.upload` + `youtube.readonly` only. Comment read and
  reply need **`youtube.force-ssl`**.

## The one thing that needs the owner

Re-consent **once** per channel so the token also carries `youtube.force-ssl`:

    python3 scripts/yt_auth.py --scopes force-ssl --loopback --slug genx
    python3 scripts/yt_auth.py --scopes force-ssl --loopback --slug dharma
    python3 scripts/yt_auth.py --scopes force-ssl --loopback --slug kongkeat

Each prints a URL; open it, approve, done. The new token covers upload + read +
comments together, so nothing else changes. Until then, comment reading and
replying stay blocked — that is a scope limit, not a bug.

## What still needs a human, whatever the tooling

- **Pinned comments** are a Studio-only feature; the API has no endpoint. Cannot
  be automated.
- **Answering comments** and **posting** can be automated *after* the force-ssl
  re-consent.
- Aider (the code tool) stays useful for **writing the scripts** the admin runs;
  it does not operate the channel.

## Honest note on Aider for this repo

Asked twice to add the `latest` command, Aider (both the free Gemini model and
keyless Pollinations) **printed a plausible diff but did not write the file**, and
once hit a context-window limit on the real file. It proved out on small scratch
files, but on real repo files the free models are not reliable enough to trust
unreviewed. Use it for small, well-scoped chores and always check the file after.
