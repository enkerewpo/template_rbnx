#!/usr/bin/env bash
set -euo pipefail
PKG="${RBNX_PACKAGE_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"

# --mcp because this service exposes MCP tools (navigate / status /
# cancel). Without the flag, robonix_mcp_types/ wouldn't be generated
# and @cap.mcp(...) wouldn't find the typed Request/Response classes.
FLAGS=(--mcp)
[[ "${RBNX_BUILD_CLEAN:-}" == "1" ]] && FLAGS+=(--clean)
rbnx codegen -p "$PKG" "${FLAGS[@]}"
echo "[build] done."
