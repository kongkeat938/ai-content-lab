#!/usr/bin/env python3
"""The restore tool must target exactly the clips a false "rogue" label hid.

Measured 2026-11-15: 30 of the 32 ids in `content/rogue_hidden.json` are uploads of
our own predecessor rail (`content/known_uploads.json`), so they were hidden on a
false label. `restore_wrongly_hidden.wrongly_hidden()` must select exactly that
intersection -- no more (never a genuinely-unrecorded clip) and no fewer.

This guard can FAIL: empty `known_uploads.json` and the selection goes empty; a
hidden id that is NOT a known upload must never be selected.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import restore_wrongly_hidden as rw  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def main() -> int:
    hidden = {h["video_id"] for h in
              json.loads((ROOT / "content" / "rogue_hidden.json").read_text(encoding="utf-8"))["hidden"]}
    known = {u["video_id"] for u in
             json.loads((ROOT / "content" / "known_uploads.json").read_text(encoding="utf-8"))["uploads"]}

    got = {h["video_id"] for h in rw.wrongly_hidden()}
    want = hidden & known
    if got != want:
        fail(f"selection is wrong: got {len(got)} want {len(want)}")
    if not want:
        fail("no wrongly-hidden clip is selected; the restore rail would do nothing "
             "even though the predecessor rail's uploads are recorded")
    leaked = got - known
    if leaked:
        fail(f"selection includes a clip that is NOT a known upload: {sorted(leaked)[:5]}")

    # And the guard can FAIL: a video that is hidden but NOT a known upload must
    # never be selected, or the tool would un-hide a genuinely unrecorded clip.
    stranger = (hidden - known) or {"__none__"}
    if (hidden - known) and (hidden - known) & got:
        fail("a hidden clip that is not a known upload was selected")

    print(f"OK: restore selects {len(got)} clip(s) -- exactly the wrongly-hidden "
          f"intersection; {len(hidden - known)} genuinely-unrecorded id(s) are left alone")
    return 0


if __name__ == "__main__":
    sys.exit(main())
