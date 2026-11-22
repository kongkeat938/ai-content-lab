"""Guard for the owner's rule: no MV may reuse another MV's image, and every
image must be stamped with the MV that owns it.

The checks below must be able to FAIL -- a ledger with a duplicate sha, a
missing stamp or a missing file is rejected, and `generate_images` refuses to
ship a picture that is already claimed.
"""
import hashlib
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import make_mv  # noqa: E402

ok = 0


def check(name: str, cond: bool) -> None:
    global ok
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        sys.exit(1)
    ok += 1


def rec(images, duration=60.0):
    return {"images": images, "video": {"duration": duration}, "music": {}, "published": {}}


def img(path, digest, **extra):
    d = {"path": path, "sha256": digest, "prompt": "p", "seed": 1}
    d.update(extra)
    return d


# 1) A clean ledger passes.
tmp = tempfile.mkdtemp(prefix="mvtest_")
p1 = os.path.join(tmp, "a.jpg")
open(p1, "wb").write(b"a")
clean = {"version": 1, "mvs": {
    "mv_a": rec([img(os.path.relpath(p1, ROOT), "sha-a")]),
    "mv_b": rec([img(os.path.relpath(p1, ROOT), "sha-b")]),
}}
check("clean ledger accepted", make_mv.check_ledger(clean) == [])

# 2) The same image in two MVs is a violation.
dup = {"version": 1, "mvs": {
    "mv_a": rec([img(os.path.relpath(p1, ROOT), "sha-same")]),
    "mv_b": rec([img(os.path.relpath(p1, ROOT), "sha-same")]),
}}
bad = make_mv.check_ledger(dup)
check("duplicate image rejected", any("reused" in b for b in bad))

# 3) An image without its stamps is a violation.
nostamp = {"version": 1, "mvs": {"mv_a": rec([{"path": os.path.relpath(p1, ROOT)}])}}
check("missing stamp rejected", make_mv.check_ledger(nostamp) != [])

# 4) A stamped image that is not on disk is a violation when its folder exists.
gone = {"version": 1, "mvs": {"mv_a": rec([img(os.path.relpath(os.path.join(tmp, "absent.jpg"), ROOT), "sha-x")])}}
check("missing file rejected", any("missing" in b for b in make_mv.check_ledger(gone, require_files=True)))

# 5) An MV with no verified video is a violation.
noverify = {"version": 1, "mvs": {"mv_a": rec([img(os.path.relpath(p1, ROOT), "sha-a")], 0)}}
check("unverified video rejected", make_mv.check_ledger(noverify) != [])

# 6) generate_images refuses a picture another MV already owns.
fake_bytes = b"\xff\xd8" + b"x" * 6000
digest = hashlib.sha256(fake_bytes).hexdigest()
real = make_mv.gen_cover_image.from_pollinations
make_mv.gen_cover_image.from_pollinations = lambda *a, **k: fake_bytes
try:
    claimed = {"version": 1, "mvs": {"mv_old": rec([img("x", digest)])}}
    try:
        make_mv.generate_images("mv_new", "dharma", 1, os.path.join(tmp, "new"), claimed)
        raised = False
    except SystemExit:
        raised = True
    check("claimed image refuses to be reused", raised)

    # 7) With the ledger empty the same call stamps a fresh image.
    out_dir = os.path.join(tmp, "fresh")
    got = make_mv.generate_images("mv_new2", "dharma", 1, out_dir, {"version": 1, "mvs": {}})
    check("fresh image stamped", got[0]["sha256"] == digest and os.path.exists(
        os.path.join(out_dir, "img01.jpg")))
finally:
    make_mv.gen_cover_image.from_pollinations = real

# 8) The ledger that ships in the repo must obey the rule.
if os.path.exists(make_mv.LEDGER):
    with open(make_mv.LEDGER, encoding="utf-8") as fh:
        live = json.load(fh)
    check("repo ledger clean", make_mv.check_ledger(live) == [])

print(f"{ok} checks passed")
