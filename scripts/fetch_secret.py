#!/usr/bin/env python3
"""Fetch a repository secret onto the pod, encrypted so the trip is safe.

A GitHub secret is write-only: nothing can read it back, not the API and not the
agent. So the value is moved the other way -- a GitHub Actions job encrypts it to a
public key whose private half exists only on this pod, prints the ciphertext, and
this script decrypts it here. The ciphertext can sit in a public log; only this
machine can open it.

    python3 scripts/fetch_secret.py IMAP_ACCOUNTS [--key ~/.pod-cred-key.pem]

The private key is created on first use and never leaves the pod. The decrypted
value is printed to stdout once, so write it somewhere safe or pipe it straight
into the place that needs it -- do not leave it in a shell history.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

REPO = "kongkeat938/ai-content-lab"
WORKFLOW = "cred-transport.yml"


def gh(*args: str, check: bool = True, timeout: float | None = None) -> str:
    token = os.environ.get("KONGKEAT_GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
    # A minimal env, not dict(os.environ): the child needs a PATH, a HOME for gh's
    # config, and the token -- nothing else. Copying the pod's whole environment
    # would hand every other secret (YT_CH*_REFRESH_TOKEN, GEMINI_API_KEY) to a
    # process that never uses them. GH_CONFIG_DIR is pinned to this script's own
    # directory so gh cannot pick up a token from root's global config.
    env = {"GH_TOKEN": token, "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
           "HOME": os.environ.get("HOME", "/root"),
           "GH_CONFIG_DIR": os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         ".gh-config")}
    for keep in ("GH_HOST", "NO_COLOR", "LANG"):
        if keep in os.environ:
            env[keep] = os.environ[keep]
    # Log output is not guaranteed to be valid UTF-8, and a stray byte must not take
    # the whole run down with a decode error.
    try:
        r = subprocess.run(("gh",) + args, capture_output=True, env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        # `gh run watch` blocks until the run ends; a wedged run would hang the pod
        # forever. The timeout is deliberate -- say TIMEOUT, not just "failed", so
        # a hang is never mistaken for a run that finished with no log. Whatever
        # log exists is read next, and PLAINTEXT_LEN rejects a truncated one.
        print(f"TIMEOUT: gh {' '.join(args)} exceeded {timeout}s "
              f"({timeout / 60:.0f} min); continuing with whatever log exists",
              file=sys.stderr)
        return ""
    if r.returncode != 0:
        err = r.stderr.decode("utf-8", "replace").strip()
        if check:
            sys.exit(f"gh {' '.join(args)} failed: {err}")
        # `check=False` is used where a failed run still has a readable log. Say
        # ERROR with the exit code and gh's own message, so a failure is never
        # silent and is never confused with the TIMEOUT above.
        print(f"ERROR: gh {' '.join(args)} exited {r.returncode}: {err}",
              file=sys.stderr)
    return r.stdout.decode("utf-8", "replace")


def ensure_key(path: str) -> tuple[str, str]:
    """Return (pem_public, pem_private), creating the pair on first use.

    The private key is created through a 0600 file descriptor rather than written
    by openssl and chmod-ed after: between those two calls the key sits on disk
    world-readable, which is exactly the window a copy would come from.
    """
    pub_path = path + ".pub"
    if not (os.path.exists(path) and os.path.exists(pub_path)):
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.close(fd)
        subprocess.run(["openssl", "genrsa", "-out", path, "2048"],
                       check=True, capture_output=True)
        os.chmod(path, 0o600)  # openssl rewrites the file; restore the mode
        subprocess.run(["openssl", "rsa", "-in", path, "-pubout", "-out", pub_path],
                       check=True, capture_output=True)
    if os.stat(path).st_mode & 0o077:
        print(f"warning: {path} is readable by other users; tightening to 0600",
              file=sys.stderr)
        os.chmod(path, 0o600)
    with open(pub_path) as fh:
        pub = fh.read()
    with open(path) as fh:
        priv = fh.read()
    return pub, priv


def created_epoch(run: dict) -> float:
    """A run's creation time as epoch seconds; 0.0 if unreadable.

    `gh run list --json createdAt` gives `2026-11-16T04:18:12Z`. A run with an
    unreadable timestamp sorts oldest, so it can never displace a run we know
    started after our dispatch.
    """
    try:
        return datetime.strptime(run.get("createdAt", ""), "%Y-%m-%dT%H:%M:%SZ") \
            .replace(tzinfo=timezone.utc).timestamp()
    except (TypeError, ValueError):
        return 0.0


def parse_log(log: str, run_id: str) -> tuple[str, int, int]:
    """Pull (ciphertext, plaintext_len, status) out of a run log.

    status: 0 = ok, 2 = the workflow said the secret is empty, 3 = no usable
    ciphertext. Only bare output lines count -- `gh run view --log` also echoes
    the workflow source, which contains these same marker strings.
    """
    ct = ""
    want_len = -1
    for line in log.splitlines():
        if "EMPTY:" in line and "print(" not in line:
            return "", -1, 2
        if "PLAINTEXT_LEN=" in line and "print(" not in line:
            try:
                want_len = int(line.split("PLAINTEXT_LEN=", 1)[1].strip())
            except ValueError:
                want_len = -1
        if "CIPHERTEXT_B64=" not in line or "print(" in line or '"' in line:
            continue
        found = line.split("CIPHERTEXT_B64=", 1)[1].strip().strip("'\"")
        # The workflow prefixes its own run id, so a line from another run is
        # ignored rather than decrypted -- two runs share the log listing.
        marker, _, payload = found.partition(":")
        if not marker.isdigit() or marker != run_id:
            continue
        if payload and ct and payload != ct:
            return "", -1, 3
        ct = payload or ct
    return ct, want_len, 0 if ct else 3


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("secret_name")
    ap.add_argument("--key", default=os.path.expanduser("~/.pod-cred-key.pem"))
    args = ap.parse_args()

    pub, priv = ensure_key(args.key)
    pub_b64 = base64.b64encode(pub.encode()).decode()

    before = time.time()
    gh("workflow", "run", WORKFLOW, "--repo", REPO,
       "-f", f"secret_name={args.secret_name}", "-f", f"pubkey={pub_b64}")
    print(f"triggered {WORKFLOW} for {args.secret_name}; waiting...", file=sys.stderr)

    run_id = ""
    # `before` exists so the poll can ignore older runs: `run list` returns the
    # newest entries of every dispatch, so an earlier cred-transport run would be
    # picked as "fresh" and its log read instead of ours.
    for _ in range(30):
        time.sleep(6)
        out = gh("run", "list", "--repo", REPO, "--workflow", WORKFLOW,
                 "--limit", "10", "--json", "databaseId,createdAt,status")
        runs = json.loads(out or "[]")
        mine = [r for r in runs if created_epoch(r) >= before - 30]
        if not mine:
            continue
        newest = max(mine, key=created_epoch)
        run_id = str(newest["databaseId"])
        if newest.get("status") == "completed":
            break

    if run_id:
        gh("run", "watch", run_id, "--repo", REPO, "--exit-status", check=False,
           timeout=600)
        # `gh run view --log` is used rather than the API's log endpoint, which
        # returns a zip. The echoed script is interleaved with the output, and that
        # echoed script contains the marker strings, so the filters below require the
        # line to be bare output rather than source.
        log = gh("run", "view", run_id, "--repo", REPO, "--log", check=False)
    else:
        log = ""

    ct, want_len, status = parse_log(log, run_id)
    if status == 2:
        print(f"no secret named {args.secret_name} is visible to the workflow",
              file=sys.stderr)
        return 2
    if status == 3 or not ct:
        print("no ciphertext in the run log; the workflow may have failed, or the "
              "line belongs to a different run", file=sys.stderr)
        return 3

    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    key = serialization.load_pem_private_key(priv.encode(), password=None)
    try:
        value = key.decrypt(base64.b64decode(ct), padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(), label=None)).decode()
    except Exception as exc:
        # A decrypt failure means the ciphertext is not ours: wrong run, or a
        # different pod key. Say which, instead of dumping a raw traceback.
        print(f"could not decrypt the ciphertext with {args.key}: {exc}", file=sys.stderr)
        return 4

    # PLAINTEXT_LEN is printed by the workflow, so the decrypted value is checked
    # against it -- a truncated log would otherwise yield a silently short secret.
    if want_len >= 0 and len(value) != want_len:
        print(f"decrypted {len(value)} chars but the workflow said {want_len}; "
              f"the log was truncated -- refusing to emit a partial secret",
              file=sys.stderr)
        return 4

    print(f"# {args.secret_name}: {len(value)} chars", file=sys.stderr)
    sys.stdout.write(value)
    if sys.stdout.isatty():
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
