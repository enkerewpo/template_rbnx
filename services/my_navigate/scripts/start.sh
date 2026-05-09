#!/usr/bin/env bash
set -eo pipefail
PKG_ROOT="${RBNX_PACKAGE_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$PKG_ROOT"

# robonix_api lives in the workspace pylib dir; expose it on PYTHONPATH
# so `from robonix_api import Capability` resolves. Capability's
# constructor walks up to find the codegen output in
# `rbnx-build/codegen/`, so we don't add those paths manually.
export PYTHONPATH="$(rbnx path robonix-api):$PKG_ROOT:${PYTHONPATH:-}"

exec python3 -m my_navigate.main
