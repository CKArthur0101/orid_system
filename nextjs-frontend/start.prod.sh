#!/bin/sh

set -eu

cd /app

# Rebuilding on every container start leaves port 3200 dead until Next finishes,
# which makes ngrok return 502 after every Windows/Docker reboot.
if [ ! -f .next/BUILD_ID ]; then
  pnpm run build
fi

exec pnpm exec next start --hostname 0.0.0.0 --port 3000
