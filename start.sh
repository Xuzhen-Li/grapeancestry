#!/usr/bin/env bash
# GrapeAncestry v1.0.0 launcher (customer drop or this repo root).
# Private fat image: grapeancestry:1.0.0 (linux/amd64). NEVER docker push (panel inside).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

IMAGE="grapeancestry:1.0.0"
NAME="grapeancestry"
TAR="grapeancestry-v1.0.0-amd64.tar"
ALLOW_INCOMPLETE="${ALLOW_INCOMPLETE:-0}"

mkdir -p input output settings
# Host uid (e.g. 501 on macOS) must write auth.json; image default mambauser may differ.
chmod a+rwx input output settings 2>/dev/null || true

# Colima sockets
if [[ -S "${HOME}/.colima/default/docker.sock" ]]; then
  if ! docker info >/dev/null 2>&1; then
    export DOCKER_HOST="unix://${HOME}/.colima/default/docker.sock"
  fi
elif [[ -S "${HOME}/.colima/docker.sock" ]]; then
  if ! docker info >/dev/null 2>&1; then
    export DOCKER_HOST="unix://${HOME}/.colima/docker.sock"
  fi
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "STOP: Docker is required. Install Docker Desktop (linux/amd64 engine on Apple Silicon)." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "STOP: Docker is not running (or DOCKER_HOST is wrong). Start Docker Desktop / Colima, then retry." >&2
  exit 1
fi

image_ok() {
  docker image inspect "$IMAGE" >/dev/null 2>&1
}

ensure_image() {
  if image_ok; then
    return 0
  fi
  if [[ -f "$TAR" ]]; then
    echo "Loading $TAR …"
    docker load -i "$TAR"
    if ! image_ok; then
      echo "STOP: Loaded $TAR but image tag $IMAGE is still missing. Check the tar contents." >&2
      exit 1
    fi
    return 0
  fi
  echo "Image $IMAGE not found and $TAR is missing."
  echo "A docs-only GitHub clone cannot produce a working fat image (no VS-1 / 2449 panel)."
  if [[ ! -f Dockerfile ]]; then
    echo "STOP: No Dockerfile and no tar." >&2
    exit 1
  fi
  if [[ "$ALLOW_INCOMPLETE" != "1" ]]; then
    echo "STOP: Refusing docker build+run without the fat tar (Analyze would fail)." >&2
    echo "Place $TAR next to this script, or set ALLOW_INCOMPLETE=1 to force an incomplete build." >&2
    exit 1
  fi
  echo "ALLOW_INCOMPLETE=1 — building incomplete image (expected: Analyze stops without private assets)…"
  docker build --platform linux/amd64 -t "$IMAGE" .
  if ! image_ok; then
    echo "STOP: docker build did not produce $IMAGE." >&2
    exit 1
  fi
}

ensure_image

if docker ps -a --format '{{.Names}}' | grep -qx "$NAME"; then
  docker rm -f "$NAME" >/dev/null 2>&1 || true
fi

HOST_UID="$(id -u)"
HOST_GID="$(id -g)"

echo "Starting $NAME ($IMAGE) on :8501 (UI) and :8502 (reports) as ${HOST_UID}:${HOST_GID}…"
echo "NEVER docker push $IMAGE (panel assets inside)."
docker run -d --name "$NAME" \
  --user "${HOST_UID}:${HOST_GID}" \
  -e HOME=/tmp \
  -p 8501:8501 -p 8502:8502 \
  -v "$ROOT/input:/input" \
  -v "$ROOT/output:/output" \
  -v "$ROOT/settings:/settings" \
  "$IMAGE"

echo "UI:     http://127.0.0.1:8501"
echo "Report: http://127.0.0.1:8502"
echo "Folders: $ROOT/input  $ROOT/output  $ROOT/settings"

if command -v open >/dev/null 2>&1; then
  open "http://127.0.0.1:8501" >/dev/null 2>&1 || true
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "http://127.0.0.1:8501" >/dev/null 2>&1 || true
fi
