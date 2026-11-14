#!/usr/bin/env python3
"""A `videos.update` that writes `part=snippet` must KEEP description and tags.

`videos.update` REPLACES the whole `snippet` part: any field left out of the body is
erased, not preserved. Measured 2026-11-14 -- `optimize_titles.apply_title` sent only
`{title, categoryId}`, so every retitle silently wiped the description and tags
(123/146 genx clips had no tags; 120 of them were retitled). The description holds the
subscribe ask, so this is a subscriber lever erased on every title pass.

This guard runs the real `apply_title` against a fake network and asserts the PUT body
carries the CURRENT description and tags back. It can FAIL: drop either field from the
body and it exits 1.

    python3 scripts/test_snippet_update_preserves.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import optimize_titles as ot  # noqa: E402

CUR = {"title": "old title", "description": "สมัครเลย DESC", "categoryId": "22",
       "tags": ["tag-a", "tag-b"], "defaultLanguage": "th", "defaultAudioLanguage": "th"}


class _Resp:
    def __init__(self, payload: bytes) -> None:
        self._p = payload

    def read(self) -> bytes:
        return self._p

    def __enter__(self) -> "_Resp":
        return self

    def __exit__(self, *a) -> bool:
        return False


def main() -> int:
    captured: dict = {}

    def fake_urlopen(req, timeout=None):          # noqa: ANN001
        captured["body"] = json.loads(req.data.decode())
        return _Resp(json.dumps({"snippet": {"title": captured["body"]["snippet"]["title"]}}
                                ).encode())

    def fake_get(resource, params, token):        # noqa: ANN001
        return {"items": [{"snippet": dict(CUR)}]}

    orig_urlopen, orig_get = urllib.request.urlopen, ot._get
    urllib.request.urlopen = fake_urlopen
    ot._get = fake_get
    try:
        ot.apply_title("VID1", "NEW TITLE", "22", "tok")
    finally:
        urllib.request.urlopen = orig_urlopen
        ot._get = orig_get

    sn = captured.get("body", {}).get("snippet", {})
    if sn.get("title") != "NEW TITLE":
        print(f"FAIL: the new title was not written: {sn.get('title')!r}")
        return 1
    if sn.get("description") != CUR["description"]:
        print(f"FAIL: apply_title did not preserve the description "
              f"(got {sn.get('description')!r}) -- videos.update erased it")
        return 1
    if sn.get("tags") != CUR["tags"]:
        print(f"FAIL: apply_title did not preserve the tags (got {sn.get('tags')!r})")
        return 1
    if sn.get("defaultAudioLanguage") != CUR["defaultAudioLanguage"]:
        print(f"FAIL: apply_title dropped defaultAudioLanguage "
              f"(got {sn.get('defaultAudioLanguage')!r})")
        return 1

    # Secondary source scan: any other VIDEO snippet write must name description+tags
    # in its body too, so a new writer cannot reintroduce the same erase. A write is
    # "a video" if its body targets the videos resource (an inline `/videos` URL, a
    # module-level `API = ".../videos"` variable, or `.videos().update`). Playlist and
    # channel updates are a different resource (no tags) and are not matched.
    import re
    for name in sorted(os.listdir(HERE)):
        if not name.endswith(".py") or name.startswith("test_"):
            continue
        text = open(os.path.join(HERE, name), encoding="utf-8").read()
        lines = text.splitlines()
        videos_vars = set(re.findall(
            r'^(\w+)\s*=\s*f?["\'][^"\']*youtube/v3/videos["\']\s*$', text, re.M))
        for i, line in enumerate(lines):
            near = "\n".join(lines[max(0, i - 6):i + 3])
            if "part=snippet" not in near:
                continue
            is_put = "PUT" in near or ".update(part=" in near
            if not is_put:
                continue
            low = near.lower()
            if "playlists" in low or "/channels" in low or "channels?" in low:
                continue                                  # a different resource
            is_video = ("/videos" in near or "videos?part=snippet" in near
                        or any(v in near for v in videos_vars))
            if not is_video:
                continue
            window = "\n".join(lines[max(0, i - 30):i + 5])
            if '"description"' not in window or '"tags"' not in window:
                print(f"FAIL: {name}:{i + 1} writes videos part=snippet without "
                      f"description+tags in the body -- videos.update would erase them")
                return 1

    print("OK: apply_title preserves description, tags and language; no snippet PUT "
          "omits them")
    return 0


if __name__ == "__main__":
    sys.exit(main())
