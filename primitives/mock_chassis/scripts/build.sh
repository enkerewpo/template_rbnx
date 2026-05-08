#!/usr/bin/env bash
# mock_chassis build — codegen + docker image.
set -euo pipefail
PKG="${RBNX_PACKAGE_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$PKG"

CLEAN="${RBNX_BUILD_CLEAN:-}"

# 1. rbnx codegen: emits the proto stubs the cap imports at runtime
#    into <pkg>/rbnx-build/codegen/{proto_gen,robonix_mcp_types}/.
FLAGS=()
[[ "$CLEAN" == "1" ]] && FLAGS+=(--clean)
rbnx codegen -p "$PKG" "${FLAGS[@]}"

# 2. Docker image. Bind-mounted package dir means we don't have to
#    bake source into the image — only the ROS 2 base + Python deps.
if ! command -v docker >/dev/null 2>&1; then
  echo "[build] error: docker not found on PATH" >&2
  exit 1
fi
DOCKER_FLAGS=()
[[ "$CLEAN" == "1" ]] && DOCKER_FLAGS+=(--no-cache)
docker build "${DOCKER_FLAGS[@]}" \
  -f docker/Dockerfile \
  -t mock-chassis docker/

echo "[build] done."
