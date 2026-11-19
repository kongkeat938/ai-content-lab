#!/usr/bin/env python3
"""Which code has Gemini actually approved, and which has not (K, 2026-11-19).

K's rule: *"งานที่ผ่านการตรวจสอบจาก gemini เอามาให้ K ดูทั้งหมด ถ้างานไม่ได้รับการ
ตรวจให้ผ่านจาก gemini และ K ห้ามอัพ"* -- nothing enters main without a recorded
Gemini APPROVE. That rule needs a ledger, or "was this reviewed?" is an opinion.

Two kinds of entry in `docs/reviews/ledger.json`:

  approved  a file Gemini read, with the verdict text on disk as evidence
  baseline  a file that predates the rule. NOT an approval -- visible debt.

The check that makes this a guard rather than a list: every entry stores the
sha256 of the file the reviewer saw. Change one byte of an approved file and it
is stale (FAIL: re-review). Change one byte of a *baseline* file and it is no
longer the file that predated the rule, so it must be reviewed (FAIL). A file in
neither set is invisible, which is the false pass this exists to prevent.

Honest limit: a digest proves the evidence is about *this* content, not that a
human read it. Fabricating a verdict file is possible and visible in the diff --
which is why the evidence file carries the model name and the prompt hash.

    python3 scripts/review_ledger.py --status     # counts + the unreviewed list
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LEDGER = os.path.join(ROOT, "docs", "reviews", "ledger.json")
CODE_GLOBS = ("scripts/*.py", ".github/workflows/*.yml")


def sha256_of(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def rel(path: str) -> str:
    return os.path.relpath(os.path.abspath(path), ROOT).replace(os.sep, "/")


def reviewable(root: str = ROOT) -> list[str]:
    """Every file the rule covers, swept from disk -- never a hardcoded list.

    A hardcoded set is how a new rail goes unwatched (K, 2026-11-11): the guard
    would pass forever while the newest file it was meant to protect was absent.
    """
    found: set[str] = set()
    for pattern in CODE_GLOBS:
        for p in glob.glob(os.path.join(root, pattern)):
            found.add(os.path.relpath(os.path.abspath(p), root).replace(os.sep, "/"))
    return sorted(found)


def load(path: str = LEDGER) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save(ledger: dict, path: str = LEDGER) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(ledger, fh, indent=1, ensure_ascii=False, sort_keys=True)
        fh.write("\n")


VERDICTS = ("APPROVE WITH CHANGES", "APPROVE", "REJECT")
# a decision is often written after its label on the same line ("คำตัดสิน: APPROVE")
LABELS = ("คำตัดสิน", "verdict", "decision")


def verdict_of(evidence_path: str) -> str | None:
    """'APPROVE' / 'APPROVE WITH CHANGES' / 'REJECT', or None if unreadable.

    An unreadable or missing evidence file is None, never "approved": an unknown
    must not read as a pass (the thumbnail `--skip-existing` trap, 2026-11-18).

    The verdict is the decision written on its own line, not any occurrence of the
    word: a real reply can say "pointing at a REJECT file is impossible" while
    approving, and a whole-text search reads that as REJECT (measured 2026-11-19,
    on this project's own evidence). So a line counts only when it *starts* with a
    verdict once markdown decoration and list numbering are stripped, and the last
    such line wins -- a reply that changes its mind ends with the decision.
    """
    try:
        text = open(evidence_path, encoding="utf-8").read()
    except OSError:
        return None
    found = None
    for line in text.splitlines():
        bare = line.strip().lstrip("-*>#0123456789.)( ").replace("*", "").strip()
        low = bare.lower()
        for label in LABELS:
            at = low.rfind(label)
            if at != -1:
                bare = bare[at + len(label):].strip(" :*")
                break
        upper = bare.upper()
        for verdict in VERDICTS:
            if upper.startswith(verdict):
                found = verdict
                break
    return found


def check(ledger: dict | None = None, root: str = ROOT) -> tuple[list[str], dict]:
    """Return (problems, stats). An empty problem list means the rule holds."""
    ledger = load() if ledger is None else ledger
    approved = ledger.get("approved") or {}
    baseline = ledger.get("baseline") or {}
    problems: list[str] = []

    def abs_of(name: str) -> str:
        return os.path.join(root, name)

    on_disk = reviewable(root)
    known = set(approved) | set(baseline)

    for name in on_disk:
        if name not in known:
            problems.append(f"{name}: no review entry -- a new file needs a Gemini "
                            "APPROVE before it enters main")

    for name in sorted(known - set(on_disk)):
        problems.append(f"{name}: in the ledger but no longer on disk -- remove the "
                        "entry or restore the file")

    for name in sorted(set(approved) & set(baseline)):
        problems.append(f"{name}: both approved and baseline -- a file is one or the other")

    for name, entry in sorted(approved.items()):
        if name not in on_disk:
            continue
        want = entry.get("sha256")
        got = sha256_of(abs_of(name))
        if want != got:
            problems.append(f"{name}: changed since it was reviewed "
                            f"({str(want)[:12]} -> {got[:12]}) -- re-review")
        ev = entry.get("evidence") or ""
        if not ev:
            problems.append(f"{name}: approved with no evidence file")
            continue
        verdict = verdict_of(abs_of(ev))
        if verdict is None:
            problems.append(f"{name}: evidence {ev} is missing or has no verdict")
        elif verdict != "APPROVE":
            problems.append(f"{name}: evidence verdict is {verdict!r}, not APPROVE")

    for name, entry in sorted(baseline.items()):
        if name not in on_disk:
            continue
        if entry.get("sha256") != sha256_of(abs_of(name)):
            problems.append(f"{name}: baseline file was edited -- it is no longer the "
                            "file that predated the rule, so it must be reviewed")

    stats = {"reviewable": len(on_disk), "approved": len(set(approved) & set(on_disk)),
             "baseline": len(set(baseline) & set(on_disk))}
    return problems, stats


def record(name: str, evidence: str, root: str = ROOT, commit: str = "") -> tuple[bool, str]:
    """Add one approved entry, refusing unless the evidence really says APPROVE.

    Hand-editing the JSON is how a typo becomes an approval nobody can trace, and
    how an entry gets recorded for a verdict that was never given. The verdict is
    re-read from the evidence file here, so `--record` cannot manufacture a pass.
    """
    target = os.path.join(root, name)
    if not os.path.isfile(target):
        return False, f"{name}: no such file -- nothing to record"
    ev_path = os.path.join(root, evidence)
    verdict = verdict_of(ev_path)
    if verdict != "APPROVE":
        return False, (f"{name}: evidence {evidence} reads {verdict!r}, not APPROVE -- "
                       "ask Gemini again, do not edit the evidence")
    ledger = load(os.path.join(root, "docs", "reviews", "ledger.json"))
    ledger.setdefault("approved", {})[name] = {
        "sha256": sha256_of(target),
        "verdict": "APPROVE",
        "commit": commit,
        "evidence": evidence,
    }
    (ledger.get("baseline") or {}).pop(name, None)
    save(ledger, os.path.join(root, "docs", "reviews", "ledger.json"))
    return True, f"{name}: recorded as approved against {evidence}"


def main() -> int:
    ap = argparse.ArgumentParser(description="Gemini review ledger for code changes")
    ap.add_argument("--status", action="store_true", help="print counts and the unreviewed list")
    ap.add_argument("--record", metavar="FILE", help="record an APPROVE for one file")
    ap.add_argument("--evidence", metavar="PATH", help="the verdict text backing --record")
    ap.add_argument("--commit", default="", help="the commit the approval belongs to")
    args = ap.parse_args()

    if args.record:
        if not args.evidence:
            print("--record needs --evidence (the Gemini reply on disk)")
            return 2
        ok, msg = record(args.record, args.evidence, commit=args.commit)
        print(msg)
        return 0 if ok else 1

    ledger = load()
    problems, stats = check(ledger)
    print(f"reviewable {stats['reviewable']}: approved {stats['approved']}, "
          f"baseline (predates the rule, NOT approved) {stats['baseline']}")
    if args.status:
        debt = sorted(set(ledger.get("baseline") or {}))
        # Folded in CI so a 236-line list does not bury the rest of the log
        # (Gemini, 2026-11-19). The count stays on the summary line above.
        print(f"::group::unreviewed debt ({len(debt)})")
        for name in debt:
            print(f"  {name}")
        print("::endgroup::")
    for p in problems:
        print(f"PROBLEM {p}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
