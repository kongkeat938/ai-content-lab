#!/usr/bin/env python3
"""A draft is a file, never a message.

  * the module has no send path at all (no smtplib, no HTTP client, no POST),
  * every draft is written with status "draft" and sent_at null,
  * work we cannot deliver (animation, avatars) is skipped, not pitched,
  * the price quoted is the price in content/packages.json.
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPT = os.path.join(HERE, "proposal_draft.py")
FAILED = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" ({detail})" if detail else ""))
    if not cond:
        FAILED.append(name)


def main() -> int:
    src = open(SCRIPT, encoding="utf-8").read()
    tree = ast.parse(src)

    print("no send path")
    banned = {"smtplib", "requests", "httpx", "urllib", "http", "socket", "webbrowser", "subprocess"}
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    check("nothing that can send is imported", not (imported & banned), str(sorted(imported & banned)))
    check("no POST/PUT call in the source", not re.search(r"method\s*=\s*['\"](POST|PUT)", src))

    print("drafting")
    tmp = tempfile.mkdtemp()
    store = os.path.join(tmp, "prospects.json")
    items = [
        {"id": "p1", "source": "t", "url": "https://example.invalid/1", "status": "open",
         "title": "Edit my podcast into 10 vertical clips", "text": "9:16 reels weekly",
         "budget_text": "$40", "deadline_text": "5 days left",
         "contact_public": "site message after sign-in (payment verified)"},
        {"id": "p2", "source": "t", "url": "https://example.invalid/2", "status": "open",
         "title": "2D animated explainer with avatar", "text": "animation", "budget_text": "$500",
         "deadline_text": "", "contact_public": ""},
    ]
    with open(store, "w", encoding="utf-8") as fh:
        json.dump({"items": items}, fh)
    out = os.path.join(tmp, "proposals")
    env = {**os.environ, "PROSPECT_STORE": store, "PROPOSAL_DIR": out}
    r = subprocess.run([sys.executable, SCRIPT, "--top", "5"], capture_output=True, text=True,
                       env=env, stdin=subprocess.DEVNULL)
    check("the run succeeds", r.returncode == 0, r.stderr[-200:])
    index = json.load(open(os.path.join(out, "index.json"), encoding="utf-8"))
    drafts = index["drafts"]
    check("one draft for the one real request", len(drafts) == 1, f"{len(drafts)}")
    check("the animation job is skipped",
          any("not our service" in s["reason"] for s in index.get("skipped", [])),
          str(index.get("skipped")))
    d = drafts[0]
    check("status starts at draft", d["status"] == "draft", d["status"])
    check("nothing is marked sent", d["sent_at"] is None, str(d["sent_at"]))
    body = open(os.path.join(ROOT, d["file"]), encoding="utf-8").read()
    check("the draft quotes the buyer's own headline", "Edit my podcast into 10 vertical clips" in body)
    packs = json.load(open(os.path.join(ROOT, "content", "packages.json"), encoding="utf-8"))
    price = next(p["price"] for p in packs["packages"] if p["id"] == d["package"])
    check("the quoted price is the canonical price", f"{price} THB" in body or f"{price} บาท" in body,
          f"pack {d['package']} = {price}")
    check("the draft says the samples are ours, not client work",
          "not client work" in body or "ไม่ใช่งานลูกค้า" in body)

    print("no promise we cannot keep")
    banned = ("ยอดวิว", "ยอดรับชม", "ไวรัล", "viral", "guarantee", "guaranteed", "more views",
              "increase your views", "followers will")
    hits = [b for b in banned if b.lower() in body.lower()]
    check("the draft promises no views or growth", not hits, str(hits))
    check("the first clip comes before payment",
          "ไม่ต้องจ่ายก่อน" in body or "before you pay" in body)

    print("right-sizing")
    sys.path.insert(0, HERE)
    import proposal_draft as pmod
    packs_list = packs["packages"]
    mini = pmod.pick_package(350, packs_list)
    check("a 350 THB budget gets fewer clips, not a discount", mini["id"] == "mini"
          and mini["clips"] == 3 and mini["price"] <= 350, str(mini))
    packed = pmod.pick_package(665, packs_list)
    check("a 665 THB budget buys pack A at list price", packed["id"] == "A"
          and packed["price"] == 490, str(packed))

    print("\nPASS test_proposal_draft" if not FAILED else f"\nFAIL test_proposal_draft: {FAILED}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
