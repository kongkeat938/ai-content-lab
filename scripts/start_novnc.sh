#!/usr/bin/env bash
# Start a headless desktop on the pod and serve it over a work URL, so a person
# with a browser can sign in to a site (Google, YouTube Studio, ...) once and leave
# the session signed in for the agent to drive.
#
# Why: some logins cannot be done by an agent -- Google turns away the pod's
# headless browser ("This browser or app may not be secure", measured 2026-11-08).
# A real Chromium in a real X session is not turned away, so the owner signs in
# through a VNC view of that session, and the agent then drives the same browser
# over the DevTools protocol. This is the path that needs no machine of K's.
#
#   Xvfb        virtual 1440x900 display on :99
#   x11vnc      shares :99
#   websockify  serves noVNC + the VNC socket on $PORT (default 12001 = work-2)
#   chromium    on that display, with --remote-debugging-port for the agent
#
# Free tools only. Idempotent: an already-running part is left alone.
#
#   scripts/start_novnc.sh [port]
#   scripts/start_novnc.sh --stop
#
# Then open:  <work-2 URL>/vnc_lite.html   (or /vnc.html)
set -u

if [ "${1:-}" = "--stop" ]; then
  for pat in "websockify --web=/usr/share/novnc" "x11vnc -display :99" \
             "remote-debugging-port=9222" "Xvfb :99"; do
    pkill -9 -f "$pat" 2>/dev/null
  done
  sleep 1
  rm -f /tmp/.X99-lock
  echo "stopped"
  exit 0
fi

PORT="${1:-12001}"
DISPLAY_NUM=":99"
SCREEN="1440x900x24"
LOG_DIR="${HOME}/.novnc"
VNC_PASS_FILE="${HOME}/.vnc/passwd"
VNC_PASSWORD="${VNC_PASSWORD:-contentlab}"
CHROME_PROFILE="${CHROME_PROFILE:-$HOME/.chromium-profile}"
mkdir -p "$LOG_DIR" "$(dirname "$VNC_PASS_FILE")"

running() { pgrep -f "$1" >/dev/null 2>&1; }

# A stale lock from a killed Xvfb makes the next start fail with "already active".
if [ -e "/tmp/.X${DISPLAY_NUM#:}-lock" ] && ! running "Xvfb $DISPLAY_NUM"; then
  rm -f "/tmp/.X${DISPLAY_NUM#:}-lock"
fi

if ! running "Xvfb $DISPLAY_NUM"; then
  echo "starting Xvfb on $DISPLAY_NUM"
  setsid Xvfb "$DISPLAY_NUM" -screen 0 "$SCREEN" -ac -nolisten tcp \
    >"$LOG_DIR/xvfb.log" 2>&1 </dev/null &
  sleep 3
fi

if [ ! -f "$VNC_PASS_FILE" ]; then
  x11vnc -storepasswd "$VNC_PASSWORD" "$VNC_PASS_FILE" >/dev/null 2>&1
fi

if ! running "x11vnc -display $DISPLAY_NUM"; then
  echo "starting x11vnc"
  # -auth guess finds the X server's cookie wherever this distro keeps it.
  setsid x11vnc -display "$DISPLAY_NUM" -auth guess -rfbauth "$VNC_PASS_FILE" \
    -forever -shared -rfbport 5900 -quiet >"$LOG_DIR/x11vnc.log" 2>&1 </dev/null &
  sleep 3
fi

if ! running "websockify --web=/usr/share/novnc"; then
  echo "starting websockify + noVNC on :$PORT"
  setsid websockify --web=/usr/share/novnc "$PORT" localhost:5900 \
    >"$LOG_DIR/websockify.log" 2>&1 </dev/null &
  sleep 3
fi

if ! running "remote-debugging-port=9222"; then
  echo "starting chromium (CDP on 9222)"
  setsid env DISPLAY="$DISPLAY_NUM" chromium \
    --no-sandbox --disable-dev-shm-usage \
    --remote-debugging-port=9222 --remote-allow-origins='*' \
    --user-data-dir="$CHROME_PROFILE" \
    --window-size=1440,900 --start-maximized \
    --no-first-run --no-default-browser-check \
    "https://accounts.google.com/signin" >"$LOG_DIR/chromium.log" 2>&1 </dev/null &
  sleep 6
fi

echo
echo "noVNC is up."
echo "  Open:  \$WORK_HOST_2/vnc_lite.html   (simple)  or  /vnc.html"
echo "  VNC password:  $VNC_PASSWORD"
echo "  CDP for the agent:  http://localhost:9222/json/version"
echo "  Logs:  $LOG_DIR/"
echo "  Sign in, then leave the tab open. Profile: $CHROME_PROFILE"
