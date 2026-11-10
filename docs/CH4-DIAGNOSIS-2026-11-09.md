# ch4 diagnosis: views grow, subscribers do not (2026-11-09)

K asked why kongkeat (ch4) gets views but its subscriber count never moves. This
is the measurement, then the advisor panel, then the change shipped.

## The measurement (YouTube Analytics)

| channel  | views 30d | subs+ | subs/1k | avg view % | avg dur | shares | comments |
|----------|-----------|-------|---------|------------|---------|--------|----------|
| genx ch1 | 32,690    | 176   | 5.38    | 69.5 %     | 32 s    | 79     | 15       |
| dharma ch2 | 22,873  | 91    | 3.98    | 13.7 %     | 47 s    | 29     | 2        |
| **kongkeat ch4** | **6,148** | **11** | **1.79** | **59.5 %** | **33 s** | **0** | **0** |

- ch4 net subscribers, 90 days: **+10** (11 gained, 1 lost). genx: **+168**.
- ch4 traffic (10 d): Shorts feed 4,508 · search 123 · channel 24 ·
  **from subscriber 1** · related 7. So the views are real Shorts-feed views.
- ch4 daily views are steady (~400-1,500/day for two weeks) -- no shadow ban, no
  drop to zero. The problem is not reach.
- ch4 retention (59.5 %) is close to ch1's (69.5 %), so the hook and length are
  not the obvious fault. The clips are watched; they are not *converted*.

**Conclusion from the numbers:** ch4 has a distribution-to-relationship problem,
not a content-reach problem. It is the one channel with 0 shares and 0 comments,
and the lowest subscribe rate, at the same retention as a channel that converts
3x better.

## The panel (K's rule: no decision to a human, ask >= 5 AI advisors)

Five independent advisors answered (gemini-3.5, gemini-3.1, gemini-flash,
gemini-preview, pollinations; openrouter had no key). The brief is
`docs/CONSULT-ch4-2026-11-09.md`.

**Unanimous finding:** the subscribe ask sits at the tail of every clip
(`cta` is the last line), after the viewer has already swiped away. The fix is to
speak the CTA *earlier* -- after the story's peak, not after it ends -- and to make
it emotional (a question or a share invite), not a bare "กดติดตาม".

Representative answers (Thai, condensed):
- gemini-3.1: "ย้าย CTA มาไว้ช่วงกลางคลิป (หลังพีคสุด) ... ห้ามขอให้กดติดตามท้ายคลิป
  เพราะคนดูปิดไปแล้ว"
- gemini-preview: "ย้าย CTA มาวินาทีที่ 15-20 ... ห้ามวาง CTA หลังวินาทีที่ 25
  เพราะสถิติบอกชัดว่าคนดูหายไปเยอะแล้ว"
- gpt-oss-20b: "CTA ไม่โดนจับจังหวะ ... แสดง CTA ทันทีหลังคลิป 10-15 s"
- pollinations: "ใส่ CTA 5 วินาทีก่อนจบ ... 'อยากดูเรื่องต่อ? กดติดตาม + แชร์'"

Panel TEST: move the CTA to the middle of the clip (after the peak).
Panel METRIC: subs per 1k views and comments, up from 1.79 and 0, within ~3 days.

## The change shipped

`make_short.py` gains `spoken_sequence(script, cta_mid)`: with `cta_mid` the CTA is
inserted after the story's peak (`CTA_MID_RATIO = 0.6` through the lines) instead
of appended last; captions follow the same order. `publish_shorts.py` and
`remake_shorts.py` pass `--cta-mid` when the channel spec sets `cta_mid: True`,
and only **kongkeat** sets it. The other two channels keep the tail CTA.

Measured end-to-end: a real ch4 render (id 71, 41.9 s) places the CTA caption at
index 6 of 10 (mid), not 9 (tail).

## How this is judged (the loop already measures it)

The pace loop grades each post and the analytics rail records subs/shares/comments.
This change is kept only if ch4's subs/1k and comments rise over the next ~3 days;
if they do not, the panel's next step (an emotional CTA line, then a pinned
comment) is the fallback. The experiment is reversible: remove `cta_mid` from the
kongkeat spec.
