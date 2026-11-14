# AK-IDENTITY — ak's own profile and mailbox (do not forget again)

K (2026-11-13): *"Ak ลืมไปหรือยังว่า ak มีโปรไฟล์และเมลของตัวเอง"* — ak **had** its own
mailbox, but the note lived only in the **old `ax-workspace` repo** and in a **PC1 vault
that is now dead**, so a fresh session never saw it. That is the root cause of the
"forgetting". This file is the durable copy in the live repo.

## What ak is allowed to own (measured history, `ax-workspace` 2026-10-31 → 11-01)
- K: *"ถ้าติดก็ใช้เมล์ของบริษัทใหม่นะ"* → ak **opened its own mailbox**, built entirely on PC1
  so the credential never crossed the chat. Providers used: **tempmail.lol** (ephemeral) and
  **mail.tm** (durable, has a password → recoverable). The PC1 vault held the values; the repo
  held only the map (`ax-workspace/docs/MAILBOXES.md`).
- Rule ak set for itself (`AK-ACCOUNTS.md` #3): **"ak never signs up as K"** — ak may open free
  accounts of its own, but never impersonate K's identity, and must stop and ask if a service
  demands a phone number that ak cannot own.

## ak's live mailbox (re-established 2026-11-13, measured)
- Address: **`akmaila185d0@fldubai.com`** (provider **mail.tm**, domain `fldubai.com`).
- Has a password → recoverable; re-create a fresh one with `scripts/ak_mail.py new` if purged.
- Stored in the **KV vault** (survives sandbox death): key `ak.identity.mailbox`
  (anchor automation `94068e1c-c98c-4f3b-96f5-0df4a1e9a78a`, `ax_vault`). Read it back with
  `scripts/ak_mail.py show`.
- Measured live: `POST /accounts` 201, `POST /token` 200 (token 354 chars), `GET /messages` 200,
  `GET /me` 200 (quota 40 MB, `isDisabled=false`).

## EVERY tool and EVERY agent uses its OWN mailbox (K, 2026-11-14)
K: *"ต่อไปเครื่องมือทุกอย่างใช้เมล์ตัวเองล็อกอินเลย รวมถึง agent ในทีมด้วย ไม่ต้องใช้เมล์ K แล้ว"*.

So a mailbox is now **per-identity**, not just for ak. The vault key is
`ak.identity.mailbox` for ak and **`ak.identity.mail.<role>`** for every worker in `team.py`.
Never K's address (`kongkeat.938` / `farmmer.938` / `kongkeat.p3` / `aerismusic8`) — those are
the **business channel assets**, a different thing entirely (they stay, for the YouTube API).

```
python3 scripts/ak_mail.py new  --as researcher   # a worker's own mailbox
python3 scripts/ak_mail.py show --as critic
python3 scripts/ak_mail.py roster                 # every identity + its address (no passwords)
python3 scripts/team.py mail researcher --new     # same, from the team CLI
```

Measured live 2026-11-14: all **7 identities** (ak + researcher, scriptwriter, packager,
critic, analyst, engineer) each created a distinct mailbox and stored it. The roster is read
from `team.py`, so a new worker is never silently missing a mailbox.

**Trap fixed (the real reason ak "forgot" its mailbox):** `cmd_new` created an address at the
provider but a failed vault write still exited 0 → the mailbox existed but was never recorded,
so the next session read "no ak mailbox". Now a failed store **exits 1** (a generator that can
drop a piece must FAIL), the vault write retries, and `scripts/test_agent_own_email.py` locks
both this and the per-identity separation.


## How to use it (headless, no human)
```
python3 scripts/ak_mail.py new                 # create + store a fresh ak mailbox
python3 scripts/ak_mail.py show                # print the stored address (no password)
python3 scripts/ak_mail.py inbox               # list messages in ak's own inbox
python3 scripts/ak_mail.py read <id>           # read one message (verification links)
```
Use it when a free tool needs an email to sign up — ak uses **its own** address, never K's.

## Provider facts measured 2026-11-13 (from the pod)
- **mail.tm** works with a browser User-Agent: create 201, token 200, read 200.
- **tempmail.lol** works with a browser User-Agent for create+read (403 without one).
- Blocked / unusable from this IP: `mail.gw` (connection refused), `1secmail` (TLS mismatch),
  `guerrillamail` / `temp-mail.io` / `mailsac` (403 Cloudflare), `inboxes.com` (DNS).
- **Trap:** `mail.tm`'s `POST /token` returns **401 for a while right after create** and the
  response can exceed a naive read buffer — read the full body and retry the token a few times.
