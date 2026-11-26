#!/usr/bin/env python3
"""Every upload leaves a line, and the audit never moves the cap.

The daily cap is counted from content/upload_log.json, which only the Shorts rail
writes. Measured 2026-11-26: a long-form upload left no trace anywhere, so a
channel could pass DAILY_CAP and nobody could prove it afterwards. The audit file
answers "what did this channel upload in the last 24 h" without changing what the
cap refuses -- this test holds both halves of that.

    python3 scripts/test_upload_audit.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

tmp = tempfile.mkdtemp()
audit = os.path.join(tmp, "upload_audit.jsonl")
os.environ["UPLOAD_AUDIT_PATH"] = audit

import publish_youtube as py  # noqa: E402
import publish_batch as pb  # noqa: E402

failures: list[str] = []


def check(ok: bool, what: str) -> None:
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        failures.append(what)


def main() -> int:
    ledger = os.path.join(tmp, "upload_log.json")
    with open(ledger, "w", encoding="utf-8") as fh:
        json.dump({"channels": {"UCM3QO5L_pmj34n1JVlbhh-w": ["2026-11-26T01:05:00+00:00"]}}, fh)
    before = open(ledger, encoding="utf-8").read()

    py.audit_upload("dharma", "7Ev8NLgcIBM", "ธรรมะก่อนนอน 15 นาที", "public")
    py.audit_upload("dharma", "aaaaaaaaaaa", "คลิปที่สอง", "private", kind="short")

    check(os.path.exists(audit), "the audit file is written")
    lines = [json.loads(x) for x in open(audit, encoding="utf-8").read().splitlines() if x]
    check(len(lines) == 2, f"one line per upload (got {len(lines)})")
    check(lines[0]["video_id"] == "7Ev8NLgcIBM", "the video id is recorded")
    check(lines[0]["kind"] == "long" and lines[1]["kind"] == "short", "the kind is recorded")
    check(all(x.get("ts", "").endswith("+00:00") for x in lines), "every line is timestamped UTC")
    pb.audit_upload("dharma", "ccccccccccc", "คลิปยาวจาก manifest", "public")
    lines = [json.loads(x) for x in open(audit, encoding="utf-8").read().splitlines() if x]
    check(lines[-1]["source"] == "publish_batch.py", "the manifest rail writes the same file")
    check(open(ledger, encoding="utf-8").read() == before,
          "the cap ledger is untouched (the audit must not change what the cap refuses)")

    # A broken audit path must not cost an upload: the writer reports and returns.
    blocker = os.path.join(tmp, "blocker")
    open(blocker, "w").close()
    py.AUDIT_PATH = os.path.join(blocker, "audit.jsonl")   # a file used as a directory
    try:
        py.audit_upload("dharma", "bbbbbbbbbbb", "ต้องไม่ล้ม", "public")
        raised = ""
    except OSError as exc:
        raised = str(exc)
    check(not raised, "an unwritable audit path does not raise")
    check(len(open(audit, encoding="utf-8").read().splitlines()) == 3,
          "and it appends nothing behind your back")

    print()
    if failures:
        print(f"FAILED: {len(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
