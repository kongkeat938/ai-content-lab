#!/usr/bin/env python3
"""The restore tool must target exactly the clips a false "rogue" label hid.

`restore_wrongly_hidden.wrongly_hidden()` must return exactly
`hidden ∩ known_uploads` -- no more (never a genuinely-unrecorded clip) and no
fewer (every hidden clip our own predecessor rail recorded). The ledgers are
append-only and the restore rail prunes the ids it resolves, so the LIVE
intersection can legitimately be empty; the selection PROPERTY must still hold.

This guard can FAIL: break the intersection and the synthetic cases below fail,
and an empty `known` set must yield an empty selection.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import restore_wrongly_hidden as rw  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def select(tmp: Path, hidden: list[dict], known: list[str]) -> set[str]:
    (tmp / "hidden.json").write_text(json.dumps({"hidden": hidden}), encoding="utf-8")
    (tmp / "known.json").write_text(
        json.dumps({"uploads": [{"video_id": k} for k in known]}), encoding="utf-8")
    rw.HIDDEN, rw.KNOWN = str(tmp / "hidden.json"), str(tmp / "known.json")
    return {h["video_id"] for h in rw.wrongly_hidden()}


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        hid = [{"video_id": "A"}, {"video_id": "B"}, {"video_id": "C"}, {"video_id": "STRANGER"}]

        got = select(tmp, hid, ["A", "C", "Z"])
        if got != {"A", "C"}:
            fail(f"synthetic selection wrong: got {sorted(got)} want ['A', 'C']")
        if "STRANGER" in got:
            fail("a hidden clip that is not a known upload was selected")
        if select(tmp, hid, []):
            fail("empty known_uploads must select nothing")

    hidden = {h["video_id"] for h in
              json.loads((ROOT / "content" / "rogue_hidden.json").read_text(encoding="utf-8"))["hidden"]}
    known = {u["video_id"] for u in
             json.loads((ROOT / "content" / "known_uploads.json").read_text(encoding="utf-8"))["uploads"]}
    rw.HIDDEN = str(ROOT / "content" / "rogue_hidden.json")
    rw.KNOWN = str(ROOT / "content" / "known_uploads.json")
    got = {h["video_id"] for h in rw.wrongly_hidden()}
    if got != (hidden & known):
        fail(f"live selection != hidden∩known: got {sorted(got)} want {sorted(hidden & known)}")
    if got - known:
        fail(f"live selection includes a non-upload: {sorted(got - known)[:5]}")

    print(f"OK: selection == hidden∩known (synthetic cases pass; live {len(got)} selected "
          f"of {len(hidden)} hidden / {len(known)} known)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
