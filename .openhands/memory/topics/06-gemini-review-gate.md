# 06 — The Gemini review gate — REMOVED 2026-11-21

**Status: removed.** K, 2026-11-21: *"Gemini ลบไปเลย ไม่ต้องใช้ระบบนี้มาตรวจแล้ว"*.
The ledger, the approval rule ("งานไม่ผ่าน Gemini = ห้ามอัพ") and the Gemini auto-fix are gone:
`scripts/review_ledger.py`, `test_review_ledger.py`, `fix_with_gemini.py`,
`test_fix_with_gemini.py` and the whole `docs/reviews/` directory were deleted in that commit.
`scripts/test_upload_autonomy.py` fails if an approval rule creeps back into the docs or a
publish path.

**What replaced it:** a gate that can FAIL + a live measurement is the bar. ak publishes on its
own when the gates pass (cap, cadence, `short_standard`, `clip_standard`, `qa_gate`).

**Advisor is not a gate.** `scripts/advise.py` still exists as optional drafting help
(K, 2026-11-18: panel = Gemini alone; follow its advice when stuck). It is never an approval step.

**Lessons kept from the removed system** (still true):
- A rule you cannot check is a rule that is already broken — "was this reviewed?" was an opinion
  until a digest proved *what* was reviewed.
- A digest proves the evidence is about *this content*, not that a human read it.
- A missing or unreadable evidence file is `None`, never a pass — the same false-pass trap as a
  403 gate with `|| echo 0`.
