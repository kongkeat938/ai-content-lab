"""Guard: push access must come back with no human in the loop.

Measured 2026-11-22: every recycle left ak unable to push (read-only App token,
revoked PAT, and `gh` handing git the env token first). The fix is a credential
that survives in the KV vault. This test pins the source order, the loud failure
when nothing is found, and that the token is never printed.
"""
import io
import os
import sys
import tempfile
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gh_auth  # noqa: E402

ok = 0


def check(name, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        sys.exit(1)
    ok += 1


TOKEN = "gho_" + "x" * 36

# 1) $GH_PUSH_TOKEN wins.
os.environ["GH_PUSH_TOKEN"] = TOKEN
check("env wins", gh_auth.token() == (TOKEN, "env:GH_PUSH_TOKEN"))

# 2) With no env token the vault is the next source (network boundary stubbed).
os.environ.pop("GH_PUSH_TOKEN", None)
gh_auth._vault = lambda method, value=None: {"token": TOKEN, "login": "kongkeat938"}
check("vault second", gh_auth.token() == (TOKEN, "vault:ak.github.token"))

# 3) An empty vault falls through to the local file, and a missing one is "none".
tmp = tempfile.mkdtemp(prefix="ghauth_")
gh_auth._vault = lambda method, value=None: None
gh_auth.LOCAL = os.path.join(tmp, "token")
check("nothing found", gh_auth.token() == ("", "none"))
with open(gh_auth.LOCAL, "w", encoding="utf-8") as fh:
    fh.write(TOKEN)
check("file third", gh_auth.token() == (TOKEN, "file:" + gh_auth.LOCAL))

# 4) No token must FAIL setup loudly, not pretend to be ready.
os.remove(gh_auth.LOCAL)
buf = io.StringIO()
with redirect_stdout(buf):
    rc = gh_auth.setup()
check("setup fails with no token", rc == 1 and "no GitHub token" in buf.getvalue())

# 5) status never prints the secret.
gh_auth._vault = lambda method, value=None: {"token": TOKEN}
gh_auth._api = lambda tok, path: (200, {"login": "kongkeat938"})
buf = io.StringIO()
with redirect_stdout(buf):
    gh_auth.main.__globals__["sys"].argv = ["gh_auth.py", "status"]
    gh_auth.main()
check("token never printed", TOKEN not in buf.getvalue() and "kongkeat938" in buf.getvalue())

# 6) save() refuses a token GitHub rejects.
gh_auth._api = lambda tok, path: (401, {})
buf = io.StringIO()
with redirect_stdout(buf):
    rc = gh_auth.save(TOKEN)
check("bad token rejected", rc == 1 and "rejected" in buf.getvalue())

# 7) A token GitHub rejects must not block a later source that still works.
#    Measured 2026-11-22: the env token answered 401 while the vault copy pushed.
os.environ["GH_PUSH_TOKEN"] = "dead-token"
gh_auth.LOCAL = os.path.join(tmp, "absent")
gh_auth._vault = lambda method, value=None: {"token": TOKEN}
gh_auth._api = lambda tok, path: (401, {}) if tok == "dead-token" else (200, {"login": "kongkeat938"})
tok, src, who = gh_auth.verified()
check("a rejected token falls through", (tok, src, who.get("login")) ==
      (TOKEN, "vault:ak.github.token", "kongkeat938"))

# 8) push() retries through an auth HEADER (not argv) when the helper path fails,
#    so the secret never shows up in the process list.
calls = []


class R:
    def __init__(self, rc):
        self.returncode = rc


def fake_run(argv, **kw):
    calls.append((argv, kw.get("env") or {}))
    return R(0)


real_run = gh_auth.subprocess.run
gh_auth.subprocess.run = fake_run
try:
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = gh_auth.push()
finally:
    gh_auth.subprocess.run = real_run
    os.environ.pop("GH_PUSH_TOKEN", None)
env2 = calls[-1][1]
import base64 as _b64
check("push used the token", rc == 0 and len(calls) == 1)
check("token travels as basic auth in the env, not argv",
      env2.get("GIT_CONFIG_VALUE_0") == "Authorization: basic " + _b64.b64encode(
          f"x-access-token:{TOKEN}".encode()).decode()
      and all(TOKEN not in " ".join(a) for a, _ in calls)
      and TOKEN not in buf.getvalue())

print(f"{ok} checks passed")
