"""Guard: the Google login must be a phone task, not a noVNC task.

K (2026-11-22): "I work from a phone; in noVNC I cannot scroll or zoom and
reaching the password field is a fight." So the device flow is the only
documented login path, and its state machine must be able to FAIL:

  * authorization_pending -> keep waiting
  * slow_down             -> widen the interval, then keep waiting
  * access_denied         -> exit 2
  * expired_token         -> exit 3
  * an expired deadline   -> exit 3, never a silent success

The refresh token must never appear in what K is shown.
"""
import io
import json
import os
import sys
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import yt_auth_device as dev  # noqa: E402

ok = 0


def check(name, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        sys.exit(1)
    ok += 1


CLIENT = {"client_id": "cid.apps.googleusercontent.com", "client_secret": "s"}
DEVICE = {"device_code": "dc", "user_code": "LBXJ-MZLR", "expires_in": 1800, "interval": 0}
REFRESH = "1//SECRET-refresh-token-value"


def scripted(answers):
    """_post stand-in: pop one (status, body) per call."""
    calls = []

    def _post(url, data):
        calls.append(data)
        return answers.pop(0) if answers else (400, {"error": "expired_token"})

    return _post, calls


# 1) Pending twice, then the token -- and the grant is the device grant.
dev._post, calls = scripted([
    (400, {"error": "authorization_pending"}),
    (400, {"error": "authorization_pending"}),
    (200, {"access_token": "at", "refresh_token": REFRESH, "scope": "s1 s2"}),
])
tok = dev.poll(DEVICE, CLIENT, sleep=lambda s: None, now=lambda: 0)
check("pending then token", tok["access_token"] == "at")
check("device grant sent", calls[-1]["grant_type"] ==
      "urn:ietf:params:oauth:grant-type:device_code")

# 2) slow_down widens the interval instead of hammering.
dev._post, calls = scripted([(400, {"error": "slow_down"}),
                             (200, {"access_token": "at2"})])
seen = []
dev.poll(DEVICE, CLIENT, sleep=seen.append, now=lambda: 0)
check("slow_down widens", seen == [0, 5])

# 3) A refusal is terminal and loud.
dev._post, _ = scripted([(400, {"error": "access_denied"})])
try:
    dev.poll(DEVICE, CLIENT, sleep=lambda s: None, now=lambda: 0)
    check("access_denied raises", False)
except dev.DeviceError as e:
    check("access_denied raises", e.code == "access_denied")

# 4) The code expiring must FAIL -- a guard that cannot fail proves nothing.
dev._post, _ = scripted([])
try:
    dev.poll(DEVICE, CLIENT, timeout=1, sleep=lambda s: None,
             now=iter([0, 5, 10]).__next__)
    check("expiry raises", False)
except dev.DeviceError as e:
    check("expiry raises", e.code == "expired_token")

# 5) What K sees: the phone URL, the code, and no secret.
buf = io.StringIO()
with redirect_stdout(buf):
    dev.announce(DEVICE)
out = buf.getvalue()
check("shows phone url + code", "google.com/device" in out and "LBXJ-MZLR" in out)
check("no secret in the prompt", REFRESH not in out and "SECRET" not in out)

# 6) The docs must point at the phone path, and must not send K to noVNC to log in.
root = os.path.dirname(HERE)
doc = open(os.path.join(root, "docs", "PROJECT-MAP.md"), encoding="utf-8").read()
check("map documents the phone login", "yt_auth_device.py" in doc)
# A dated file is a record of what was measured then, not an instruction: the
# rule binds the docs an agent acts on (AGENTS.md, the undated docs, memory).
bad = []
import glob
import re
paths = ([os.path.join(root, "AGENTS.md")]
         + sorted(glob.glob(os.path.join(root, "docs", "*.md")))
         + [os.path.join(root, ".openhands", "memory", "MEMORY.md")])
for path in paths:
    if not os.path.exists(path) or re.search(r"20\d\d-\d\d-\d\d", os.path.basename(path)):
        continue
    name = os.path.relpath(path, root)
    for i, line in enumerate(open(path, encoding="utf-8"), 1):
        low = line.lower()
        if ("novnc" in low or "pc1" in low) and ("login" in low or "log in" in low
                                                 or "ล็อกอิน" in line or "รหัส" in line):
            if not any(w in low for w in ("never", "no longer", "ไม่ต้อง", "instead", "ห้าม",
                                           "superseded", "yt_auth_device")):
                bad.append(f"{name}:{i}")
check("no doc sends K to noVNC for a login", not bad)

print(f"{ok} checks passed")
