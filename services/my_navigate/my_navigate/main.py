# SPDX-License-Identifier: MIT
"""my_navigate — service template.

Demonstrates as much of the robonix v0.1 Python API as fits in one
service:

  Lifecycle decorators
    @my_navigate.on_init       — parse cfg, validate, declare interfaces
    @my_navigate.on_activate   — find primitives, open channels, allocate threads
    @my_navigate.on_deactivate — close channels, drop heavy state
    @my_navigate.on_shutdown   — last-chance cleanup

  Discovery + connect
    ATLAS.find_capability(contract_id=..., transport=…) — returns list[Capability]
    ATLAS.find_unique_capability(...) — same but errors on 0 or >1 matches
    my_navigate.connect_capability(cap_view, contract_id, transport) — open Channel
    Channel.endpoint          — atlas-resolved topic / host:port

  Atlas declares
    my_navigate.declare_grpc(...)   — explicit gRPC declare (driver auto-declared)
    my_navigate.create_publisher(...) / my_navigate.emit(...)  — ROS 2 producer

  MCP tools
    @my_navigate.mcp("...")  — typed-input tool the LLM dispatches via pilot

  Result helpers: Ok / Err / Deferred

Replace `# TODO(planner)` with your real planner. The skeleton wires
the contract surface so every consumer (rbnx chat / scene / executor)
sees a well-formed cap regardless.
"""
from __future__ import annotations

import logging
import threading
import time
import uuid

from robonix_api import ATLAS, Service, Ok, Err, Deferred
from robonix_api.atlas_types import Transport

my_navigate = Service(id="my_navigate", namespace="robonix/service/navigation")

# Codegen-emitted typed dataclasses for the MCP tools.
from navigation_mcp import (  # noqa: E402
    Navigate_Request, Navigate_Response,
    GetNavigationStatus_Request, GetNavigationStatus_Response,
    CancelNavigation_Request, CancelNavigation_Response,
)

log = logging.getLogger("my_navigate")
logging.basicConfig(level=logging.INFO, format="[my_navigate] %(levelname)s %(message)s")


# ── module state populated by on_init / on_activate ──────────────────
_state: dict = {
    "max_linear":     0.4,
    "goal_tolerance": 0.3,
    # discovery results, filled at activate
    "chassis_cap_id": "",
    "chassis_move_endpoint": "",
    # in-flight task tracking
    "active_task_id": "",
    "active_goal":    None,
    "lock":           threading.Lock(),
}


# ── @my_navigate.mcp tools ───────────────────────────────────────────────────
# IDL shapes (lib/navigation/srv/):
#   Navigate.srv             req: geometry_msgs/PoseStamped goal
#                            resp: bool accepted, string goal_id, string status_message
#   GetNavigationStatus.srv  req: string goal_id
#                            resp: bool known, string status, bool terminal
#   CancelNavigation.srv     req: string goal_id
#                            resp: bool accepted, string status_message
@my_navigate.mcp("robonix/service/navigation/navigate")
def navigate(req: Navigate_Request) -> Navigate_Response:
    """Drive the robot to req.goal (PoseStamped). Non-blocking — returns
    a goal_id; poll progress with `status`. TODO(planner): replace the
    stub with A* / nav2 / Pure Pursuit / your favourite."""
    goal_id = str(uuid.uuid4())
    pos = req.goal.pose.position
    with _state["lock"]:
        _state["active_task_id"] = goal_id
        _state["active_goal"] = (pos.x, pos.y, pos.z)
    log.info("navigate accepted goal=%s target=(%.2f, %.2f)", goal_id, pos.x, pos.y)
    # TODO(planner): actually plan + drive. For now we just record.
    return Navigate_Response(
        accepted=True,
        goal_id=goal_id,
        status_message="stub planner accepted goal",
    )


@my_navigate.mcp("robonix/service/navigation/status")
def status(req: GetNavigationStatus_Request) -> GetNavigationStatus_Response:
    """Poll progress. Empty goal_id == latest goal."""
    with _state["lock"]:
        gid = req.goal_id or _state["active_task_id"]
        active = bool(gid) and gid == _state["active_task_id"] and _state["active_goal"] is not None
    return GetNavigationStatus_Response(
        known=bool(gid),
        status="running" if active else "idle",
        terminal=not active,
    )


@my_navigate.mcp("robonix/service/navigation/cancel")
def cancel(req: CancelNavigation_Request) -> CancelNavigation_Response:
    """Abort the active goal. Idempotent. Empty goal_id targets the active goal."""
    with _state["lock"]:
        was_active = _state["active_goal"] is not None
        _state["active_goal"] = None
        _state["active_task_id"] = ""
    return CancelNavigation_Response(
        accepted=True,
        status_message="cancelled" if was_active else "no active goal",
    )


# ── Lifecycle ────────────────────────────────────────────────────────
@my_navigate.on_init
def init(cfg: dict):
    """REGISTERED → INACTIVE. Light: parse cfg only. Don't touch
    other caps yet — they may not be online."""
    _state.update({
        k: cfg.get(k, _state[k]) for k in ("max_linear", "goal_tolerance")
    })
    log.info("init ok: max_linear=%.2f goal_tol=%.2f",
             _state["max_linear"], _state["goal_tolerance"])
    return Ok()


@my_navigate.on_activate
def activate():
    """INACTIVE → ACTIVE. Discover the chassis primitive and open
    the channel we'll use to issue motion commands. Returns
    Deferred(...) when chassis isn't online yet — rbnx boot will
    surface that to the operator and retry."""

    # 1. Discovery: every cap providing chassis/move over gRPC.
    #    ATLAS.find_capability always returns a list — possibly empty,
    #    possibly multiple. Caller decides how to pick.
    candidates = ATLAS.find_capability(
        contract_id="robonix/primitive/chassis/move",
        transport=Transport.GRPC,
    )
    if not candidates:
        return Deferred("no chassis primitive online (waiting for chassis/move)")
    cap_view = candidates[0]  # single-robot template; multi-robot deploys
                              # filter by provider_id (e.g. cap_view.provider_id == "front_chassis")
    log.info("found %d chassis candidate(s); using %s",
             len(candidates), cap_view.provider_id)

    # 2. Open a channel. The Channel context-manages the atlas
    #    bookkeeping — Capability tracks it for teardown, so even
    #    if we never explicitly close, atlas drops the edge when
    #    we shut down.
    ch = my_navigate.connect_capability(
        cap_view,
        "robonix/primitive/chassis/move",
        Transport.GRPC,
    )
    _state["chassis_cap_id"] = cap_view.provider_id
    _state["chassis_move_endpoint"] = ch.endpoint
    log.info("connected to %s @ %s", cap_view.provider_id, ch.endpoint)

    # 3. (Optional) declare any extra contracts we expose beyond the
    #    auto-declared MCP tools. Skipped here — the four
    #    navigation/* contracts are auto-declared by @my_navigate.mcp / the
    #    Capability framework.

    return Ok()


@my_navigate.on_deactivate
def deactivate():
    """ACTIVE → INACTIVE. Drop the chassis channel, cancel any active
    task. Idempotent."""
    with _state["lock"]:
        _state["active_goal"] = None
        _state["active_task_id"] = ""
        _state["chassis_cap_id"] = ""
        _state["chassis_move_endpoint"] = ""
    # Channels we opened with my_navigate.connect_capability are auto-closed by the
    # Capability framework; nothing to do here.
    log.info("deactivated")
    return Ok()


@my_navigate.on_shutdown
def shutdown():
    log.info("shutdown")


def main() -> int:
    my_navigate.run()
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
