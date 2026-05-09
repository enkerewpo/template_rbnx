# template_rbnx — Robonix deploy template

Minimum viable Robonix deploy that boots end-to-end on a desktop
without any robotic hardware or simulator. Clone, build, boot, chat.

Contains one of each package kind so you can see the full pattern:

| Layer       | Package          | What it shows |
|-------------|------------------|---|
| `primitive` | `mock_chassis`   | Docker-packaged ROS 2 driver. Publishes fake `/odom`, accepts `/cmd_vel`. Declares the built-in `robonix/primitive/chassis/*` contracts. |
| `service`   | `my_navigate`    | Native Python. `on_init` finds chassis via `cap.find_one + cap.connect`, declares own MCP tools (`navigate / status / cancel` from built-in `robonix/service/navigation/*`). Stub planner — replace with A* / Pure Pursuit / nav2. |
| `skill`     | `say_hello`      | Native Python. **Owns its own contract** under `capabilities/` (IDL + toml). Single MCP tool the LLM dispatches via `rbnx chat`. |

System services (atlas / executor / pilot / liaison) ship with
robonix-cli — `rbnx boot` spawns them automatically.

## Prerequisites

- robonix toolchain installed: `cargo install` from the
  [`robonix`](https://github.com/syswonder/robonix) repo's `rust/`
  workspace (or `make install`), and `rbnx setup <robonix_root>` once
  so `rbnx path robonix-api` resolves.
- Python 3.10+ with `grpcio-tools` and `mcp[fastmcp]` available.
- Docker (for the primitive's container).
- A VLM endpoint reachable by pilot. Any OpenAI-compatible API works.

## Quick start

```bash
git clone https://github.com/enkerewpo/template_rbnx.git
cd template_rbnx

# Build all 3 packages (codegen + docker image for the primitive).
rbnx build

# Bring up the whole stack. VLM creds can be in your shell rc or
# inlined on the command:
VLM_API_KEY=sk-...  VLM_BASE_URL=https://api.openai.com/v1  VLM_MODEL=gpt-4o-mini  rbnx boot
```

In another terminal:

```bash
rbnx caps           # list registered caps + their state
rbnx chat           # talk to pilot — try "say hello to alice"
```

`rbnx chat` should pick up the `say_hello` skill and route your
prompt through it.

## Layout

```
template_rbnx/
├── robonix_manifest.yaml           # deploy: which packages + their config
├── primitives/
│   └── mock_chassis/
│       ├── package_manifest.yaml
│       ├── scripts/{build,start}.sh
│       ├── docker/{Dockerfile,entrypoint.sh}
│       └── mock_chassis/main.py
├── services/
│   └── my_navigate/
│       ├── package_manifest.yaml
│       ├── scripts/{build,start}.sh
│       └── my_navigate/main.py
└── skills/
    └── say_hello/
        ├── package_manifest.yaml
        ├── scripts/{build,start}.sh
        ├── capabilities/
        │   ├── lib/say_hello/srv/SayHello.srv
        │   ├── say_hello.v1.toml
        │   └── driver.v1.toml
        └── say_hello_skill/main.py
```

## Customizing

- **Replace `mock_chassis`** with your real driver: keep the same
  contract IDs (`robonix/primitive/chassis/{driver,move,twist_in,odom}`),
  swap the `main.py` body. Service consumers don't need to change.
- **Replace `my_navigate`'s planner**: search for `TODO(planner)` in
  `main.py`. The skeleton already wires init / dependency resolution
  / MCP tools — just fill the body.
- **Add a new skill**: copy `skills/say_hello/`, change the contract
  IDs under `capabilities/`, append to `robonix_manifest.yaml`.

## What gets bound to atlas

After `rbnx boot`:

| Cap            | Kind      | Contracts (over)                             |
|----------------|-----------|-----------------------------------------------|
| `mock_chassis` | primitive | `chassis/driver` (grpc), `chassis/twist_in` (ros2), `chassis/odom` (ros2), `chassis/move` (grpc) |
| `my_navigate`  | service   | `navigation/driver` (grpc), `navigation/navigate` (mcp), `navigation/status` (mcp), `navigation/cancel` (mcp) |
| `say_hello`    | skill     | `say_hello/driver` (grpc), `say_hello/say` (mcp) |

`rbnx caps -v` after boot prints this same table from the live registry.
