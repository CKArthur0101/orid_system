#!/bin/sh

set -eu

pnpm run build
exec pnpm exec next start --hostname 0.0.0.0 --port 3000
