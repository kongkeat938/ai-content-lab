#!/usr/bin/env python3
"""Quality gate for a finished episode — run it before claiming "done".

Every check prints a *measured* value and a verdict, so the result is evidence,
not an assurance. Fails loudly (exit 1) when a hard requirement is broken.

    python3 work/research/quality_gate.py episodes/ep02_manthana_phatha
    python3 work/research/quality_gate.py episodes/ep02_manthana_phatha --channel ch2
    python3 work/research/quality_gate.py episodes/ep02_manthana_phatha --json out.json

This lives in `work/research/` on purpose: `scripts/` is the pipeline owner's
directory, and a checker that any account can run belongs outside it.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

# Hard requirements from docs/GOAL.md, per channel. Length is a *target*, so it
# is reported as a WARN unless --strict-length is given.
PROFILES = {
    "ch1": {"min_min": 8, "max_min": 15, "label": "ปรัชญา"},
    "ch2": {"min_min": 10, "max_min": 22, "label": "ธรรมะก่อนนอน"},
    "ch4": {"min_min": 12, "max_min": 25, "label": "เรื่องเล่า/การ์ตูน"},
}
LUFS_TARGET, LUFS_TOL = -14.0, 1.0        # -15 .. -13
TRUE_PEAK_MAX = -3.0                       # at or below -3 dBFS
MAX_TITLE = 100
MAX_LINE_CHARS = 90

ARABIC = re.compile(r"[0-9]")
TAG = re.compile(r"^\[[^\]]+\]\s*")


class Gate:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, bool, str]] = []

    def add(self, level: str, name: str, ok: bool, detail: str) -> None:
        self.rows.append((level, name, ok, detail))

    def fail(self, name: str, ok: bool, detail: str) -> None:
        self.add("FAIL", name, ok, detail)

    def warn(self, name: str, ok: bool, detail: str) -> None:
        self.add("WARN", name, ok, detail)

    def info(self, name: str, detail: str) -> None:
        self.add("INFO", name, True, detail)

    @property
    def hard_failed(self) -> bool:
        return any(lv == "FAIL" and not ok for lv, _, ok, _ in self.rows)


def load(path: str, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def script_lines(path: str) -> list[str]:
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = TAG.sub("", raw.strip())
            if line:
                out.append(line)
    return out


def normalize(s: str) -> str:
    return re.sub(r"\s+", "", s)


def timing_coverage(timing: dict, lines: list[str]) -> tuple[int, int]:
    """How many script lines appear in the synthesised boundary text."""
    words = (timing or {}).get("words", [])
    hay = normalize("".join(w.get("text", "") for w in words))
    matched = sum(1 for ln in lines if normalize(ln) and normalize(ln) in hay)
    return matched, len(lines)


def probe_video(path: str) -> dict | None:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=pix_fmt,color_range,width,height",
             "-of", "json", path],
            capture_output=True, text=True, timeout=30)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    try:
        return json.loads(out.stdout)["streams"][0]
    except (KeyError, IndexError, json.JSONDecodeError):
        return None


def check(ep_dir: str, profile: dict, strict_length: bool) -> Gate:
    g = Gate()
    info = load(os.path.join(ep_dir, "audio_info.json"), {}) or {}
    timing = load(os.path.join(ep_dir, "timing.json"), {}) or {}
    meta = load(os.path.join(ep_dir, "meta.json"), {}) or {}
    scenes = load(os.path.join(ep_dir, "scenes.json"), {}) or {}
    lines = script_lines(os.path.join(ep_dir, "narration_th.txt"))

    # --- narration ---
    g.info("narration.lines", f"{len(lines)} non-blank lines")
    g.info("narration.chars", f"{info.get('chars', '?')} chars")
    bad_digits = [ln for ln in lines if ARABIC.search(ln)]
    g.fail("narration.no-digits", not bad_digits,
           f"{len(bad_digits)} line(s) contain Arabic digits "
           f"(e.g. {bad_digits[0][:40]!r})" if bad_digits else "no digits")
    long_lines = [ln for ln in lines if len(ln) > MAX_LINE_CHARS]
    g.warn("narration.line-length", not long_lines,
           f"{len(long_lines)} line(s) > {MAX_LINE_CHARS} chars "
           f"(longest {max((len(x) for x in lines), default=0)})")

    # --- timing ---
    matched, total = timing_coverage(timing, lines)
    g.fail("timing.all-lines-matched", total > 0 and matched == total,
           f"{matched}/{total} lines matched a SentenceBoundary")

    # --- audio ---
    dur = float(info.get("duration_sec") or timing.get("duration_sec") or 0)
    minutes = dur / 60
    length_ok = profile["min_min"] <= minutes <= profile["max_min"]
    detail = (f"{minutes:.1f} min (target {profile['min_min']}-{profile['max_min']} "
              f"for {profile['label']})")
    (g.fail if strict_length else g.warn)("audio.length", length_ok, detail)
    try:
        lufs = float(info.get("lufs"))
        g.fail("audio.lufs", abs(lufs - LUFS_TARGET) <= LUFS_TOL,
               f"{lufs} LUFS (target {LUFS_TARGET}±{LUFS_TOL})")
    except (TypeError, ValueError):
        g.fail("audio.lufs", False, "lufs missing from audio_info.json")
    try:
        tp = float(info.get("true_peak_dbfs"))
        g.fail("audio.true-peak", tp <= TRUE_PEAK_MAX,
               f"{tp} dBFS (max {TRUE_PEAK_MAX})")
    except (TypeError, ValueError):
        g.fail("audio.true-peak", False, "true_peak_dbfs missing")

    # --- poster cards ---
    sc = scenes.get("scenes", [])
    g.info("scenes.cards", f"{len(sc)} cards")
    missing = [s.get("image") for s in sc
               if s.get("image") and not os.path.exists(s["image"])]
    g.fail("scenes.images-exist", not missing,
           f"{len(missing)} missing (e.g. {missing[0]})" if missing else "all present")
    over = [s.get("title") for s in sc if len(s.get("title") or "") > 40]
    g.warn("scenes.title-fits", not over, f"{len(over)} card title(s) > 40 chars")

    # --- packaging (what the strategy says drives discovery) ---
    title = meta.get("title") or scenes.get("title") or ""
    g.fail("packaging.title", 0 < len(title) <= MAX_TITLE,
           f"{len(title)} chars: {title[:60]!r}")
    hook = meta.get("hook") or ""
    g.warn("packaging.hook", len(hook) >= 20,
           f"{len(hook)} chars" + ("" if hook else " (missing)"))
    g.warn("packaging.hook-first-line",
           bool(lines) and len(lines[0]) <= 60,
           f"first narration line {len(lines[0]) if lines else 0} chars")
    tags = meta.get("tags") or []
    g.warn("packaging.tags", len(tags) >= 5, f"{len(tags)} tags")
    g.warn("packaging.description", len(meta.get("description") or "") >= 80,
           f"{len(meta.get('description') or '')} chars")
    src = meta.get("source") or {}
    g.fail("packaging.source", bool(src.get("work") and src.get("licence")),
           f"work={src.get('work')!r} licence={src.get('licence')!r}")
    g.fail("packaging.attribution", bool(meta.get("attribution")),
           "attribution present" if meta.get("attribution") else "attribution missing")

    # --- video (optional: media is gitignored, may not be built here) ---
    video = os.path.join(ep_dir, "video.mp4")
    if os.path.exists(video):
        v = probe_video(video)
        if v is None:
            g.warn("video.probe", False, "ffprobe unavailable or failed")
        else:
            g.fail("video.pix-fmt", v.get("pix_fmt") == "yuv420p",
                   f"pix_fmt={v.get('pix_fmt')}")
            g.fail("video.color-range", v.get("color_range") == "tv",
                   f"color_range={v.get('color_range')}")
            g.info("video.size", f"{v.get('width')}x{v.get('height')}")
    else:
        g.warn("video.present", False, "video.mp4 not built in this checkout")
    return g


def render(g: Gate) -> None:
    icon = {"FAIL": "✗", "WARN": "!", "INFO": "·"}
    for level, name, ok, detail in g.rows:
        mark = "✓" if ok else icon[level]
        print(f"  [{mark}] {name:28} {detail}")
    fails = sum(1 for lv, _, ok, _ in g.rows if lv == "FAIL" and not ok)
    warns = sum(1 for lv, _, ok, _ in g.rows if lv == "WARN" and not ok)
    print(f"\n  {fails} hard failure(s), {warns} warning(s)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("episode")
    ap.add_argument("--channel", default="ch2", choices=sorted(PROFILES))
    ap.add_argument("--strict-length", action="store_true")
    ap.add_argument("--json", metavar="PATH")
    args = ap.parse_args()

    if not os.path.isdir(args.episode):
        sys.exit(f"not a directory: {args.episode}")
    print(f"quality gate: {args.episode}  (channel {args.channel})")
    g = check(args.episode, PROFILES[args.channel], args.strict_length)
    render(g)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"episode": args.episode, "channel": args.channel,
                       "pass": not g.hard_failed,
                       "checks": [{"level": lv, "name": n, "ok": ok, "detail": d}
                                  for lv, n, ok, d in g.rows]},
                      fh, ensure_ascii=False, indent=1)
    return 1 if g.hard_failed else 0


if __name__ == "__main__":
    sys.exit(main())
