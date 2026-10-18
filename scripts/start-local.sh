#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if ! command -v docker >/dev/null 2>&1; then
  echo 'Docker is unavailable. Start Docker Desktop and enable WSL integration for this distribution.' >&2
  exit 1
fi
docker info >/dev/null
docker compose up -d --wait
echo 'FalkorDB database: localhost:6379'
echo 'FalkorDB Browser: http://localhost:3000'
echo 'Verify application access with: .venv/bin/python -m swarmlab doctor'
