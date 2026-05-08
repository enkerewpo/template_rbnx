#!/usr/bin/env bash
set -euo pipefail
PKG="${RBNX_PACKAGE_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"

# --mcp because @cap.mcp tools need typed Request/Response classes
# under robonix_mcp_types/. rbnx codegen also picks up this package's
# own capabilities/ tree (driver + say.v1.toml + lib/say_hello/srv/)
# so the generated proto contains a SkillSayHelloSay servicer.
FLAGS=(--mcp)
[[ "${RBNX_BUILD_CLEAN:-}" == "1" ]] && FLAGS+=(--clean)
rbnx codegen -p "$PKG" "${FLAGS[@]}"
echo "[build] done."
