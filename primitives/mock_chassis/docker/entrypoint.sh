#!/usr/bin/env bash
# Container entrypoint. Sources ROS 2 humble, sets PYTHONPATH so the
# cap can import codegen output + robonix_api, then exec's the node.
set -eo pipefail

# shellcheck disable=SC1091
source /opt/ros/humble/setup.bash

cd /pkg

# robonix_api lives on the host at `rbnx path robonix-api` and is
# bind-mounted at /robonix-api by start.sh. Codegen output lives
# under /pkg/rbnx-build/codegen/ (rbnx codegen v0.1 default) — the
# Capability constructor walks up to find it, so we only need
# robonix_api itself + the package src on PYTHONPATH.
export PYTHONPATH="/robonix-api:/pkg:${PYTHONPATH:-}"

exec python3 -m mock_chassis.node
