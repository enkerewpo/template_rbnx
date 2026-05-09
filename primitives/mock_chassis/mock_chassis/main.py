# SPDX-License-Identifier: MIT
"""mock_chassis — primitive template.

Demonstrates:
  * Capability + on_init / on_activate lifecycle decorators.
  * Declaring built-in `robonix/primitive/chassis/*` contracts (no
    package-local .toml — primitives reuse the canonical surface).
  * @cap.grpc handler for chassis/move (typed against codegen-emitted
    Request/Response classes).
  * ROS 2 publisher for chassis/odom + subscription for chassis/twist_in.

Replace the bodies marked TODO with your real chassis code. The
contract surface stays the same so service consumers don't need to
care which physical chassis is mounted.
"""
from __future__ import annotations

import logging
import math
import threading
import time

from robonix_api import Capability, Ok, Err, Deferred

cap = Capability(id="mock_chassis", namespace="robonix/primitive/chassis")

import chassis_pb2          # type: ignore  # noqa: E402  (codegen)
import nav_msgs_pb2         # type: ignore  # noqa: E402
from geometry_msgs.msg import Twist  # noqa: E402
from nav_msgs.msg import Odometry    # noqa: E402

log = logging.getLogger("mock_chassis")
logging.basicConfig(level=logging.INFO, format="[mock_chassis] %(levelname)s %(message)s")


# ── module state populated by on_init ────────────────────────────────
_state = {
    "odom_frame":      "odom",
    "base_frame":      "base_link",
    "odom_rate_hz":    20.0,
    "circle_radius_m": 0.0,
    "x":               0.0,
    "y":               0.0,
    "yaw":             0.0,
    "vx":              0.0,
    "wz":              0.0,
    "last_t":          0.0,
}

_pub_thread: threading.Thread | None = None
_stop = threading.Event()


# ── @cap.grpc: chassis/move RPC ──────────────────────────────────────
@cap.grpc("robonix/primitive/chassis/move")
def move(req, ctx):
    """One-shot move command. TODO: replace with your real chassis
    motion controller. Stub just records the velocity and returns ok."""
    _state["vx"] = float(req.linear_x)
    _state["wz"] = float(req.angular_z)
    log.info("move: linear=%.2f angular=%.2f", _state["vx"], _state["wz"])
    return chassis_pb2.ExecuteMoveCommand_Response(success=True)


# ── ROS 2 subscription: chassis/twist_in (consumers publish to drive) ─
def _on_twist(msg: Twist) -> None:
    _state["vx"] = msg.linear.x
    _state["wz"] = msg.angular.z


# ── ROS 2 publisher: chassis/odom (we publish kinematics) ────────────
def _publish_loop() -> None:
    """Integrate vx / wz into a fake pose, publish at odom_rate_hz."""
    period = 1.0 / max(0.1, _state["odom_rate_hz"])
    last = time.monotonic()
    while not _stop.is_set():
        now = time.monotonic()
        dt = now - last
        last = now

        # Simple unicycle integration. If circle_radius_m is set,
        # auto-spin the robot in a circle even when vx/wz are zero —
        # makes /odom non-trivial for visual sanity-checks.
        if _state["circle_radius_m"] > 0.0 and abs(_state["vx"]) < 1e-6:
            _state["vx"] = 0.2
            _state["wz"] = 0.2 / _state["circle_radius_m"]

        _state["yaw"] += _state["wz"] * dt
        _state["x"]   += _state["vx"] * math.cos(_state["yaw"]) * dt
        _state["y"]   += _state["vx"] * math.sin(_state["yaw"]) * dt

        msg = Odometry()
        msg.header.frame_id = _state["odom_frame"]
        msg.child_frame_id  = _state["base_frame"]
        msg.pose.pose.position.x = _state["x"]
        msg.pose.pose.position.y = _state["y"]
        msg.pose.pose.orientation.z = math.sin(_state["yaw"] / 2.0)
        msg.pose.pose.orientation.w = math.cos(_state["yaw"] / 2.0)
        msg.twist.twist.linear.x  = _state["vx"]
        msg.twist.twist.angular.z = _state["wz"]
        cap.emit("robonix/primitive/chassis/odom", msg)

        _stop.wait(period)


# ── Lifecycle ────────────────────────────────────────────────────────
@cap.on_init
def init(cfg: dict):
    """REGISTERED → INITIALIZED. Read cfg, declare ROS 2 contracts."""
    _state.update({
        k: cfg.get(k, _state[k])
        for k in ("odom_frame", "base_frame", "odom_rate_hz", "circle_radius_m")
    })

    # Subscribe to /cmd_vel (twist_in contract).
    cap.create_subscription(
        contract_id="robonix/primitive/chassis/twist_in",
        topic="/cmd_vel",
        msg_type=Twist,
        callback=_on_twist,
        qos="reliable",
    )

    # Publisher for /odom (odom contract). create_publisher also
    # auto-declares the contract on atlas, so consumers can find us.
    cap.create_publisher(
        contract_id="robonix/primitive/chassis/odom",
        topic="/odom",
        msg_type=Odometry,
        qos="best_effort",
    )

    log.info("init ok: odom_rate=%.1f Hz circle_r=%.2f m",
             _state["odom_rate_hz"], _state["circle_radius_m"])
    return Ok()


@cap.on_activate
def activate():
    """INITIALIZED → RUNNABLE. Start the odom publish thread."""
    global _pub_thread
    _stop.clear()
    _pub_thread = threading.Thread(target=_publish_loop,
                                   name="mock_chassis-odom",
                                   daemon=True)
    _pub_thread.start()
    return Ok()


@cap.on_shutdown
def shutdown():
    _stop.set()


def main() -> int:
    cap.run()
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
