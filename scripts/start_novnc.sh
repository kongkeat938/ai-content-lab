#!/usr/bin/env bash
# Start a headless desktop on the pod and serve it over the work-2 URL, so a
# person with a browser can log in to a site (YouTube Studio, Google, ...) and
# leave the session signed in for the agent to drive.
#
# Why: some logins cannot be done by an agent -- Google blocks automated
# browsers, and the OAuth flow needs a human. A real Chromium in a real X
# session, reachable through noVNC, is the way the owner does that login once.
#
# What it starts:
#   Xvfb        a virtual 1440x900 display on :99
#   chromium    with --remote-debugging-port so the agent can drive it over CDP
#   x11vnc      shares :99
#   websockify  serves noVNC + the VNC socket on $PORT (default 12001 = work-2)
#
# Free tools only. Idempotent: an already-running instance is left alone.
#
# Usage:  scripts/start_novnc.sh [port]
# Then open:  <work-2 URL>/vnc.html   (or /vnc_lite.html for the simple client)
set -u

PORT="${1:-12001}"
DISPLAY_NUM=":99"
SCREEN="1440x900x24"
VNC_PASS_FILE="${HOME}/.vnc/passwd"
LOG_DIR="${HOME}/.novnc"
mkdir -p "$LOG_DIR" "$(dirname "$VNC_PASS_FILE")"

# A shared, known password so the owner is not guessing. Overridable.
VNC_PASSWORD="${VNC_PASSWORD:-contentlab}"

running() { pgrep -f "$1" >/dev/null 2>&1; }

if ! running "Xvfb $DISPLAY_NUM"; then
  echo "starting Xvfb on $DISPLAY_NUM"
  nohup Xvfb "$DISPLAY_NUM" -screen 0 "$SCREEN" -ac >"$LOG_DIR/xvfb.log" 2>&1 &
  sleep 2
fi

# VNC password (8 chars max). x11vnc wants the encrypted form.
if [ ! -f "$VNC_PASS_FILE" ]; then
  x11vnc -storepasswd "$VNC_PASSWORD" "$VNC_PASS_FILE" >/dev/null 2>&1
fi

if ! running "x11vnc"; then
  echo "starting x11vnc"
  nohup x11vnc -display "$DISPLAY_NUM" -rfbauth "$VNC_PASS_FILE" \
    -forever -shared -rfbport 5900 -quiet >"$LOG_DIR/x11vnc.log" 2>&1 &
  sleep 2
fi

if ! running "websockify"; then
  echo "starting websockify + noVNC on :$PORT"
  nohup websockify --web=/usr/share/novnc "$PORT" localhost:5900 \
    >"$LOG_DIR/websockify.log" 2>&1 &
  sleep 2
fi

if ! running "remote-debugging-port=9222"; then
  echo "starting chromium (CDP on 9222)"
  nohup env DISPLAY="$DISPLAY_NUM" chromium \
    --no-sandbox --disable-dev-shm-usage \
    --remote-debugging-port=9222 \
    --remote-allow-origins='*' \
    --user-data-dir="$HOME/.chromium-profile" \
    --window-size=1440,900 --start-maximized \
    --no-first-run --no-default-browser-check \
    "https://www.youtube.com" >"$LOG_DIR/chromium.log" 2>&1 &
  sleep 5
fi

cat <<EOF

noVNC is up.

  Open this in your browser:  \$WORK_HOST_2  ->  port $PORT
  Path:  /vnc.html        (full client)
         /vnc_lite.html   (simple client, scales to fit)

  VNC password:  $VNC_PASSWORD

  CDP for the agent:  http://localhost:9222/json/version
  Logs:  $LOG_DIR/

Log in to the account you want the agent to use, then leave the tab open.
The Chromium profile is $HOME/.chromium-profile -- the login persists there
until the pod is recycled.
EOF
