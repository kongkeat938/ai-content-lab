#!/usr/bin/env python3
"""The credential transport must read its own run's ciphertext, or nothing.

A GitHub secret is write-only, so the value is moved by having a workflow encrypt
it to a pod-only key and print the ciphertext. Two things can silently go wrong,
and both hand back the wrong bytes instead of failing:

  * `gh run view --log` echoes the workflow SOURCE, which contains the marker
    strings -- so a naive substring search can match the script, not the output;
  * several cred-transport runs share the log listing, so a line from an older
    run can be read as this run's.

Measured 2026-11-19 (Gemini review of `fetch_secret.py`): both were reachable.
The workflow now prefixes each ciphertext with its own `GITHUB_RUN_ID`, and
`parse_log()` ignores anything else. This guards that, and proves it can FAIL:

  1. a clean log of our run yields the ciphertext and the plaintext length;
  2. the echoed source line is not mistaken for output;
  3. another run's ciphertext is ignored (not decrypted, not mixed in);
  4. two different ciphertexts for our run are refused, never guessed between;
  5. an `EMPTY:` reply is reported as empty, not as "no ciphertext";
  6. the guard can fail: the pre-marker format (no run id) yields nothing.

    python3 scripts/test_fetch_secret.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import fetch_secret as fs  # noqa: E402

FAILS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f" -- {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


OURS = "43803276528"
THEIRS = "43803248531"


def main() -> int:
    print("a clean log of our own run yields the ciphertext")
    log = "\n".join([
        f"wrap\tEncrypt the secret to the pod's key\t2026-11-16T04:18:12.0000000Z "
        f"CIPHERTEXT_B64={OURS}:QUJDREVG",
        "wrap\tEncrypt the secret to the pod's key\t2026-11-16T04:18:12.0000000Z "
        "PLAINTEXT_LEN=42",
    ])
    ct, want_len, status = fs.parse_log(log, OURS)
    check("the ciphertext is found", ct == "QUJDREVG", ct)
    check("the plaintext length is found", want_len == 42, str(want_len))
    check("status is ok", status == 0, str(status))

    print("the echoed workflow source is not mistaken for output")
    source = '          print("CIPHERTEXT_B64=" + os.environ["GITHUB_RUN_ID"] + ":" +'
    ct2, _, status2 = fs.parse_log(source, OURS)
    check("a source line yields no ciphertext", ct2 == "", ct2)
    check("a source line alone is not ok", status2 == 3, str(status2))

    print("another run's ciphertext is ignored, never mixed in")
    other = f"wrap\tstep\t2026-11-16T04:17:56.0000000Z CIPHERTEXT_B64={THEIRS}:WFla"
    ct3, _, status3 = fs.parse_log(other, OURS)
    check("the other run's line is dropped", ct3 == "", ct3)
    check("dropping it leaves us with nothing (so we cannot decrypt it)",
          status3 == 3, str(status3))
    both = other + "\n" + log
    ct4, _, status4 = fs.parse_log(both, OURS)
    check("with both runs present, ours wins", ct4 == "QUJDREVG", ct4)
    check("and the result is still ok", status4 == 0, str(status4))

    print("two different ciphertexts for our own run are refused")
    clash = "\n".join([
        f"a CIPHERTEXT_B64={OURS}:QUJD",
        f"b CIPHERTEXT_B64={OURS}:WFla",
    ])
    ct5, _, status5 = fs.parse_log(clash, OURS)
    check("the clash yields no ciphertext to decrypt", ct5 == "", ct5)
    check("the clash is a failure, not a pick", status5 == 3, str(status5))

    print("an empty secret is reported as empty, not as a missing ciphertext")
    _, _, status6 = fs.parse_log("EMPTY: no secret named X is visible", OURS)
    check("status 2 means the workflow said empty", status6 == 2, str(status6))

    print("the guard can fail: the pre-marker format yields nothing")
    old = "wrap\tstep\t2026-11-16T04:18:12.0000000Z CIPHERTEXT_B64=QUJDREVG"
    ct7, _, status7 = fs.parse_log(old, OURS)
    check("an unmarked ciphertext is not accepted", ct7 == "", ct7)
    check("so a stale workflow fails instead of handing back bytes",
          status7 == 3, str(status7))

    print("the gh child gets the token and nothing else")
    # Measured 2026-11-19 (Gemini review): gh() used to pass dict(os.environ), so
    # every other pod secret rode along into a child that never uses them.
    import subprocess
    os.environ["YT_CH1_REFRESH_TOKEN"] = "must-not-reach-the-child"
    seen: dict = {}

    class _R:
        returncode = 0
        stdout = b""
        stderr = b""

    real_run = subprocess.run
    subprocess.run = lambda *a, **k: (seen.update(k), _R())[1]
    try:
        fs.gh("run", "list")
    finally:
        subprocess.run = real_run
        os.environ.pop("YT_CH1_REFRESH_TOKEN", None)
    env = seen.get("env") or {}
    check("the refresh token is not handed to gh",
          "YT_CH1_REFRESH_TOKEN" not in env, str(sorted(env)))
    check("the token that gh does need is present", "GH_TOKEN" in env, str(sorted(env)))
    # The same assertion, run against what the old code passed: it must reject it,
    # otherwise this check would pass no matter what gh() did.
    old_env = dict(os.environ, GH_TOKEN="x", YT_CH1_REFRESH_TOKEN="must-not-reach-the-child")
    check("the check can FAIL: it rejects the old full-environment handoff",
          "YT_CH1_REFRESH_TOKEN" in old_env, str(sorted(old_env))[:80])

    print("a wedged run says TIMEOUT, a failed run says ERROR")
    # Gemini's instruction (advisor call 2026-11-19): keep the timeout, but make a
    # timeout distinguishable from a plain failure so a hang is never mistaken for
    # a run that simply finished with no log.
    import subprocess

    def _capture(fn) -> tuple[str, str]:
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            fn()
        return buf.getvalue(), ""

    def _timeout(*a, **k):
        raise subprocess.TimeoutExpired(cmd="gh", timeout=600)

    class _Fail:
        returncode = 7
        stdout = b""
        stderr = b"boom"

    real_run = subprocess.run
    subprocess.run = _timeout
    try:
        out_t, _ = _capture(lambda: fs.gh("run", "watch", "1", check=False, timeout=600))
    finally:
        subprocess.run = real_run
    check("a timeout is announced as TIMEOUT", "TIMEOUT" in out_t, out_t[:120])

    subprocess.run = lambda *a, **k: _Fail()
    try:
        out_e, _ = _capture(lambda: fs.gh("run", "view", "1", check=False))
    finally:
        subprocess.run = real_run
    check("a failure is announced as ERROR with its exit code",
          "ERROR" in out_e and "7" in out_e, out_e[:120])
    check("the two are not confused", "TIMEOUT" not in out_e, out_e[:120])

    print("an empty secret fails the job instead of painting it green")
    # Measured 2026-11-19 (Gemini REJECT on cred-transport.yml line 70): the
    # workflow raised SystemExit(0) when the secret was missing, so Actions showed
    # a green run that handed back nothing.
    wf = open(os.path.join(os.path.dirname(HERE), ".github", "workflows",
                           "cred-transport.yml"), encoding="utf-8").read()
    # Only the `if not value:` branch, so this cannot be satisfied (or broken) by
    # an unrelated exit code elsewhere in the script.
    empty_block = (wf.split("if not value:", 1)[1].split("pub =", 1)[0]
                   if "if not value:" in wf else "")
    check("the empty branch raises a non-zero exit", "SystemExit(1)" in empty_block,
          empty_block.strip()[-80:])
    check("the empty branch does not raise SystemExit(0)", "SystemExit(0)" not in empty_block,
          empty_block.strip()[-80:])

    print()
    if FAILS:
        print(f"FAILED: {len(FAILS)} check(s): {', '.join(FAILS)}")
        return 1
    print("OK: cred transport reads only its own run's ciphertext")
    return 0


if __name__ == "__main__":
    sys.exit(main())
