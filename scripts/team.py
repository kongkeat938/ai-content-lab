#!/usr/bin/env python3
"""ak's own team -- named workers that DO the job, not just advise.

K (2026-11-13): "Ak ไปสร้างทีมงานของตัวเองใหม่ ... เอาแบบที่คัดแล้วช่วยงาน ak ได้จริง ๆ"
and "เอามาช่วยทำงานเลย ... ไม่ต้องเอามาปรึกษาอย่างเดียว".

So this is not the decision panel (`advise.py`) -- it is a roster of **workers**. ak hands a
worker a task and gets back an artifact it can use (a topic list, a Thai script, a title set,
a grade, a diagnosis). Each worker is a role prompt bound to an advisor that was measured
reachable from the pod (`advise.py` registry): the fast Google models answer in seconds; the
`engineer` worker runs on OpenHands Cloud and can actually read/run code.

    python3 scripts/team.py list
    python3 scripts/team.py run researcher "หา 3 หัวข้อเรื่องสั้นไทยสำหรับ dharma"
    python3 scripts/team.py run scriptwriter "เรื่อง: พ่อกับลูก ... เขียนสคริปต์ 20 บรรทัด"
    python3 scripts/team.py run engineer --deep "ทำไม rail X ไม่ยิง"   # runs on a Cloud worker
    python3 scripts/team.py all "ตรวจงานชุดนี้"                        # several workers, side by side

A role not in the roster fails loudly (the `.get()+continue` trap that silently emptied the
light panel once). Guards live in `scripts/test_team.py`.
"""
from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import advise  # noqa: E402

# role -> (advisor from advise.ADVISORS, the worker's standing brief)
TEAM: dict[str, dict[str, str]] = {
    "researcher": {
        "advisor": "gemini-flash",
        "prompt": ("คุณคือนักวิจัยคอนเทนต์ของช่อง YouTube ไทยเรื่องเล่า/ธรรมะ เป้าหมาย YPP "
                   "(ผู้ชมไทย, คลิปยาว 20-120 นาที). งาน: หาหัวข้อ/มุมเรื่องที่คนไทยค้นหาเยอะ "
                   "พร้อมเหตุผลสั้น ๆ ว่าทำไมน่าดู และอ้างอิงว่าข้อมูลมาจากไหนถ้ามี. "
                   "ตอบเป็นภาษาไทย เป็นรายการสั้น ๆ ที่เอาไปใช้ต่อได้ทันที ห้ามเดาตัวเลข"),
    },
    "scriptwriter": {
        "advisor": "gemini-flash",
        "prompt": ("คุณคือนักเขียนบทของช่องเล่าเรื่องไทย. เขียนบทบรรยายภาษาไทยที่ฟังลื่น "
                   "เปิดเรื่องด้วย hook ที่ดึงคนใน 20 วินาทีแรก (มีแรงเสียดทาน/คำถาม) แล้วเล่าเป็นตอน. "
                   "ความยาวตามที่สั่ง. ตอบเป็นบทพร้อมใช้ ไม่ต้องมีคำอธิบายอื่น"),
    },
    "packager": {
        "advisor": "gemini-flash",
        "prompt": ("คุณคือคนแพ็กเกจวิดีโอ YouTube ไทย. ผลิต: ชื่อคลิป (ไม่เกิน 90 ตัวอักษร, มีคำค้น), "
                   "คำอธิบาย 2 ย่อหน้าพร้อมแฮชแท็ก, แท็ก 12-15 คำ (ไทย+อังกฤษ), และข้อความบนปก. "
                   "ตอบเป็นภาษาไทย จัดหัวข้อให้อ่านง่าย"),
    },
    "critic": {
        "advisor": "gemini-3.1",
        "prompt": ("คุณคือผู้ตรวจงานที่โหดแต่ยุติธรรม. ให้เกรด A-D ตามเกณฑ์: (1) เปิดเรื่องดึงคนไหม "
                   "(2) ตรงกลุ่มผู้ชมไทยไหม (3) โครงเรื่องชัดไหม. บอกจุดที่ต้องแก้เป็นข้อ ๆ "
                   "พร้อมเหตุผล. ถ้าดีอยู่แล้วให้บอกว่าผ่าน. ตอบภาษาไทย"),
    },
    "analyst": {
        "advisor": "gemini-3.5",
        "prompt": ("คุณคือนักวิเคราะห์ตัวเลขช่อง YouTube. อ่านตัวเลขที่ให้ (ยอดวิว, ชม.ดู, retention, "
                   "ผู้ติดตาม) แล้วบอกว่าควรทำอะไรต่อก่อน-หลัง เพื่อไปถึง YPP. ใช้เฉพาะตัวเลขที่ให้ "
                   "ห้ามแต่งตัวเลข. ตอบภาษาไทย กระชับ"),
    },
    "engineer": {
        "advisor": "openhands",
        "prompt": ("คุณคือวิศวกรของโปรเจกต์ ai-content-lab (repo kongkeat938/ai-content-lab). "
                   "อ่านโค้ดจริง วัดสาเหตุจริง แล้วเสนอการแก้ที่ทำได้จริง (หรือแก้ให้เลยถ้าทำได้) "
                   "พร้อมหลักฐาน. ห้ามเดา: ถ้าวัดไม่ได้ให้บอกว่าวัดไม่ได้. ตอบภาษาไทย"),
    },
}

DEEP_ROLES = {"engineer"}  # slow workers (OpenHands Cloud); the rest answer in seconds


def worker(role: str) -> dict[str, str]:
    """The worker spec, or a loud error. A missing role is a wiring bug, not a dead worker."""
    spec = TEAM.get(role)
    if spec is None:
        raise KeyError(f"unknown worker {role!r}; team = {sorted(TEAM)}")
    return spec


def mailbox(role: str) -> str | None:
    """The worker's OWN mailbox address (never K's), or None if it has none yet.

    K (2026-11-14): every tool and every agent in the team signs up with its own
    mailbox, never K's. Each worker's mailbox lives in the vault under its own key
    (`ak_mail.py --as <role>`); create one with `ak_mail.py new --as <role>`.
    """
    worker(role)                                        # loud on an unknown role
    sys.path.insert(0, HERE)
    import ak_mail  # noqa: PLC0415
    acct = ak_mail._vault("GET", identity=role)
    return acct.get("address") if acct else None


def dispatch(role: str, task: str) -> str:
    spec = worker(role)
    fn = advise.advisor(spec["advisor"])   # loud if the advisor name is wrong
    # Every worker signs up / acts as ITSELF (K, 2026-11-14), never as K. The brief
    # carries the worker's own mailbox so it can never reach for K's address.
    own = mailbox(role)
    ident = (f"\n\nคุณคือ worker '{role}' ของ ak -- ใช้เมลของตัวเองเท่านั้น"
             + (f" ({own})" if own else " (ยังไม่มีเมล -- สร้างด้วย ak_mail.py new --as "
                f"{role})")
             + " ห้ามใช้เมลของเจ้าของช่อง (K) เด็ดขาด")
    prompt = f"{spec['prompt']}{ident}\n\nงานที่มอบหมาย:\n{task}"
    return fn(prompt).strip()


def cmd_list(_args) -> int:
    print(f"ak's team ({len(TEAM)} workers):")
    for role, spec in TEAM.items():
        kind = "Cloud worker (minutes)" if role in DEEP_ROLES else f"fast ({spec['advisor']})"
        own = mailbox(role) or "(no mailbox yet)"
        print(f"  {role:13} {kind:24} {own:26} {spec['prompt'][:40]}...")
    return 0


def cmd_mail(args) -> int:
    """Create or show a worker's OWN mailbox, so a signup never uses K's address."""
    sys.path.insert(0, HERE)
    import ak_mail  # noqa: PLC0415
    if args.new:
        return ak_mail.cmd_new(argparse.Namespace(as_=args.role))
    addr = mailbox(args.role)
    if addr:
        print(addr)
        return 0
    print(f"no mailbox for {args.role} -- run: python3 scripts/team.py mail {args.role} --new")
    return 1


def cmd_run(args) -> int:
    out = dispatch(args.role, args.task)
    print(f"### {args.role}\n{out}")
    return 0


def cmd_all(args) -> int:
    roles = [r for r in TEAM if r not in DEEP_ROLES]
    results: dict[str, str] = {}

    def run(r: str) -> None:
        try:
            results[r] = dispatch(r, args.task)
        except Exception as exc:  # noqa: BLE001 - one dead worker must not stop the team
            results[r] = f"(unavailable: {str(exc)[:150]})"

    with ThreadPoolExecutor(max_workers=len(roles)) as pool:
        list(pool.map(run, roles))
    for r in roles:
        print(f"### {r}\n{results.get(r, '(no result)')}\n")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="ak's own team of workers")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    r = sub.add_parser("run")
    r.add_argument("role")
    r.add_argument("task")
    r.add_argument("--deep", action="store_true", help="allow a slow Cloud worker")
    r.set_defaults(fn=cmd_run)
    a = sub.add_parser("all")
    a.add_argument("task")
    a.set_defaults(fn=cmd_all)
    m = sub.add_parser("mail", help="create/show a worker's OWN mailbox (never K's)")
    m.add_argument("role")
    m.add_argument("--new", action="store_true", help="create a fresh mailbox for this role")
    m.set_defaults(fn=cmd_mail)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
