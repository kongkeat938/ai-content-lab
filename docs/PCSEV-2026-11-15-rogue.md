# PCSEV — the "rogue uploader" is our own sibling repo (2026-11-15)

Owner K pushed back: *"it's weird — you made all of this; who else could post? it
has to be a bug you created. go check everything."* K was right.

## 1. Problem
Clips appear on our channels that `audit_channels.py` flags as "LIVE rogue upload
outside the rails" — on the channel but in no manifest. The prior conclusion
(`docs/PCSEV-2026-11-12-private.md`) was "an external attacker with a leaked OAuth
token, signature `en-US`/category 27/old brand". K did not believe it.

## 2. Cause (measured 2026-11-15)
Two separate errors, both ours:

1. **A fabricated signature.** The audit reads `videos.list(part="snippet,statistics,
   contentDetails")` — it never reads a per-video `categoryId`, `defaultLanguage` or
   `defaultAudioLanguage`. The "these carry `en-US`/category 27 and an old brand, so
   they are NOT our rails" sentence was written into the alert body by hand. The
   clips in fact carry **`th`, category 22/24**, and our own `— ช่องพี่น้อง —` promo
   block (`scripts/promote_channels.py`). The whole "external attacker" story rested
   on an unmeasured sentence.
2. **A shared identity.** The sibling repo `aerismusic8-alt/aeris-drive-automation`
   maps our exact channels — `ops/ax_channels.json` names ch1 `UCI6Efsg…` (genx),
   ch2 `UCM3QO5L…` (dharma), ch4 `UC7gCIu4G…` (kongkeat-story) — and its workflows
   hold the **same** secrets (`YT_CH1..CH4_REFRESH_TOKEN`, `YT_CLIENT_ID`,
   `YT_CLIENT_SECRET`; `ops/patches/ai-content-lab-let-ai-post.patch`). An upload from
   either repo reaches our channels with no manifest entry, so the audit reads it as
   "outside the rails".

Evidence the ids are ours/known: `fn38n2-CRm0` (called rogue) is entry **88** in our
`content/ch1_shorts.json`, committed by our rail (`publish(genx): record Short 88`);
`UcgpJinQUcs` / `cQ69KqIGjTg` are in `content/ch1_shorts_remakes.json`; `recorded_ids`
already returns True for all of them.

## 3. Solution
- Stop asserting what the audit does not measure. The alert now states only
  "unrecorded + recent" and names the shared-OAuth-client cause.
- Separate the identity: each repo needs its **own** OAuth client; revoke any grant
  we do not recognise (K, at a browser — `docs/K-PHONE-ACTION.md`).
- A guard that can FAIL so the fabrication cannot return.

## 4. Execute
- `scripts/audit_channels.py`: new pure `rogue_alert_body(live, now)`; the old
  fabricated sentence removed; body now names the shared-client cause.
- `scripts/test_rogue_alert_body.py`: fails if the body claims `en-US` / `category 27`
  / `defaultLanguage=th` / "NOT our rails", or if it drops the measured cause.
- `docs/PCSEV-2026-11-12-private.md`: correction banner.

## 5. Verify (measured live)
- Panel `scripts/advise.py` 2026-11-15: **5/5 advisors** → "(b) our own/sibling
  automation sharing tokens", not an outside attacker.
- `test_rogue_alert_body.py` **can FAIL**: injected the old sentence → rc=1; restored
  → rc=0.
- Full suite **PASS=70 FAIL=0**.
- **Not done (honest):** the actual separation (per-repo OAuth client / revoke) needs
  K at a Google screen; the pod cannot reach it (`cloudresourcemanager` 403).
