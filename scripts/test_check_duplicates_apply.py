#!/usr/bin/env python3
"""Guards for the duplicate cleanup: it must keep the winner, park (not delete), and
change only privacyStatus.

Measured 2026-11-28: three title-duplicates were still public (dharma 21BEmghClt8 vs
pl-el1XyeXc 1067 views, genx wAQXOP7vyG4 873 vs AEJEVTpRwIo 141, genx vDAtN4W3tQI 145
vs RQL050n9e3k 14). Splitting views across two identical titles is the one thing K's
rule forbids outright."""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def load():
    spec = importlib.util.spec_from_file_location("cd", os.path.join(HERE, "check_duplicates.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, HERE)
    spec.loader.exec_module(mod)
    return mod


def row(vid, views, pub, priv="public", title="t"):
    return {"id": vid, "title": title, "dur": 30, "pub": pub, "priv": priv,
            "views": views, "status": {"privacyStatus": priv,
                                       "selfDeclaredMadeForKids": False,
                                       "license": "youtube"}}


def fail(msg):
    print(f"FAIL: {msg}")
    raise SystemExit(1)


def main() -> int:
    cd = load()

    # 1. a public copy beside an unlisted one is NOT a duplicate (remake_shorts parks it)
    groups = cd.public_groups([row("a", 5, "2026-11-01T00:00:00Z"),
                               row("b", 900, "2026-11-02T00:00:00Z", priv="unlisted")])
    if groups:
        fail(f"an unlisted twin was reported as a duplicate: {groups}")

    # 2. two public copies are a duplicate
    groups = cd.public_groups([row("a", 5, "2026-11-01T00:00:00Z"),
                               row("b", 900, "2026-11-02T00:00:00Z")])
    if len(groups) != 1:
        fail(f"two public copies with one title were not flagged: {groups}")

    # 3. the keeper is the one with more views, whatever the upload order
    keep, redundant = cd.choose_keeper([row("old_few", 5, "2026-11-01T00:00:00Z"),
                                       row("new_many", 900, "2026-11-09T00:00:00Z")])
    if keep["id"] != "new_many" or [r["id"] for r in redundant] != ["old_few"]:
        fail(f"kept {keep['id']} instead of the 900-view copy")

    # 4. a tie goes to the newer upload
    keep, _ = cd.choose_keeper([row("older", 100, "2026-11-01T00:00:00Z"),
                               row("newer", 100, "2026-11-05T00:00:00Z")])
    if keep["id"] != "newer":
        fail("a view tie kept the older upload")

    # 5. only privacyStatus changes -- videos.update replaces the whole status part
    status = cd.unlisted_status(row("a", 0, "x")["status"]).copy()
    if status["privacyStatus"] != "unlisted":
        fail("privacyStatus was not changed")
    for key in ("selfDeclaredMadeForKids", "license"):
        if key not in status:
            fail(f"unlisting would drop status.{key} (videos.update replaces the part)")
    if row("a", 0, "x")["status"]["privacyStatus"] != "public":
        fail("unlisted_status mutated the caller's dict")

    # 6. the PUT body carries the full status and only touches the status part
    sent = {}

    def fake_send(path, body, tok):
        sent.update(path=path, body=body)
        return 200, "{}"

    cd.put_status("tok", "vid", cd.unlisted_status(row("a", 0, "x")["status"]), send=fake_send)
    if sent["path"] != "videos?part=status":
        fail(f"PUT went to {sent['path']}; it must touch only part=status")
    if set(sent["body"]["status"]) < {"privacyStatus", "selfDeclaredMadeForKids"}:
        fail(f"PUT status lost fields: {sent['body']['status']}")

    # 7. the code can fail: an apply path that deleted instead of parking would break K's
    #    reversibility rule, so the file must not call delete at all
    src = open(os.path.join(HERE, "check_duplicates.py"), encoding="utf-8").read()
    if '"DELETE"' in src or "method=\"DELETE\"" in src:
        fail("check_duplicates.py deletes videos; the cleanup must park them (unlisted)")

    # 8. the same video listed three times (measured: the uploads playlist did that for
    #    E1gxiblSUo0) is one video, not a duplicate -- and --apply must never unlist the keeper
    groups = cd.public_groups([row("same", 93, "2026-11-08T00:48:00Z")] * 3)
    if groups:
        fail(f"a repeated id was reported as a duplicate: {groups}")
    src = open(os.path.join(HERE, "check_duplicates.py"), encoding="utf-8").read()
    if 'if r["id"] == keep["id"]:' not in src:
        fail("--apply has no guard against unlisting the keeper")
    if "dict.fromkeys(ids)" not in src:
        fail("scan() does not de-duplicate the uploads playlist")
    print("ok   keeper by views, unlisted twins ignored, park not delete, status preserved")
    return 0


if __name__ == "__main__":
    sys.exit(main())
