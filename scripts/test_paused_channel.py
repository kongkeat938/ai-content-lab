#!/usr/bin/env python3
"""A paused channel must not produce content -- and the pause must be per channel.

The pause is a business decision that flips: kongkeat was paused 2026-11-12 (dead:
+3 views/day, 0 subs, 0.5 long-form watch-hours in 28 days) and UNPAUSED 2026-11-13
on K's order. So this guard does NOT assert that kongkeat is paused -- it asserts the
*mechanism*, driven by a synthetic PAUSED file, and keeps passing whether the live
file names a channel or not:

  * a name in `content/PAUSED` makes publish_shorts / publish_batch skip that channel
    and exit 0 (a clean skip, no upload);
  * the refusal is per channel -- a channel that is NOT paused is not gated (so the
    guard can fail: a blanket "always skip" would gate dharma too);
  * health.py maps each paused channel to its rails, and every mapped rail is a
    watched rail (an unmapped name would be a silently dead rail).

    python3 scripts/test_paused_channel.py
"""
from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

FAILS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" -- {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


def call_main(mod, argv: list) -> tuple[int, str]:
    """Run mod.main() with argv, capture stdout and the return code."""
    buf = io.StringIO()
    old = sys.argv
    sys.argv = ["x"] + argv
    rc = 0
    try:
        with contextlib.redirect_stdout(buf):
            rc = mod.main()
    except SystemExit as e:  # argparse / credential exits are fine here
        rc = e.code if isinstance(e.code, int) else 1
    finally:
        sys.argv = old
    return rc, buf.getvalue()


def main() -> int:
    import publish_shorts as ps
    import publish_batch as pb
    import health as H

    real = os.path.join(ROOT, "content", "PAUSED")
    check("content/PAUSED exists", os.path.exists(real))
    check("live PAUSED parses to a set", isinstance(ps.paused_channels(), set),
          str(ps.paused_channels()))

    # Drive the mechanism from a synthetic PAUSED file, so the guard proves the
    # pause works whether or not the live file names a channel today.
    with tempfile.TemporaryDirectory() as td:
        os.makedirs(os.path.join(td, "content"))
        with open(os.path.join(td, "content", "PAUSED"), "w", encoding="utf-8") as fh:
            fh.write("# a comment must be ignored\nkongkeat\nkongkeat-story\n")
        old_ps, old_pb, old_h = ps.ROOT, pb.ROOT, H.ROOT
        ps.ROOT, pb.ROOT, H.ROOT = td, td, td
        try:
            print("a name in PAUSED is read; comments are ignored")
            check("paused_channels reads both spellings",
                  ps.paused_channels() == {"kongkeat", "kongkeat-story"},
                  str(ps.paused_channels()))

            print("a paused Shorts channel is skipped, cleanly")
            rc, out = call_main(ps, ["--channel", "kongkeat", "--dry-run"])
            check("exit code is zero", rc == 0, f"rc={rc}")
            check("prints the pause notice", "paused" in out, out[-200:])

            print("a paused long-form manifest is skipped, cleanly")
            man = os.path.join(td, "ch4_publish.json")
            with open(man, "w", encoding="utf-8") as fh:
                fh.write('{"channel_slug": "kongkeat-story", "videos": []}')
            rc2, out2 = call_main(pb, ["--manifest", man, "--dry-run"])
            check("exit code is zero", rc2 == 0, f"rc={rc2}")
            check("prints the pause notice", "paused" in out2, out2[-200:])

            print("the refusal is per channel -- a non-paused channel is NOT gated")
            # dharma is not in this PAUSED file, so main() must NOT short-circuit on
            # the pause. It fails later (no build/creds), which is fine; the point is
            # the pause notice is absent -- a blanket "always skip" would fail here.
            rc3, out3 = call_main(ps, ["--channel", "dharma", "--dry-run"])
            check("dharma is not reported paused", "paused" not in out3, out3[-200:])

            print("health.py maps a paused channel's rails, and only watched ones")
            pr = H.paused_rail_names(H.paused_channels())
            check("health reads the same PAUSED list",
                  {"kongkeat", "kongkeat-story"} <= H.paused_channels(),
                  str(H.paused_channels()))
            check("health knows publish-ch4 + ch4-longform are the ch4 rails",
                  {"publish-ch4", "ch4-longform"} <= pr, str(pr))
            # A mapping to a rail health does not watch would be silently dead.
            check("every paused rail is a watched rail", pr <= set(H.EXPECTED),
                  str(pr - set(H.EXPECTED)))
            # No pause file -> nothing suppressed, so the skip cannot be blanket.
            check("no pause file -> no suppressed rails",
                  H.paused_rail_names(set()) == set())
        finally:
            ps.ROOT, pb.ROOT, H.ROOT = old_ps, old_pb, old_h

    print()
    if FAILS:
        print(f"FAIL: {len(FAILS)} check(s) failed: {FAILS}")
        return 1
    print("OK: a paused channel is skipped, and only the paused one")
    return 0


if __name__ == "__main__":
    sys.exit(main())
