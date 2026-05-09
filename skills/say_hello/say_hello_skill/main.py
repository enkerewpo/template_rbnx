# SPDX-License-Identifier: MIT
"""say_hello — skill template.

Demonstrates:

  * Skill-kind lifecycle: rbnx boot stops at INACTIVE, executor
    fires CMD_ACTIVATE on first MCP call (sticky thereafter).
    on_activate / on_deactivate are REQUIRED for skills.
  * Owning a custom contract under `capabilities/`: SayHello.srv +
    say_hello.v1.toml + driver.v1.toml. Codegen produces the typed
    Request/Response classes used in @cap.mcp below.
  * Single MCP tool — the LLM dispatches here through pilot when
    `rbnx chat` sees a relevant prompt ("say hello to alice").

Replace the rendering logic with your real skill body. The shape
(declare contract → @cap.on_init → @cap.on_activate / on_deactivate
→ @cap.mcp) is the only thing the framework cares about.
"""
from __future__ import annotations

import logging

from robonix_api import Capability, Ok, Err, Deferred

cap = Capability(id="say_hello", namespace="robonix/skill/say_hello")

# Codegen output: the typed dataclasses derived from
# capabilities/lib/say_hello/srv/SayHello.srv. Available after
# `rbnx codegen --mcp` runs.
from say_hello_mcp import SayHello_Request, SayHello_Response  # noqa: E402

log = logging.getLogger("say_hello")
logging.basicConfig(level=logging.INFO, format="[say_hello] %(levelname)s %(message)s")


# ── module state populated by lifecycle handlers ─────────────────────
_state = {
    "default_style":  "casual",
    "active":         False,
    "greet_count":    0,
}


# ── @cap.mcp: the actual LLM-callable tool ──────────────────────────
# Description for pilot's tool-picker comes from the docstring.
# Pilot uses it verbatim when deciding whether to dispatch this skill.
@cap.mcp("robonix/skill/say_hello/say")
def say(req: SayHello_Request) -> SayHello_Response:
    """Greet a person or thing. The LLM should call this whenever the
    user wants someone to be greeted, with optional style hint
    ("formal", "casual", "pirate"). Empty style defaults to casual."""
    if not _state["active"]:
        return SayHello_Response(greeting="(skill not yet activated)")

    style = (req.style or _state["default_style"]).lower()
    if style == "formal":
        msg = f"Good day, {req.name}. A pleasure to make your acquaintance."
    elif style == "pirate":
        msg = f"Ahoy, {req.name}! Yarrr."
    else:
        msg = f"Hey {req.name}!"

    _state["greet_count"] += 1
    log.info("greeted %s (style=%s, count=%d)",
             req.name, style, _state["greet_count"])
    return SayHello_Response(greeting=msg)


# ── Lifecycle ────────────────────────────────────────────────────────
@cap.on_init
def init(cfg: dict):
    """REGISTERED → INACTIVE. Light: parse config, validate inputs.
    Don't allocate heavy resources — the user might have spawned us
    only to inspect the cap tree, not to actually invoke the tool."""
    style = cfg.get("default_style", _state["default_style"])
    if style not in ("formal", "casual", "pirate"):
        return Err(f"unsupported default_style {style!r}")
    _state["default_style"] = style
    log.info("init ok: default_style=%s", style)
    return Ok()


@cap.on_activate
def activate():
    """INACTIVE → ACTIVE. Heavy: this is where a real skill
    loads models, opens hardware, starts background threads.
    Triggered by the executor lazily on first MCP call."""
    _state["active"] = True
    _state["greet_count"] = 0
    log.info("activated — ready to greet")
    return Ok()


@cap.on_deactivate
def deactivate():
    """ACTIVE → INACTIVE. Drop heavy state but stay registered;
    a follow-up MCP call will re-activate. Executor's eviction policy
    fires this on idle."""
    log.info("deactivating after %d greetings", _state["greet_count"])
    _state["active"] = False
    return Ok()


@cap.on_shutdown
def shutdown():
    """any → TERMINATED. Last-chance cleanup: flush logs, persist
    state, etc."""
    log.info("shutdown (lifetime greetings=%d)", _state["greet_count"])


def main() -> int:
    cap.run()
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
