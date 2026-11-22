"""Guard for K's rule: the STORY of each clip must be new, not just the pictures.

Fails when one narration part airs in two videos, when a channel repeats a title
or a music bed, when a video has nothing stamped, or when the compilation builder
would happily rebuild an already-aired set of parts. Every check is exercised
with a ledger that breaks the rule, so the guard can fail.
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import content_ledger as cl  # noqa: E402

ok = 0


def check(name: str, cond: bool) -> None:
    global ok
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        sys.exit(1)
    ok += 1


def part(pid: str, digest: str) -> dict:
    return {"id": pid, "sha256": digest, "words": 200}


# 1) Two videos sharing a part is a violation.
led = {"version": 1, "videos": {
    "a": {"channel": "dharma", "parts": [part("01.txt", "s1")], "title": "A"},
    "b": {"channel": "dharma", "parts": [part("01.txt", "s1")], "title": "B"},
}}
bad = cl.check(led)
check("shared part rejected", any("already used" in b for b in bad))

# 2) Same title twice on a channel is a violation (a follower sees the same thing).
led = {"version": 1, "videos": {
    "a": {"channel": "dharma", "parts": [part("01.txt", "s1")], "title": "หลับลึก"},
    "b": {"channel": "dharma", "parts": [part("01.txt", "s2")], "title": "หลับลึก "},
}}
check("repeated title rejected", any("title repeated" in b for b in cl.check(led)))

# 3) Same music bed twice on a channel is a violation.
led = {"version": 1, "videos": {
    "a": {"channel": "dharma", "parts": [], "arc": "x", "title": "A",
          "music": {"sha256": "m1"}},
    "b": {"channel": "dharma", "parts": [], "arc": "y", "title": "B",
          "music": {"sha256": "m1"}},
}}
check("repeated music rejected", any("music bed repeated" in b for b in cl.check(led)))

# 4) A video with nothing stamped is a violation.
check("empty stamp rejected", cl.check(
    {"version": 1, "videos": {"a": {"channel": "dharma", "parts": [], "title": "A"}}}) != [])

# 5) Two different parts on two channels pass.
led = {"version": 1, "videos": {
    "a": {"channel": "dharma", "parts": [part("01.txt", "s1")], "title": "A"},
    "b": {"channel": "genx", "parts": [part("01.txt", "s2")], "title": "B"},
}}
check("distinct stories accepted", cl.check(led) == [])

# 6) parts_of + used_parts spot a copied script across two content dirs.
tmp = tempfile.mkdtemp(prefix="cleg_")
for d, extra in (("one", "story one"), ("two", "story one")):
    os.makedirs(os.path.join(tmp, d))
    open(os.path.join(tmp, d, "01.txt"), "w", encoding="utf-8").write(
        f"{extra} " + "คำ " * 60)
led = {"version": 1, "videos": {"a": {"channel": "dharma",
                                      "parts": cl.parts_of(os.path.join(tmp, "one"))}}}
aired = cl.used_parts(led)
copy = cl.parts_of(os.path.join(tmp, "two"))
check("copied script detected", any(p["sha256"] in aired for p in copy))

# 7) The builder refuses a set that already aired (exit 3, before rendering).
proc = subprocess.run(
    [sys.executable, os.path.join(HERE, "build_night.py"),
     "--content", "content/standard/dharma_long_01", "--work", os.path.join(tmp, "w"),
     "--minutes", "1", "--skip-video", "--key", "test_repeat_attempt"],
    cwd=ROOT, capture_output=True, text=True, stdin=subprocess.DEVNULL)
check("builder refuses aired parts", proc.returncode == 3)

# 8) The ledger that ships must be clean, and every unknown must say why.
with open(cl.LEDGER, encoding="utf-8") as fh:
    live = json.load(fh)
check("repo ledger clean", cl.check(live) == [])
check("unverified documented", all(r.get("why") for r in live.get("unverified", {}).values()))

print(f"{ok} checks passed")
