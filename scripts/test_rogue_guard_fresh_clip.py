"""Guard: the rogue rail must never hide one of our own fresh clips.

Measured 2026-11-22: rogue-guard paused six clips we had just published, because
a pod build records its upload locally and those commits were not pushed (push
403), so the runner still read "unrecorded" -- the same shape as the rogue
stream.

Measured 2026-11-24: the escape hatch failed again. The RSS watcher also derives
its verdict from that same stale manifest (it names every fresh unrecorded upload
`ROGUE <ch> <id>`), so "confirmed by the RSS watcher" was not independent
evidence, and a 7-minute-old Short plus a 2.5 h-old dharma long-form were paused.
This test pins the rule that survives both: a clip under the age floor is never
paused, whoever names it; only a clip unrecorded for the whole floor is.
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import audit_channels as ac  # noqa: E402

ok = 0


def check(name, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        sys.exit(1)
    ok += 1


def defect(vid, age, title="clip"):
    return (f"video {vid} is UNRECORDED and published {age:.1f}d ago "
            f"-- LIVE rogue upload outside the rails: {title}")


FRESH = defect("HkFULkG2sRk", 0.04)
OLD = defect("9JbwOneU_7A", 3.0)

# 1) A fresh unrecorded clip with no independent signal stays live.
check("fresh clip kept", ac._live_rogue_ids([FRESH], confirmed=set()) == [])

# 2) The RSS watcher naming a fresh clip does NOT make it hideable: both sources
#    read the same unpushed manifest.
check("confirmed fresh clip still kept",
      ac._live_rogue_ids([FRESH], confirmed={"HkFULkG2sRk"}) == [])

# 3) A clip that stayed unrecorded for a day is still hidden, named or not.
check("stale clip hidden", [v for v, _ in ac._live_rogue_ids([OLD])] == ["9JbwOneU_7A"])
check("confirmed stale clip hidden",
      [v for v, _ in ac._live_rogue_ids([OLD], confirmed={"9JbwOneU_7A"})]
      == ["9JbwOneU_7A"])

# 4) The RSS log parses to ids.
tmp = tempfile.mkdtemp(prefix="rogue_")
log = os.path.join(tmp, "rogue_rss.txt")
open(log, "w", encoding="utf-8").write(
    "ROGUE genx VjmZyCpqyPk (0.11d) ปรัชญาชีวิต\nno live rogue on dharma\n")
check("rss log parsed", ac._confirmed_rogues(log) == {"VjmZyCpqyPk"})
check("missing rss log is empty", ac._confirmed_rogues(os.path.join(tmp, "nope")) == set())

# 5) End to end: hide_live_rogue touches nothing for a fresh clip.
calls = []


class _Req:
    def __init__(self, body):
        self.body = body

    def execute(self):
        calls.append(self.body)
        return {"id": self.body["id"]}


class _Videos:
    def update(self, part=None, body=None):
        assert part == "status"
        return _Req(body)


class _YT:
    def videos(self):
        return _Videos()


ac.client_for = lambda slug, ch_id: _YT()
ledger = os.path.join(tmp, "hidden.json")
report = {"dharma": {"channel": {"id": "UC1"}, "defects": [FRESH]}}
ac.hide_live_rogue(report, confirmed=set(), ledger_path=ledger)
check("nothing paused for a fresh clip", calls == [] and not os.path.exists(ledger))

ac.hide_live_rogue(report, confirmed={"HkFULkG2sRk"}, ledger_path=ledger)
check("still nothing paused when the RSS watcher names a fresh clip",
      calls == [] and not os.path.exists(ledger))

old_report = {"dharma": {"channel": {"id": "UC1"}, "defects": [OLD]}}
ac.hide_live_rogue(old_report, confirmed={"9JbwOneU_7A"}, ledger_path=ledger)
check("a clip unrecorded for a full day is paused (reversibly)",
      len(calls) == 1
      and calls[0]["status"]["privacyStatus"] == "private"
      and os.path.exists(ledger))

print(f"{ok} checks passed")
