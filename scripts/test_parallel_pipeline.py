#!/usr/bin/env python3
"""The two systems must really run apart, and never hand two clips one picture.

K (2026-11-19): "ถ้าแยกระบบ สร้างภาพกับทำคลิปได้แยกงานทำคู่ขนานเลย". Two claims
that are easy to make and easy to get wrong, so both are measured here:

  1. SEPARATION -- system B builds clips with NO renderer available. The art
     module is removed from import, so if a clip still needs to paint its own
     picture the run fails. A joined pipeline would pass this only by accident.
  2. NO SHARING UNDER PARALLELISM -- 4 clips built at once from a pool of 4 must
     take 4 DIFFERENT pictures. The claim is a ledger write, and a racy ledger
     would hand the same piece to two clips; the check is the set of md5s.

The third check proves the second one can FAIL: the same run with the ledger
disabled must produce duplicates. A guard that cannot fail proves nothing.

    python3 scripts/test_parallel_pipeline.py    # exit 0 = separated + unique
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PP = os.path.join(HERE, "parallel_pipeline.py")

fails = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global fails
    print(f"  {'ok  ' if ok else 'FAIL'} {name}{(' -- ' + detail) if detail else ''}")
    if not ok:
        fails += 1


def make_pool(d: str, n: int) -> list[str]:
    """n real pictures, one per seed -- the pool system A would leave behind."""
    os.makedirs(d, exist_ok=True)
    subprocess.check_call([sys.executable, os.path.join(HERE, "generative_art.py"),
                           "--count", str(n), "--size", "256", "--seed", "9100",
                           "--out-dir", d, "--jobs", "2"],
                          stdout=subprocess.DEVNULL)
    return sorted(os.path.join(d, f) for f in os.listdir(d) if f.endswith(".png"))


def stories(tmp: str, n: int) -> list[str]:
    """n tiny stories -- a real story file, so the renderer takes its normal path."""
    out = []
    for i in range(n):
        p = os.path.join(tmp, f"s{i}.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump({"id": f"p{i}", "genre": "dharma", "mood": "night",
                       "hook": "ลมหายใจเบา ๆ", "lines": ["วางใจลงช้า ๆ"],
                       "cta": "ติดตาม", "rate": "+30%"}, fh, ensure_ascii=False)
        out.append(p)
    return out


def md5s(out_dir: str, ids: list[str]) -> list[str]:
    got = []
    for sid in ids:
        p = os.path.join(out_dir, sid, "art.jpg")
        got.append(hashlib.md5(open(p, "rb").read()).hexdigest() if os.path.exists(p)
                   else "MISSING")
    return got


def _floor_db(path: str) -> float | None:
    """10th-percentile short-term RMS: the floor between sentences."""
    import re
    try:
        r = subprocess.run(
            ["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af",
             "astats=metadata=1:reset=10,ametadata=print:key="
             "lavfi.astats.Overall.RMS_level:file=-", "-f", "null", "-"],
            capture_output=True, text=True)
    except OSError:
        return None
    vals = sorted(float(m) for m in re.findall(r"RMS_level=(-?\d+\.?\d*)",
                                               (r.stdout or "") + (r.stderr or ""))
                  if float(m) > -120)
    return vals[int(len(vals) * 0.10)] if vals else None


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="parpipe_")
    try:
        pool = os.path.join(tmp, "pool")
        pieces = make_pool(pool, 4)
        check("pool built", len(pieces) == 4, f"{len(pieces)} pieces")

        st = stories(tmp, 4)
        ids = [f"p{i}" for i in range(4)]

        print("1) clips build with NO renderer importable (the systems are apart)")
        # Sitecustomize blocks generative_art: a clip that tries to paint its own
        # background now dies instead of quietly joining the two systems again.
        block = os.path.join(tmp, "block")
        os.makedirs(block, exist_ok=True)
        with open(os.path.join(block, "sitecustomize.py"), "w", encoding="utf-8") as fh:
            fh.write(
                "import sys\n"
                "from importlib.abc import MetaPathFinder\n"
                "class _Block(MetaPathFinder):\n"
                "    def find_spec(self, name, path=None, target=None):\n"
                "        if name == 'generative_art':\n"
                "            raise ImportError('renderer blocked: systems must be apart')\n"
                "        return None\n"
                "sys.meta_path.insert(0, _Block())\n")
        env = dict(os.environ, PYTHONPATH=block)
        out1 = os.path.join(tmp, "out_sep")
        ledger1 = os.path.join(tmp, "ledger1.json")
        r = subprocess.run([sys.executable, PP, "clips", "--pool", pool,
                            "--stories", *st, "--out-dir", out1,
                            "--ledger", ledger1, "--jobs", "2",
                            "--receipt", os.path.join(tmp, "r1.json")],
                           env=env, capture_output=True, text=True)
        check("clip side ran with the renderer blocked", r.returncode == 0,
              f"rc={r.returncode} {(r.stderr or '')[-300:]}")
        built = [i for i in ids if os.path.exists(
            os.path.join(out1, i, f"motion_{i}.mp4"))]
        check("all clips built without rendering anything", len(built) == 4,
              f"{len(built)}/4 clips")

        print("2) every clip gets a MUSIC BED, and no two clips share one")
        # K (2026-11-19): the built clips shipped with no music at all -- the rail
        # accepted `--music` but nothing ever passed it. A bed is measurable: a
        # voice-only clip falls to near-silence between sentences, a mixed one
        # keeps a floor under them. Measured on the real build: floor rose 8-22 dB.
        beds = {}
        bedled = os.path.join(tmp, "bed_ledger.json")
        try:
            beds = json.load(open(bedled, encoding="utf-8")).get("beds", {})
        except (OSError, ValueError):
            beds = {}
        check("a bed was claimed for every clip", len(beds) == 4,
              f"{len(beds)}/4 beds: {sorted(beds)}")
        check("no two clips share a bed", len(set(beds.values())) == len(beds),
              f"{len(set(beds.values()))} distinct of {len(beds)}")
        quiet = []
        for i in ids:
            f = os.path.join(out1, i, f"motion_{i}.mp4")
            floor = _floor_db(f)
            quiet.append(floor)
        check("the audio floor sits above silence (a bed is playing)",
              all(q is not None and q > -30 for q in quiet),
              f"p10 RMS per clip: {[round(q,1) if q is not None else None for q in quiet]}")

        print("3) speech is not sped up (K: 'จังหวะพูดเร็วเกินไป')")
        # Measured on the pre-fix build: +15..+25% rate gave 11.8-13.7 chars/s
        # against 8.5 for the un-sped clip. The rail's own default is -25%.
        import make_motion_short as MMS
        check("the rail defaults to a slower rate, not a faster one",
              MMS.RATE.strip().startswith("-"),
              f"RATE={MMS.RATE!r}")
        import glob
        sped = []
        for story in sorted(glob.glob(os.path.join(ROOT, "content", "motion", "*.json"))):
            d = json.load(open(story, encoding="utf-8"))
            if "rate" in d and not str(d["rate"]).strip().startswith("-"):
                sped.append((os.path.basename(story), d["rate"]))
        check("no shipped story overrides the rate with a speed-up",
              not sped, f"positive rates: {sped}")

        print("4) 4 clips in parallel from a 4-piece pool take 4 DIFFERENT pictures")
        got = md5s(out1, ids)
        check("no picture shared", len(set(got)) == 4,
              f"{len(set(got))} distinct of 4: {[g[:6] for g in got]}")

        print("5) the uniqueness check can FAIL (lock removed -> real collisions)")
        # A guard that cannot fail proves nothing. 4 claimers race over a 2-piece
        # pool: with the lock at most 2 get a piece and none share; without it they
        # all read the same empty `used` map and take the same piece. `_write` is
        # slowed in the unlocked case so the read-then-write window is wide enough
        # to be observed instead of raced by luck -- a flaky demo would be as
        # useless as no demo.
        def race(use_lock: bool, tag: str) -> tuple[int, int]:
            worker = os.path.join(tmp, f"race_{tag}.py")
            with open(worker, "w", encoding="utf-8") as fh:
                fh.write(
                    "import os, sys, time\n"
                    f"sys.path.insert(0, {HERE!r})\n"
                    "import parallel_pipeline as PP\n"
                    + ("" if use_lock else
                       # The lock now lives in make_short (one source, shared with
                       # library_art), so disable it THERE -- patching PP._lock
                       # would no longer reach the code under test.
                       "import make_short as MS\n"
                       "MS._lock = lambda fh: None\n"
                       "MS._unlock = lambda fh: None\n"
                       "real_write = PP._write\n"
                       "PP._write = lambda p, o: (time.sleep(0.6), real_write(p, o))\n")
                    + "pool, ledger, out, sid = sys.argv[1:5]\n"
                    "d = os.path.join(out, sid)\n"
                    "os.makedirs(d, exist_ok=True)\n"
                    "PP._claim(pool, sid, d, '', ledger)\n")
            small = os.path.join(tmp, f"pool_{tag}")
            make_pool(small, 2)
            out2 = os.path.join(tmp, f"out_{tag}")
            ledger2 = os.path.join(tmp, f"ledger_{tag}.json")
            kids = [subprocess.Popen([sys.executable, worker, small, ledger2,
                                      out2, f"p{i}"]) for i in range(4)]
            for k in kids:
                k.wait()
            got = [m for m in md5s(out2, [f"p{i}" for i in range(4)])
                   if m != "MISSING"]
            return len(got), len(set(got))

        claimed, distinct_locked = race(True, "locked")
        check("with the lock, 4 claimers over 2 pieces share nothing",
              claimed - distinct_locked == 0,
              f"{claimed} claimed, {distinct_locked} distinct, "
              f"{claimed - distinct_locked} shared")
        claimed2, distinct_free = race(False, "free")
        check("without the lock the pictures DO collide",
              claimed2 - distinct_free > 0,
              f"{claimed2} claimed, {distinct_free} distinct, "
              f"{claimed2 - distinct_free} shared "
              f"(a check that cannot fail would report 0 shared)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if fails:
        print(f"FAILED {fails} check(s)")
        return 1
    print("PASS: the two systems run apart, and parallel clips never share a picture")
    return 0


if __name__ == "__main__":
    sys.exit(main())
