#!/usr/bin/env bash
set -euo pipefail

root_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$root_dir"

case "${1:-up}" in
  down)
    docker compose down
    exit 0
    ;;
  up)
    command -v docker >/dev/null 2>&1 || { echo "Docker is required." >&2; exit 1; }
    command -v curl >/dev/null 2>&1 || { echo "curl is required." >&2; exit 1; }
    docker info >/dev/null 2>&1 || { echo "Docker Desktop is not running." >&2; exit 1; }
    if [[ ! -f .env ]]; then
      echo "Missing .env. Copy .env.example to .env and add JEV_API_KEY." >&2
      exit 1
    fi
    docker compose up -d --build
    for attempt in {1..60}; do
      if curl -fsS http://localhost:8787/api/config >/dev/null 2>&1; then
        echo "Jev Anything is ready: http://localhost:8787"
        if command -v open >/dev/null 2>&1; then
          open http://localhost:8787
        fi
        exit 0
      fi
      sleep 1
    done
    echo "The workbench did not become ready. Check: docker compose logs" >&2
    exit 1
    ;;
  *)
    echo "Usage: $0 [up|down]" >&2
    exit 2
    ;;
esac
