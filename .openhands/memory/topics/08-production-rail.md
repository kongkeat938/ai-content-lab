# 08 — the production rail (story → clip → queue), built 2026-11-20

K's order that shaped it: *"เราได้งานคุณภาพตามต้องการแล้ว ที่เหลือแค่วางระบบผลิต ใจเย็นๆ
ค่อยทำให้เสียร ลดข้อผิดพลาดให้ได้มากที่สุด"* — quality is settled; the remaining work is the
production system, built slowly and with as few errors as possible.

So the rail is built around **refusing** rather than shipping, and every refusal is measured.

## `scripts/produce.py` — one story → one clip

```
story JSON (K wrote it)  →  beats (verbatim)  →  reserve N free pictures  →  render_clip
                         →  clip_standard  →  assets/queue/index.json
```

The rail **never writes narration**. `beats_of()` copies `hook`, every `lines[i]`, then `cta`
character for character. K owns the words; the rail owns the machinery. A guard asserts the
narration equals his text exactly.

### The four refusals (each measured)

| Refusal | Why it exists | Measured |
|---|---|---|
| a story with an empty line | a dropped beat is a broken clip | refused before any picture is reserved; stock unchanged 4 → 4 |
| too little stock | handing out what it has loses the rest | needs 9, has 4 → refuses whole clip, stock unchanged 4 → 4 |
| render exits non-zero | a failed render must not eat the library | `release()` puts every reserved picture back |
| clip fails `clip_standard` | substandard is HELD, not queued | moved to `.held.mp4`, exit 1 |

### `image_vault.take_free()` / `release()` (new)

`take_free(count, channel, clip)` is **all-or-nothing** under the vault lock: a producer needing
5 and finding 3 stops *before* claiming, so a failed run burns nothing. `release(md5s, clip)`
frees **only that clip's own** reservations — releasing another clip's picture would un-ban
something already used. Both measured.

### The bug this uncovered: a spent picture lost its recipe

`stamp()` **replaced** the whole vault entry, so the moment a picture was spent its
`gen/seed/palette/size` were gone. Measured 2026-11-20: after one real clip, **all 5 entries
came back `gen: null`** — a recycled pod could never rebuild a picture a finished clip refers
to, so the clip could never be re-rendered and the ban protected nothing.

Fix: `stamp()` now **updates** the record (`rec = dict(have); rec.update(...)`). Guard
`test_a_spent_picture_keeps_its_recipe` goes RED against the old code (gen=None) and GREEN now.
The 5 damaged entries were repaired from `assets/art/library/stock/manifest.json`, which still
held their recipes; all 5 rebuild to an exact md5. The other 102 legacy entries are pictures
already live in posted videos — they need no rebuild.

## The queue (rule 3)

`assets/queue/index.json` is **one** index, written under `make_short.ledger_lock` so two rails
cannot lose an entry. An entry: `id, channel, story (repo-relative), story_id, title, file,
pictures[], music, metrics, state=queued, built_at`.

* The **index is committed**; the **media is not** (`assets/queue/*.mp4` is gitignored — a clip
  is 20-30 MB and the repo is public). Media ships as a Release asset, exactly as
  `publish_batch` expects (`video_url`).
* `test_no_pending_uploads.queued_files()` reads the index, so a clip that is filed is not an
  orphan build, while a stray `.mp4` with no index entry still fails the guard (measured RED).

## Music

Rule 4 asks for AI music. `ai_music.py` needs `torch`, which is **absent on this pod** (measured
2026-11-20: torch/transformers/audiocraft all ModuleNotFoundError). `produce.py` therefore uses
`make_bed.py` — a seamless ambient bed synthesised from first principles, no model, deterministic
(root picked from an md5 of the clip id, so a rebuild picks the same bed). `--no-music` disables it.
Install torch + MusicGen and point `bed_for()` at `ai_music.py` when a GPU-ish pod is available.

## Guards

`scripts/test_produce.py` — **17 checks, 0 failures.** Real clip built, verified by
`clip_standard` (−13.9 LUFS, 1920×1080, 3 shots), filed in the index, its pictures banned.

Live proof 2026-11-20: `content/motion/01.json` (K's story) → `assets/queue/dharma-01.mp4`,
ffprobe `1920x1080 yuv420p tv bt709 14.13 s 25.9 MB`, −14.0 LUFS, 5 shots, 5 pictures reserved
and banned.

## Not done yet (honest)

* No workflow wires `produce.py` into a schedule — K holds `content/STOP`, and a rail now would
  be the second copy the map forbids. The rail is ready for the day he lifts the stop.
* No 4K master (rule 5 says 720p out; the renderer currently emits 1080p).
* The queue index has no uploader that reads it yet — `publish_batch` still reads the old
  `content/ch*_publish.json` manifests. That is the next link to build.
