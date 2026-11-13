#!/usr/bin/env bash
# Print the noVNC link and password, restarting the stack if it is not serving.
#
# The pod is recycled often, and a recycle kills Xvfb/x11vnc/websockify/chromium --
# so the work URL answers 502 and the owner sees a dead link. This checks the local
# socket and, if it is down, starts the stack again before printing the details, so
# one command recovers the hand-off.
#
#   scripts/vnc_link.sh            # status + link + password (starts it if down)
#   scripts/vnc_link.sh --restart  # force a restart
set -u
cd "$(dirname "$0")/.."

PORT=12001
FORCE=0
case "${1:-}" in
  ""|--restart) [ "${1:-}" = "--restart" ] && FORCE=1 ;;
  *) PORT="$1" ;;
esac
HOST="${WORK_HOST_2:-work-2-untoypfpfjgkquuf.prod-runtime.all-hands.dev}"

restart() {
  bash scripts/start_novnc.sh "$PORT" >/dev/null 2>&1
}

if [ "$FORCE" = 1 ]; then
  restart
elif ! curl -s -o /dev/null -m 5 "http://127.0.0.1:${PORT}/vnc_lite.html"; then
  echo "noVNC is down (recycled pod?) -- restarting"
  restart
fi

# Keep the password stable across restarts: start_novnc.sh reuses ~/.vnc/password.
if [ -s "$HOME/.vnc/password" ]; then
  VNC_PASSWORD="$(cat "$HOME/.vnc/password")"
fi
export VNC_PASSWORD="${VNC_PASSWORD:-akwork2026}"

curl -s -o /dev/null -m 6 "http://127.0.0.1:${PORT}/vnc_lite.html" \
  && state="up" || state="DOWN"

echo "state:    $state"
echo "link:     https://${HOST}/vnc_lite.html"
echo "password: $VNC_PASSWORD"
echo "CDP:      http://127.0.0.1:9222/json/version  (for the agent)"
