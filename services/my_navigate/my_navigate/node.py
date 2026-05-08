# SPDX-License-Identifier: MIT
"""my_navigate — service template.

Demonstrates as much of the robonix v0.1 Python API as fits in one
service:

  Lifecycle decorators
    @cap.on_init       — parse cfg, validate, declare interfaces
    @cap.on_activate   — find primitives, open channels, allocate threads
    @cap.on_deactivate — close channels, drop heavy state
    @cap.on_shutdown   — last-chance cleanup

  Discovery + connect
    cap.find(...)           — list candidates
    cap.find_one(...)       — first match (auto-fail when None)
    cap.connect(...)        — open Channel context manager
    Channel.endpoint        — atlas-resolved topic / host:port

  Atlas declares
    cap.declare_grpc(...)   — explicit gRPC declare (driver auto-declared)
    cap.create_publisher(...) / cap.emit(...)  — ROS 2 producer

  MCP tools
    @cap.mcp("...")  — typed-input tool the LLM dispatches via pilot

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

from robonix_api import Capability, Ok, Err, Deferred
from robonix_api.atlas_types import Transport

cap = Capability(id="my_navigate", namespace="robonix/service/navigation")

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


# ── @cap.mcp tools ───────────────────────────────────────────────────
@cap.mcp("robonix/service/navigation/navigate")
def navigate(req: Navigate_Request) -> Navigate_Response:
    """Drive the robot to (x, y, [yaw]). Non-blocking — returns a
    task_id; poll with `status`. TODO(planner): replace the stub with
    A* / nav2 / Pure Pursuit / your favourite."""
    task_id = str(uuid.uuid4())
    with _state["lock"]:
        _state["active_task_id"] = task_id
        _state["active_goal"] = (req.target_x, req.target_y, req.target_yaw)
    log.info("navigate accepted task=%s target=(%.2f, %.2f)",
             task_id, req.target_x, req.target_y)
    # TODO(planner): actually plan + drive. For now we just record.
    return Navigate_Response(accepted=True, task_id=task_id, message="stub planner")


@cap.mcp("robonix/service/navigation/status")
def status(req: GetNavigationStatus_Request) -> GetNavigationStatus_Response:
    """Poll progress. Empty task_id == latest task."""
    with _state["lock"]:
        tid = req.task_id or _state["active_task_id"]
        running = tid and tid == _state["active_task_id"] and _state["active_goal"] is not None
    return GetNavigationStatus_Response(
        known=bool(tid),
        state="running" if running else "idle",
        progress=0.0 if running else 1.0,
        eta_s=-1.0,
        detail="stub planner",
    )


@cap.mcp("robonix/service/navigation/cancel")
def cancel(req: CancelNavigation_Request) -> CancelNavigation_Response:
    """Abort the active task. Idempotent."""
    with _state["lock"]:
        was_running = _state["active_goal"] is not None
        _state["active_goal"] = None
        _state["active_task_id"] = ""
    return CancelNavigation_Response(ok=True, message=
        "cancelled" if was_running else "no active task")


# ── Lifecycle ────────────────────────────────────────────────────────
@cap.on_init
def init(cfg: dict):
    """REGISTERED → INITIALIZED. Light: parse cfg only. Don't touch
    other caps yet — they may not be online."""
    _state.update({
        k: cfg.get(k, _state[k]) for k in ("max_linear", "goal_tolerance")
    })
    log.info("init ok: max_linear=%.2f goal_tol=%.2f",
             _state["max_linear"], _state["goal_tolerance"])
    return Ok()


@cap.on_activate
def activate():
    """INITIALIZED → RUNNABLE. Discover the chassis primitive and open
    the channel we'll use to issue motion commands. Returns
    Deferred(...) when chassis isn't online yet — rbnx boot will
    surface that to the operator and (in v0.2) retry."""

    # 1. Discovery: any cap providing chassis/move over gRPC?
    rec = cap.find_one(
        contract_id="robonix/primitive/chassis/move",
        transport=Transport.GRPC,
    )
    if rec is None:
        return Deferred("no chassis primitive online (waiting for chassis/move)")

    # 2. Optional: list every chassis-providing cap. Multi-robot
    #    deploys would pick by cap_id (cap_id == device_id convention).
    all_chassis = cap.find(contract_id="robonix/primitive/chassis/move")
    log.info("found %d chassis candidate(s); using %s",
             len(all_chassis), rec.capability_id)

    # 3. Open a channel. The Channel context-manages the atlas
    #    bookkeeping — Capability tracks it for teardown, so even
    #    if we never explicitly close, atlas drops the edge when
    #    we shut down.
    ch = cap.connect(
        contract_id="robonix/primitive/chassis/move",
        transport=Transport.GRPC,
        capability_id=rec.capability_id,
    )
    _state["chassis_cap_id"] = rec.capability_id
    _state["chassis_move_endpoint"] = ch.endpoint
    log.info("connected to %s @ %s", rec.capability_id, ch.endpoint)

    # 4. (Optional) declare any extra contracts we expose beyond the
    #    auto-declared MCP tools. Skipped here — the four
    #    navigation/* contracts are auto-declared by @cap.mcp / the
    #    Capability framework.

    return Ok()


@cap.on_deactivate
def deactivate():
    """RUNNABLE → INITIALIZED. Drop the chassis channel, cancel any
    active task. Idempotent."""
    with _state["lock"]:
        _state["active_goal"] = None
        _state["active_task_id"] = ""
        _state["chassis_cap_id"] = ""
        _state["chassis_move_endpoint"] = ""
    # Channels we opened with cap.connect are auto-closed by the
    # Capability framework; nothing to do here.
    log.info("deactivated")
    return Ok()


@cap.on_shutdown
def shutdown():
    log.info("shutdown")


def main() -> int:
    cap.run()
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
