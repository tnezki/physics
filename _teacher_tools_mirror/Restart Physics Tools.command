#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PORT=8768
PID="$(lsof -tiTCP:${PORT} -sTCP:LISTEN 2>/dev/null | head -1 || true)"
if [ -n "$PID" ]; then kill "$PID" 2>/dev/null || true; sleep 1; fi
nohup /usr/bin/python3 "$ROOT/app/server.py" > "$ROOT/runtime/physics_tools.log" 2>&1 &
for i in $(seq 1 30); do
  if /usr/bin/curl -fsS "http://127.0.0.1:${PORT}/api/version" 2>/dev/null | /usr/bin/grep -q '1.0-physics-tools'; then
    /usr/bin/open "http://127.0.0.1:${PORT}/?t=$(date +%s)"
    exit 0
  fi
  sleep .2
done
echo "Physics Tools did not start. See $ROOT/runtime/physics_tools.log"
read -r -p "Press Return to close..." _
