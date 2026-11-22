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

print(f"{ok} checks passed")
