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

REPO = "kongkeat938/ai-content-lab"
WORKFLOW = "cred-transport.yml"


def gh(*args: str, check: bool = True) -> str:
    token = os.environ.get("KONGKEAT_GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
    env = dict(os.environ, GH_TOKEN=token)
    # Log output is not guaranteed to be valid UTF-8, and a stray byte must not take
    # the whole run down with a decode error.
    r = subprocess.run(("gh",) + args, capture_output=True, env=env)
    if check and r.returncode != 0:
        err = r.stderr.decode("utf-8", "replace").strip()
        sys.exit(f"gh {' '.join(args)} failed: {err}")
    return r.stdout.decode("utf-8", "replace")


def ensure_key(path: str) -> tuple[str, str]:
    """Return (pem_public, pem_private), creating the pair on first use."""
    pub_path = path + ".pub"
    if not (os.path.exists(path) and os.path.exists(pub_path)):
        subprocess.run(["openssl", "genrsa", "-out", path, "2048"],
                       check=True, capture_output=True)
        subprocess.run(["openssl", "rsa", "-in", path, "-pubout", "-out", pub_path],
                       check=True, capture_output=True)
        os.chmod(path, 0o600)
    with open(pub_path) as fh:
        pub = fh.read()
    with open(path) as fh:
        priv = fh.read()
    return pub, priv


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
    for _ in range(30):
        time.sleep(6)
        out = gh("run", "list", "--repo", REPO, "--workflow", WORKFLOW,
                 "--limit", "5", "--json", "databaseId,createdAt,status")
        runs = json.loads(out or "[]")
        fresh = [r for r in runs if r.get("status") != "completed"] or runs
        if fresh:
            run_id = str(fresh[0]["databaseId"])
            if fresh[0].get("status") == "completed":
                break

    if run_id:
        gh("run", "watch", run_id, "--repo", REPO, "--exit-status", check=False)
        # `gh run view --log` is used rather than the API's log endpoint, which
        # returns a zip. The echoed script is interleaved with the output, and that
        # echoed script contains the marker strings, so the filters below require the
        # line to be bare output rather than source.
        log = gh("run", "view", run_id, "--repo", REPO, "--log", check=False)
    else:
        log = ""

    ct = ""
    for line in log.splitlines():
        # The real line is bare output: it has no surrounding source quoting.
        if "CIPHERTEXT_B64=" in line and "print(" not in line and '"' not in line:
            ct = line.split("CIPHERTEXT_B64=", 1)[1].strip().strip("'\"")
        if "EMPTY:" in line and "print(" not in line:
            print(line.split("EMPTY:", 1)[1].strip(), file=sys.stderr)
            return 2

    if not ct:
        print("no ciphertext in the run log; the workflow may have failed", file=sys.stderr)
        return 3

    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    key = serialization.load_pem_private_key(priv.encode(), password=None)
    value = key.decrypt(base64.b64decode(ct), padding.OAEP(
        mgf=padding.MGF1(algorithm=hashes.SHA256()),
        algorithm=hashes.SHA256(), label=None)).decode()

    print(f"# {args.secret_name}: {len(value)} chars", file=sys.stderr)
    sys.stdout.write(value)
    if sys.stdout.isatty():
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
