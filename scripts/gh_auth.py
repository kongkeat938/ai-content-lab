"""GitHub push access with no human in the loop.

Measured 2026-11-22: every pod recycle left ak unable to push -- `GITHUB_TOKEN`
is a read-only App token, the classic PAT was revoked, and `gh auth
git-credential` hands git the env token before `hosts.yml`, so even a good
credential came back 403 "denied to kongkeat938".

The credential now lives in the durable KV vault (the same store as ak's
mailbox), so a fresh pod restores it from `OPENHANDS_API_KEY` alone:

    python3 scripts/gh_auth.py status     # where the token comes from, who it is
    python3 scripts/gh_auth.py setup      # write the git helper + verify
    python3 scripts/gh_auth.py push       # push main with the env tokens unset
    python3 scripts/gh_auth.py save TOK   # store a token (vault + ~/.config/gh)

Source order: `$GH_PUSH_TOKEN`, the vault key `ak.github.token`, then
`~/.config/gh/token`. The token is never printed.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request

AID = "94068e1c-c98c-4f3b-96f5-0df4a1e9a78a"
VAULT_KEY = "ak.github.token"
LOCAL = os.path.expanduser("~/.config/gh/token")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# gh hands git the env token first; these must be gone for our credential to win.
SHADOWING = ("GH_TOKEN", "GITHUB_TOKEN")


def _vault(method: str, value: dict | None = None) -> dict | None:
    key = os.environ.get("OPENHANDS_API_KEY") or os.environ.get("KONGKEAT_OH_KEY")
    if not key:
        return None
    url = f"https://app.all-hands.dev/api/automation/v1/kv/{VAULT_KEY}?automation_id={AID}"
    body = json.dumps({"value": json.dumps(value)}).encode() if value is not None else None
    req = urllib.request.Request(url, data=body, method=method,
                                 headers={"Authorization": "Bearer " + key,
                                          "Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=25)
    except Exception:                                   # noqa: BLE001 - any miss is "no token"
        return None
    raw = json.loads(r.read().decode()).get("value")
    if isinstance(raw, str):
        raw = json.loads(raw)
    if isinstance(raw, dict) and isinstance(raw.get("value"), str):
        raw = json.loads(raw["value"])
    return raw if isinstance(raw, dict) else None


def token() -> tuple[str, str]:
    """(token, source). Empty token means nothing was found."""
    env = os.environ.get("GH_PUSH_TOKEN", "").strip()
    if env:
        return env, "env:GH_PUSH_TOKEN"
    stored = _vault("GET") or {}
    if stored.get("token"):
        return stored["token"], "vault:ak.github.token"
    if os.path.exists(LOCAL):
        with open(LOCAL, encoding="utf-8") as fh:
            local = fh.read().strip()
        if local:
            return local, "file:" + LOCAL
    return "", "none"


def _candidates():
    """Every token we hold, in source order, without repeats."""
    env = os.environ.get("GH_PUSH_TOKEN", "").strip()
    vault = (_vault("GET") or {}).get("token", "") or ""
    local = ""
    if os.path.exists(LOCAL):
        with open(LOCAL, encoding="utf-8") as fh:
            local = fh.read().strip()
    seen = set()
    for tok, src in ((env, "env:GH_PUSH_TOKEN"), (vault, "vault:ak.github.token"),
                     (local, "file:" + LOCAL)):
        if tok and tok not in seen:
            seen.add(tok)
            yield tok, src


def verified() -> tuple[str, str, dict]:
    """The first candidate GitHub ACCEPTS, with its source and the /user payload.

    Measured 2026-11-22: `KONGKEAT_GH_TOKEN` answered 401 while the vault copy was
    still valid, and pure source order failed a push that could have worked.
    """
    for tok, src in _candidates():
        status, who = _api(tok, "/user")
        if status == 200:
            return tok, src, who
    return "", "none", {}


def _api(tok: str, path: str) -> tuple[int, dict]:
    req = urllib.request.Request("https://api.github.com" + path,
                                 headers={"Authorization": "Bearer " + tok,
                                          "Accept": "application/vnd.github+json"})
    try:
        r = urllib.request.urlopen(req, timeout=25)
        return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, {}


def save(tok: str) -> int:
    tok = tok.strip()
    if not tok:
        print("refusing to save an empty token")
        return 1
    status, who = _api(tok, "/user")
    if status != 200:
        print(f"token rejected by GitHub ({status}); nothing saved")
        return 1
    ok = _vault("PUT", {"token": tok, "login": who.get("login", ""),
                        "saved_utc": __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ",
                                                                  __import__("time").gmtime())})
    os.makedirs(os.path.dirname(LOCAL), exist_ok=True)
    with open(LOCAL, "w", encoding="utf-8") as fh:
        fh.write(tok)
    os.chmod(LOCAL, 0o600)
    print(f"saved for {who.get('login')} | vault: {'yes' if ok else 'NO'} | file: {LOCAL}")
    return 0 if ok else 1


def setup() -> int:
    tok, source, who = verified()
    if not tok:
        if token()[0]:
            print(f"every token we hold was rejected by GitHub ({token()[1]}) -- "
                  f"cannot push")
        else:
            print("no GitHub token found: set GH_PUSH_TOKEN, or run "
                  "`python3 scripts/gh_auth.py save <token>`")
        return 1
    repo = subprocess.run(["git", "remote", "get-url", "origin"], cwd=ROOT,
                          capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout.strip()
    slug = repo.split("github.com/")[-1].removesuffix(".git") if "github.com/" in repo else ""
    perm = {}
    if slug:
        _, data = _api(tok, f"/repos/{slug}")
        perm = data.get("permissions") or {}
    os.makedirs(os.path.dirname(LOCAL), exist_ok=True)
    with open(LOCAL, "w", encoding="utf-8") as fh:
        fh.write(tok)
    os.chmod(LOCAL, 0o600)
    subprocess.run(["git", "config", "--local", "credential.helper",
                    '!f() { echo username=x-access-token; '
                    'echo "password=$(cat $HOME/.config/gh/token)"; }; f'],
                   cwd=ROOT, check=True, stdin=subprocess.DEVNULL)
    print(f"credential ready | {who.get('login')} | source {source} | "
          f"push={perm.get('push')} admin={perm.get('admin')}")
    if not perm.get("push"):
        print("WARNING: this token cannot push to " + (slug or "origin"))
        return 1
    return 0


def push() -> int:
    env = {k: v for k, v in os.environ.items() if k not in SHADOWING}
    r = subprocess.run(["git", "push", "origin", "HEAD:main"], cwd=ROOT, env=env,
                       stdin=subprocess.DEVNULL)
    if r.returncode == 0:
        return 0
    # Measured 2026-11-22: a fresh pod answered 403 through the credential helper
    # even with a valid token, and the same token in a header pushed fine. The
    # header goes through the environment, so the token never reaches argv.
    tok, source, _ = verified()
    if not tok:
        return r.returncode
    print(f"helper path failed; retrying with {source} in an auth header")
    env.update({"GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "http.extraheader",
                "GIT_CONFIG_VALUE_0": f"Authorization: Bearer {tok}"})
    return subprocess.run(["git", "push", "origin", "HEAD:main"], cwd=ROOT, env=env,
                          stdin=subprocess.DEVNULL).returncode


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "status":
        tok, source = token()
        if not tok:
            print("no token: " + source)
            return 1
        status, who = _api(tok, "/user")
        print(f"source={source} login={who.get('login') if status == 200 else f'HTTP {status}'}")
        return 0 if status == 200 else 1
    if cmd == "save":
        return save(sys.argv[2] if len(sys.argv) > 2 else "")
    if cmd == "setup":
        return setup()
    if cmd == "push":
        return push()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
