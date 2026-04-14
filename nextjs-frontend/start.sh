#!/bin/bash
set -e
mkdir -p .next/dev/logs

pnpm run dev &

node watcher.js

wait