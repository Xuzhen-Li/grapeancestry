#!/usr/bin/env bash
# GrapeAncestry v1.0.0 launcher (customer drop or this repo root).
# Private fat image: grapeancestry:1.0.0 (linux/amd64). Never docker push (panel inside).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

IMAGE="grapeancestry:1.0.0"
NAME="grapeancestry"
TAR="grapeancestry-v1.0.0-amd64.tar"

mkdir -p input output settings

# Colima: if default socket exists and docker info fails, point DOCKER_HOST there.
if [[ -S "${HOME}/.colima/default/docker.sock" ]]; then
  if ! docker info >/dev/null 2>&1; then
    export DOCKER_HOST="unix://${HOME}/.colima/default/docker.sock"
  fi
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required. Install Docker Desktop (linux/amd64 engine on Apple Silicon)." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker is not running (or DOCKER_HOST is wrong). Start Docker Desktop / Colima, then retry." >&2
  exit 1
fi

ensure_image() {
  if docker image inspect "$IMAGE" >/dev/null 2>&1; then
    return 0
  fi
  if [[ -f "$TAR" ]]; then
    echo "Loading $TAR → $IMAGE …"
    docker load -i "$TAR"
    return 0
  fi
  echo "Image $IMAGE not found and $TAR is missing."
  echo "Honest note: a docs-only GitHub clone cannot produce a working fat image"
  echo "(no VS-1, no 2449 panel inside a public build). Place $TAR next to this script,"
  echo "or obtain grapeancestry:1.0.0 privately. Attempting docker build anyway will not"
  echo "yield Analyze that finishes without private assets."
  if [[ -f Dockerfile ]]; then
    echo "Trying docker build --platform linux/amd64 (expected incomplete without private layers)…"
    docker build --platform linux/amd64 -t "$IMAGE" .
  else
    exit 1
  fi
}

ensure_image

# Stop a previous container with the same name (idempotent restart).
if docker ps -a --format '{{.Names}}' | grep -qx "$NAME"; then
  docker rm -f "$NAME" >/dev/null 2>&1 || true
fi

echo "Starting $NAME ($IMAGE) on :8501 (UI) and :8502 (reports)…"
docker run -d --name "$NAME" \
  -p 8501:8501 -p 8502:8502 \
  -v "$ROOT/input:/input" \
  -v "$ROOT/output:/output" \
  -v "$ROOT/settings:/settings" \
  "$IMAGE"

echo "UI:     http://127.0.0.1:8501"
echo "Report: http://127.0.0.1:8502"
echo "Folders: $ROOT/input  $ROOT/output  $ROOT/settings"

# Best-effort open browser (macOS / Linux / WSL often have xdg-open).
if command -v open >/dev/null 2>&1; then
  open "http://127.0.0.1:8501" >/dev/null 2>&1 || true
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "http://127.0.0.1:8501" >/dev/null 2>&1 || true
fi
