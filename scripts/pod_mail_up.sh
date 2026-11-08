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
# Random each start, so a recycled pod never reuses an old password. Shown below.
VNC_PASSWORD="${VNC_PASSWORD:-$(python3 -c 'import secrets;print(secrets.token_urlsafe(6))')}"
CHROME_PROFILE="${CHROME_PROFILE:-$HOME/.chromium-profile}"
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
