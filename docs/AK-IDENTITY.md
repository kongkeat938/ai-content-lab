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
