#!/usr/bin/env bash
# Start a real (headful) Chromium inside the pod, reachable over CDP.
#
# Why this exists: the pod's built-in headless browser cannot sign in to Google --
# Google answers "This browser or app may not be secure" and bounces the request to
# /signin/rejected (measured 2026-11-08). A headful Chromium driven over the
# DevTools protocol does not trip that check: it reached the password page for a
# real account (measured the same day). So the working tool is a visible browser on
# a virtual display, not the headless one and not K's PC.
#
# Prints the CDP endpoint on stdout; leaves Xvfb and Chromium running.
#
#   scripts/pod_chrome.sh            # start (idempotent)
#   scripts/pod_chrome.sh --stop
#
# Chromium runs with --no-sandbox because the pod's kernel has no usable sandbox
# (chromium refuses to start otherwise) and --disable-dev-shm-usage because /dev/shm
# is small here. The display is local to the pod; nothing is exposed.
set -u

PORT="${CDP_PORT:-9222}"
DISPLAY_NUM="${DISPLAY_NUM:-99}"
PROFILE="${CHROME_PROFILE:-/tmp/pod-chrome-profile}"
BIN="${CHROME_BIN:-/usr/bin/chromium}"

if [ "${1:-}" = "--stop" ]; then
  pkill -f "remote-debugging-port=${PORT}" 2>/dev/null
  pkill -f "Xvfb :${DISPLAY_NUM}" 2>/dev/null
  echo "stopped"
  exit 0
fi

if curl -s -m 3 "http://127.0.0.1:${PORT}/json/version" >/dev/null 2>&1; then
  echo "http://127.0.0.1:${PORT}"
  exit 0
fi

command -v Xvfb >/dev/null 2>&1 || { echo "Xvfb missing: sudo apt-get install -y xvfb" >&2; exit 1; }
if ! pgrep -f "Xvfb :${DISPLAY_NUM}" >/dev/null 2>&1; then
  nohup Xvfb ":${DISPLAY_NUM}" -screen 0 1440x900x24 >/tmp/xvfb.log 2>&1 &
  sleep 2
fi

DISPLAY=":${DISPLAY_NUM}" nohup "$BIN" \
  --no-sandbox --disable-gpu --disable-dev-shm-usage \
  --remote-debugging-port="${PORT}" --remote-allow-origins='*' \
  --no-first-run --no-default-browser-check \
  --user-data-dir="${PROFILE}" --window-size=1440,900 \
  about:blank >/tmp/pod-chrome.log 2>&1 &

for _ in $(seq 1 20); do
  if curl -s -m 2 "http://127.0.0.1:${PORT}/json/version" >/dev/null 2>&1; then
    echo "http://127.0.0.1:${PORT}"
    exit 0
  fi
  sleep 1
done
echo "chromium did not come up; see /tmp/pod-chrome.log" >&2
exit 1
