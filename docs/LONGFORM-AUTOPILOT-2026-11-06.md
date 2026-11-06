# Long-form autopilot — release → manifest → publish (2026-11-06)

The revenue lever is **watch-hours**, and the only rail that produces them at
scale is the dharma **night compilation** (120 min). Measured 0.060 watch-hours
per view against ~0.002 for a Short — a ~30x difference. So the goal is to make
that rail run without a person in the loop.

## What was broken

The night rail already worked: it built a verified 120-minute file, attached the
mp4 + mp3 to a GitHub Release, and opened a review issue. Then it **stopped**.

Turning the release into a live video needed a hand-written entry in
`content/ch2_publish.json` — the manifest that `publish-batch.yml` reads. Nothing
wrote that entry, so the rail's output sat on a Release until someone remembered
to wire it up. That is why, after weeks, only four long files were live
(`night_120`, `k_tone_01`, `night_110`, `night_money_01`) while more content sets
were ready.

The advisor panel agreed on the fix, two camps independently:
**automate the hand-off** (Google gemini-3.5 and OpenAI-OSS gpt-oss-20b; Zhipu
GLM was rate-limited and did not answer).

## What was built

`scripts/add_release_to_manifest.py` — writes the manifest entry from the release
tag, the content directory and the build receipt:

* **Idempotent.** An existing key keeps its `video_id` and `state`; only the
  URLs, duration and cover refresh. A weekly rebuild of the same content updates
  the entry instead of duplicating it, and can never re-upload.
* **Builds a real cover.** The night video's first frame is a 1920x1080 poster
  card; this makes a 1280x720 JPEG from the same image so the upload has a
  thumbnail (`assets/branding/farmmer/thumbs/<key>.jpg`).
* **Writes the description from the content.** It lists the set's own piece names
  as the chapter line, so the copy matches the audio without hand editing.

`.github/workflows/night-compilation.yml` — now runs the injector after the
release, commits the manifest, and **dispatches `publish-batch.yml` explicitly**.

> A push made with the default `GITHUB_TOKEN` **does not start another workflow**
> (GitHub's anti-recursion rule), so relying on publish-batch's push trigger would
> silently do nothing. The dispatch is explicit, and the job needs
> `actions: write` for it.

## Verified

* Injector on a temp manifest: **added** a new entry; re-run on the same key
  **updated** it and kept a planted `video_id` (no duplicate, no re-upload).
* `night_dharma_02` was already built **and published** as `night_money_01`
  (release `night-606f72d437a3-a74f6e`, 2026-11-06 02:37Z) — so a dispatch of it
  correctly skipped. The fingerprint guard works: identical content is not
  rebuilt.
* Full loop **proven end to end** 2026-11-06: `night_01` dispatched 15:23Z →
  built 124.1 min → release `night-eac9de443f2e-...` → manifest entry
  `night_sleep_01` added (commit `e72c996`) → `publish-batch` dispatched
  explicitly (run 42245195436) → **live** as
  `https://youtu.be/ZrjMi0pcDYo` ("ธรรมะก่อนนอน 120 นาที ปล่อยวางทุกเรื่อง
  หลับลึกถึงเช้า เสียงกล่อมจิตใจ", 124 min). No hand editing at any step.

**Long-form live on Farmmer after this change: 5** — `night_120`
`F4qFHoVpEyI`, `k_tone_01` `2PEjuEFpeY8`, `night_110` `q6VXmPP57xY`,
`night_money_01` `V7E6OZZJ3xQ`, `night_sleep_01` `ZrjMi0pcDYo`.

## The flow now

```
gen_night_scripts.py  (weekly, Gemini)      -> content/night_dharma_NN/
        |
night-compilation.yml (Mon 02:17 UTC)
   build_night.py  -> verified 120-min mp4 + receipt
   gh release create  -> media on a Release
   add_release_to_manifest.py -> content/ch2_publish.json
   commit + dispatch publish-batch.yml
        |
publish-batch.yml -> videos.insert -> live on Farmmer, id recorded back
```

## ch4 gets the same treatment

`ch4-longform.yml` (the เรื่องเล่าการ์ตูน family-moment rail) had the same hole
**and a worse one**: its release tag was a fixed `ch4-family-long-01`, so a
rebuild of different content clobbered the release and the manifest could point
at bytes that did not match the title. The tag is now a fingerprint of the
content and the rail, the manifest entry is written automatically, and
`publish-ch4` is dispatched explicitly.

`add_release_to_manifest.py` is per-channel now: `--channel dharma|kongkeat`
picks the tags, the category (22 for ch2, 24 for ch4), the cover directory and
the description builder.

## Still manual (deliberately)

* **ch4 content sets** are not generated on a schedule yet — ch4-longform takes
  an explicit `content` directory. `gen_night_scripts.py` writes dharma copy, so a
  ch4 generator is the next piece if the family rail earns its own cadence.
* **ch4 has no schedule trigger.** Its build is dispatched by hand or by foreman;
  ch2's weekly night build is the one that runs itself.

## Who dispatches what (no scheduler required)

GitHub's `schedule` trigger has never fired for this repo, so nothing depends on
it. Every push to `content/**` or `scripts/foreman.py` runs **foreman**, which
dispatches only what is due; the **watchdog** re-dispatches itself every ~2 hours
to keep the chain alive. foreman now also drives **polish-all** (daily, 08:00-12:00
UTC) and **watch-hours** (weekly) — both were previously missing from its plan and
so depended on a scheduler that never fired.
