#!/usr/bin/env python3
"""A paused channel must not produce content -- and the pause must be per channel.

Business decision (2026-11-12): kongkeat is dead (measured +3 views/day, 0 subs for
three days, 0.5 long-form watch-hours in 28 days), so its production stops. This
guard makes the pause a code invariant, not a hope:

  * `content/PAUSED` lists kongkeat (both spellings: the Shorts key `kongkeat` and
    the long-form manifest slug `kongkeat-story`);
  * publish_shorts / publish_batch refuse a paused channel and exit 0 (a clean skip);
  * the refusal is per channel -- a channel that is NOT paused is not gated (so the
    guard can fail: if the check were a blanket "always skip", this test fails).

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

    print("content/PAUSED names the dead channel, in both spellings")
    check("PAUSED exists", os.path.exists(os.path.join(ROOT, "content", "PAUSED")))
    check("paused_channels lists kongkeat", "kongkeat" in ps.paused_channels(),
          str(ps.paused_channels()))
    check("paused_channels lists kongkeat-story", "kongkeat-story" in ps.paused_channels(),
          str(ps.paused_channels()))

    print("a paused Shorts channel is skipped, cleanly")
    rc, out = call_main(ps, ["--channel", "kongkeat", "--dry-run"])
    check("exit code is zero", rc == 0, f"rc={rc}")
    check("prints the pause notice", "paused" in out, out[-200:])

    print("a paused long-form manifest is skipped, cleanly")
    # Point publish_batch at a paused manifest; the guard returns before any upload.
    with tempfile.TemporaryDirectory() as td:
        man = os.path.join(td, "ch4_publish.json")
        with open(man, "w", encoding="utf-8") as fh:
            fh.write('{"channel_slug": "kongkeat-story", "videos": []}')
        rc2, out2 = call_main(pb, ["--manifest", man, "--dry-run"])
        check("exit code is zero", rc2 == 0, f"rc={rc2}")
        check("prints the pause notice", "paused" in out2, out2[-200:])

    print("the refusal is per channel -- a non-paused channel is NOT gated")
    with tempfile.TemporaryDirectory() as td:
        os.makedirs(os.path.join(td, "content"))
        with open(os.path.join(td, "content", "PAUSED"), "w", encoding="utf-8") as fh:
            fh.write("kongkeat\nkongkeat-story\n")
        old = ps.ROOT
        ps.ROOT = td
        try:
            check("paused_channels is scoped to the file", ps.paused_channels() ==
                  {"kongkeat", "kongkeat-story"}, str(ps.paused_channels()))
            # dharma is not paused -> main() must NOT short-circuit on the pause.
            # It fails later (no build dir), which is fine; the point is the
            # pause notice is absent, so a blanket skip would fail this check.
            rc3, out3 = call_main(ps, ["--channel", "dharma", "--dry-run"])
            check("dharma is not reported paused", "paused" not in out3, out3[-200:])
        finally:
            ps.ROOT = old

    print("health.py treats a paused channel's rails as quiet on purpose")
    import health as H
    pr = H.paused_rail_names(H.paused_channels())
    check("health reads the same PAUSED list",
          {"kongkeat", "kongkeat-story"} <= H.paused_channels(), str(H.paused_channels()))
    check("health knows publish-ch4 + ch4-longform are paused",
          {"publish-ch4", "ch4-longform"} <= pr, str(pr))
    # A mapping to a rail health does not watch would be silently dead.
    check("every paused rail is a watched rail", pr <= set(H.EXPECTED),
          str(pr - set(H.EXPECTED)))
    # No pause file -> nothing suppressed, so the skip cannot be a blanket one.
    check("no pause file -> no suppressed rails", H.paused_rail_names(set()) == set())

    print()
    if FAILS:
        print(f"FAIL: {len(FAILS)} check(s) failed: {FAILS}")
        return 1
    print("OK: a paused channel is skipped, and only the paused one")
    return 0


if __name__ == "__main__":
    sys.exit(main())
