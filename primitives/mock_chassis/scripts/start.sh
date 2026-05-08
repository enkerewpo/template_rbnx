#!/usr/bin/env bash
# Run the mock_chassis container. --network host so it shares the
# host's DDS bus with anything else that wants to subscribe to /odom.
# --ipc=host so FastRTPS shared-memory transport works between
# containers (the v0.1 webots example documents this in detail).
set -euo pipefail

CT="${ROBONIX_MOCK_CHASSIS_CONTAINER:-rbnx_mock_chassis}"
IMG="${ROBONIX_MOCK_CHASSIS_IMAGE:-mock-chassis}"

cleanup() {
  docker stop "$CT" >/dev/null 2>&1 || true
  kill -- "-$$" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Drop a stopped container from a previous run.
docker rm -f "$CT" >/dev/null 2>&1 || true

exec docker run --rm \
  --name "$CT" \
  --network host \
  --ipc=host \
  -e ROBONIX_ATLAS="${ROBONIX_ATLAS:-127.0.0.1:50051}" \
  -e ROBONIX_CAPABILITY_ID="${ROBONIX_CAPABILITY_ID:-mock_chassis}" \
  -e ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-0}" \
  -v "$(pwd)":/pkg \
  -v "$(rbnx path robonix-api)":/robonix-api:ro \
  "$IMG"
