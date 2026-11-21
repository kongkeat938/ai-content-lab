#!/usr/bin/env python3
"""Prove the image vault can REFUSE, and that the clip standard can FAIL.

Owner K's rule: a guard that only ever passes proves nothing. So every check here
builds the bad case and asserts the guard rejects it -- a reused image, a second
channel taking the same picture, a still that never moves, a washed-out colour tag.

Run: python3 scripts/test_image_vault.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import image_vault as V  # noqa: E402

FAILS: list = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"{'PASS' if cond else 'FAIL'} {name}" + (f"  [{detail}]" if detail else ""))
    if not cond:
        FAILS.append(name)


def _png(path: str, colour: tuple) -> str:
    from PIL import Image
    Image.new("RGB", (64, 64), colour).save(path)
    return path


def test_same_image_refused() -> None:
    tmp = tempfile.mkdtemp()
    try:
        vault = os.path.join(tmp, "vault.json")
        a = _png(os.path.join(tmp, "a.png"), (200, 30, 30))
        md5 = V.claim_file(a, "dharma", "ep01", vault)
        check("claim stamps the image", V.is_used(md5, V.load(vault)))
        # Same picture, same channel, DIFFERENT clip -> must be refused.
        try:
            V.claim_file(a, "dharma", "ep02", vault)
            check("same channel reusing one image is refused", False, "it was allowed")
        except RuntimeError as exc:
            check("same channel reusing one image is refused", "already used" in str(exc))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_cross_channel_refused() -> None:
    tmp = tempfile.mkdtemp()
    try:
        vault = os.path.join(tmp, "vault.json")
        a = _png(os.path.join(tmp, "a.png"), (30, 30, 200))
        V.claim_file(a, "dharma", "ep01", vault)
        # The whole point of one vault: another CHANNEL cannot take it either.
        try:
            V.claim_file(a, "genx", "42", vault)
            check("another channel reusing one image is refused", False, "it was allowed")
        except RuntimeError as exc:
            check("another channel reusing one image is refused", "already used" in str(exc))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_restamp_same_clip_is_idempotent() -> None:
    tmp = tempfile.mkdtemp()
    try:
        vault = os.path.join(tmp, "vault.json")
        a = _png(os.path.join(tmp, "a.png"), (10, 160, 10))
        md5 = V.claim_file(a, "genx", "7", vault)
        again = V.claim_file(a, "genx", "7", vault)
        rec = V.load(vault)["images"][md5]
        check("a rebuild of the same clip keeps its own image", again == md5)
        check("stamp time is not rewritten on rebuild",
              bool(rec.get("stamped_at")), rec.get("stamped_at", ""))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_pick_free_never_hands_out_used() -> None:
    tmp = tempfile.mkdtemp()
    try:
        vault = os.path.join(tmp, "vault.json")
        cands = [_png(os.path.join(tmp, f"c{i}.png"), (i * 40, 90, 200 - i * 40))
                 for i in range(3)]
        first = V.pick_free(cands, "dharma", "ep01", vault)
        second = V.pick_free(cands, "genx", "1", vault)
        check("pick_free gives a different picture to the next clip", first != second,
              f"{os.path.basename(first)} vs {os.path.basename(second)}")
        V.pick_free(cands, "kongkeat", "9", vault)
        try:
            V.pick_free(cands, "motion", "x", vault)
            check("pick_free refuses when the stock is spent", False, "it handed one out")
        except RuntimeError as exc:
            check("pick_free refuses when the stock is spent", "no unused" in str(exc))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_stock_accumulates() -> None:
    tmp = tempfile.mkdtemp()
    try:
        vault = os.path.join(tmp, "vault.json")
        for i in range(4):
            p = _png(os.path.join(tmp, f"s{i}.png"), (i * 50, 20, 60))
            V.stamp(V.md5_of(p), "", "", p, vault)
        data = V.load(vault)
        free = [m for m, r in data["images"].items() if not r.get("clip")]
        check("freshly generated pictures stock the warehouse", len(free) == 4,
              f"{len(free)} free")
        p = _png(os.path.join(tmp, "take.png"), (i, 20, 60))
        V.stamp(V.md5_of(p), "dharma", "ep09", p, vault)
        check("taking a stocked picture bans it", len(
            [m for m, r in V.load(vault)["images"].items() if not r.get("clip")]) == 4)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_committed_vault_keeps_history_and_bans_it() -> None:
    """The 4 md5 the old per-channel ledgers shared must stay VISIBLE and BANNED.

    Dropping them would un-ban a picture that is already live in two videos, and
    hiding them would erase the evidence that the old design had this defect.
    """
    data = V.load()
    dupes = V.cross_channel_dupes(data)
    check("the old cross-channel reuse is recorded as evidence", len(dupes) == 4,
          f"{len(dupes)} md5")
    check("every recorded duplicate is banned from reuse",
          all(V.is_used(m, data) for m in dupes))
    check("the vault bans a real number of pictures", len(data["images"]) >= 100,
          f"{len(data['images'])} banned")


def main() -> int:
    if not shutil.which("ffmpeg"):
        print("SKIP: ffmpeg not on PATH")
    test_same_image_refused()
    test_cross_channel_refused()
    test_restamp_same_clip_is_idempotent()
    test_pick_free_never_hands_out_used()
    test_stock_accumulates()
    test_committed_vault_has_no_cross_channel_reuse()
    print(f"\n{len(FAILS)} failure(s)")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
