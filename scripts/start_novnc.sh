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

# The pod is recycled often, which wipes the apt packages this needs. Reinstall them
# here so a start after a recycle does not fail with a black screen and no clue why.
for bin in Xvfb x11vnc websockify chromium; do
  command -v "$bin" >/dev/null 2>&1 || {
    echo "installing $bin ..."
    sudo apt-get update -qq >/dev/null 2>&1
    sudo apt-get install -y -qq xvfb x11vnc websockify novnc chromium >/dev/null 2>&1
    break
  }
done
LOG_DIR="${HOME}/.novnc"
VNC_PASS_FILE="${HOME}/.vnc/passwd"
VNC_PASSWORD_FILE="${HOME}/.vnc/password"
CHROME_PROFILE="${CHROME_PROFILE:-$HOME/.chromium-profile}"
mkdir -p "$LOG_DIR" "$(dirname "$VNC_PASS_FILE")"

# One password, kept. If the caller sets VNC_PASSWORD that wins; otherwise reuse the
# saved one so it survives a restart and a recycle. Regenerating each time would mean
# telling the owner a new password on every start, and the old one silently failing.
if [ -z "${VNC_PASSWORD:-}" ]; then
  if [ -s "$VNC_PASSWORD_FILE" ]; then
    VNC_PASSWORD="$(cat "$VNC_PASSWORD_FILE")"
  else
    VNC_PASSWORD="$(python3 -c 'import secrets,string;print("".join(secrets.choice(string.ascii_letters+string.digits) for _ in range(8)))')"
  fi
fi
printf '%s' "$VNC_PASSWORD" > "$VNC_PASSWORD_FILE"
export VNC_PASSWORD

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

# Rewrite every start, not only when missing: the script prints a new password each
# run, so a password file left from an earlier run would not match what is shown and
# the owner would be locked out with no clue why.
x11vnc -storepasswd "$VNC_PASSWORD" "$VNC_PASS_FILE" >/dev/null 2>&1

if ! running "x11vnc -display $DISPLAY_NUM"; then
  echo "starting x11vnc"
  # Xvfb runs with -ac (access control off), so there is no cookie to find and
  # -auth guess fails with "file ~/.Xauthority does not exist". /dev/null is the
  # correct auth file in that case.
  setsid x11vnc -display "$DISPLAY_NUM" -auth /dev/null -rfbauth "$VNC_PASS_FILE" \
    -forever -shared -rfbport 5900 -quiet >"$LOG_DIR/x11vnc.log" 2>&1 </dev/null &
  sleep 3
fi

# x11vnc can die while websockify stays up, and noVNC then shows a black screen
# instead of an error. Check the socket, not just the process name.
if ! running "x11vnc -display $DISPLAY_NUM" || \
   ! python3 -c "import socket,sys;s=socket.socket();s.settimeout(2);sys.exit(0 if s.connect_ex(('127.0.0.1',5900))==0 else 1)"; then
  echo "x11vnc not serving; restarting"
  pkill -9 -f "x11vnc -display $DISPLAY_NUM" 2>/dev/null
  sleep 1
  setsid x11vnc -display "$DISPLAY_NUM" -auth /dev/null -rfbauth "$VNC_PASS_FILE" \
    -forever -shared -rfbport 5900 -quiet >"$LOG_DIR/x11vnc.log" 2>&1 </dev/null &
  sleep 3
fi

# noVNC's viewer drops ("จอหลุด", K 2026-11-12) when the websocket server is not the one
# serving the port -- e.g. a stale websockify left from an earlier run. Decide by the
# LISTENING socket, not by process count: websockify forks a child, so `pgrep` sees two
# for a single healthy instance.
if ! python3 -c "import socket,sys;s=socket.socket();s.settimeout(2);sys.exit(0 if s.connect_ex(('127.0.0.1',$PORT))==0 else 1)"; then
  echo "port $PORT not served; (re)starting websockify + noVNC"
  pkill -9 -f "websockify --web=/usr/share/novnc" 2>/dev/null
  sleep 2
  setsid websockify --web=/usr/share/novnc "$PORT" localhost:5900 \
    >"$LOG_DIR/websockify.log" 2>&1 </dev/null &
  sleep 3
fi

if ! running "remote-debugging-port=9222"; then
  # Thai glyphs render as boxes ("สี่เหลี่ยม", K 2026-11-12) without a Thai font; the base
  # image ships only DejaVu. Install on the fly, like ffmpeg.
  if ! fc-list 2>/dev/null | grep -qiE "thai|tlwg"; then
    echo "installing Thai fonts"
    (sudo apt-get update -qq && sudo apt-get install -y -qq fonts-thai-tlwg fonts-noto-core) >/dev/null 2>&1 \
      || apt-get install -y -qq fonts-thai-tlwg >/dev/null 2>&1 || true
    fc-cache -f >/dev/null 2>&1 || true
  fi
  echo "starting chromium (CDP on 9222)"
  setsid env DISPLAY="$DISPLAY_NUM" chromium \
    --no-sandbox --disable-dev-shm-usage \
    --remote-debugging-port=9222 --remote-allow-origins='*' \
    --user-data-dir="$CHROME_PROFILE" \
    --window-size=1440,900 --start-maximized \
    --lang=th-TH \
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
