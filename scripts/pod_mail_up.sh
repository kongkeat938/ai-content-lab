#!/usr/bin/env bash
# Bring the pod's mail-sign-in desktop up in one command, from a cold pod.
#
# The pod is recycled often and loses every installed package and running process,
# so this installs what it needs, starts the desktop, and prints the one link the
# owner has to open. Run it again after a recycle; it is idempotent.
#
#   scripts/pod_mail_up.sh [port]
#
# What it gives the owner: a real Chromium, on a virtual display, viewable over
# noVNC. Google turns away the pod's headless browser but not this one, so signing
# in here works -- and the agent can then drive the same browser over CDP.
set -u

PORT="${1:-12001}"
DISPLAY_NUM=":99"
LOG_DIR="${HOME}/.novnc"
VNC_PASS_FILE="${HOME}/.vnc/passwd"
# Keep one password across restarts. A new random password on every start means the
# owner has to be told a new one each time, and an old one silently stops working.
# If a password file exists it wins, so the same password keeps working after a
# recycle. The password is short by necessity -- VNC ignores everything past the
# eighth character.
VNC_PASS_FILE="${HOME}/.vnc/passwd"
VNC_PASSWORD_FILE="${HOME}/.vnc/password"
if [ -n "${VNC_PASSWORD:-}" ]; then
  :                                   # caller overrode it explicitly
elif [ -s "$VNC_PASSWORD_FILE" ]; then
  VNC_PASSWORD="$(cat "$VNC_PASSWORD_FILE")"
else
  VNC_PASSWORD="$(python3 -c 'import secrets,string;print("".join(secrets.choice(string.ascii_letters+string.digits) for _ in range(8)))')"
fi
mkdir -p "$(dirname "$VNC_PASSWORD_FILE")"
printf '%s' "$VNC_PASSWORD" > "$VNC_PASSWORD_FILE"
export VNC_PASSWORD

echo "STEP=packages"
missing=""
for t in Xvfb x11vnc websockify chromium; do
  command -v "$t" >/dev/null 2>&1 || missing="$missing $t"
done
[ -f /usr/share/novnc/vnc_lite.html ] || missing="$missing novnc"
if [ -n "$missing" ]; then
  echo "  installing:$missing"
  sudo apt-get update -qq
  sudo apt-get install -y -qq xvfb x11vnc novnc websockify chromium 2>&1 | tail -2
else
  echo "  all present"
fi

echo "STEP=python"
python3 -c "import websocket" 2>/dev/null || pip install -q websocket-client

echo "STEP=desktop"
mkdir -p "$LOG_DIR" "$(dirname "$VNC_PASS_FILE")"
# Full restart, so the VNC password file is rewritten and x11vnc picks it up. A
# running x11vnc keeps whatever password it started with, and a stale one would not
# match the password printed below.
bash "$(dirname "$0")/start_novnc.sh" --stop >/dev/null 2>&1 || true
sleep 1
rm -f "/tmp/.X${DISPLAY_NUM#:}-lock"
bash "$(dirname "$0")/start_novnc.sh" "$PORT" | sed 's/^/  /'

echo
echo "STEP=verify"
sleep 2
code=$(curl -s -o /dev/null -w '%{http_code}' -m 8 "http://localhost:${PORT}/vnc_lite.html" || echo 000)
cdp=$(curl -s -o /dev/null -w '%{http_code}' -m 8 "http://localhost:9222/json/version" || echo 000)
echo "  noVNC local  = $code"
echo "  Chromium CDP = $cdp"
echo
echo "READY=$([ "$code" = 200 ] && [ "$cdp" = 200 ] && echo yes || echo no)"
echo "VNC_PASSWORD=$VNC_PASSWORD"
echo "OPEN= https://work-2-nqwmwzbszrmrirmy.prod-runtime.all-hands.dev/vnc_lite.html"
