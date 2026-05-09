# Minimum ROS 2 base for a robonix primitive. Add system packages /
# extra Python deps here as your driver grows. The package source is
# bind-mounted at /pkg by scripts/start.sh, so we don't COPY it.
FROM ros:humble-ros-base

# ── TUNA mirrors for GFW-bound networks ─────────────────────────────
# Swap apt + pip + HuggingFace to mirrors.tuna.tsinghua.edu.cn (apt /
# pypi) and hf-mirror.com (HF). Touched once here so every robonix
# Dockerfile is build-able from China. Drop these RUN/ENV lines if
# the build host already has direct access (they're idempotent).
RUN set -eux; \
    if [ -f /etc/apt/sources.list.d/ros2.list ]; then \
        sed -i 's|http://packages.ros.org/ros2/ubuntu|https://mirrors.tuna.tsinghua.edu.cn/ros2/ubuntu|g' \
            /etc/apt/sources.list.d/ros2.list; \
    fi; \
    if [ -f /etc/apt/sources.list ]; then \
        sed -i \
            -e 's|http://archive.ubuntu.com/ubuntu/\?|https://mirrors.tuna.tsinghua.edu.cn/ubuntu/|g' \
            -e 's|http://security.ubuntu.com/ubuntu/\?|https://mirrors.tuna.tsinghua.edu.cn/ubuntu/|g' \
            -e 's|http://ports.ubuntu.com/ubuntu-ports/\?|https://mirrors.tuna.tsinghua.edu.cn/ubuntu-ports/|g' \
            /etc/apt/sources.list; \
    fi
ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    HF_ENDPOINT=https://hf-mirror.com

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3-pip python3-venv \
 && rm -rf /var/lib/apt/lists/*

# robonix Python deps. Pinned conservatively; bump as your cap grows.
RUN pip3 install --no-cache-dir \
      "grpcio>=1.60" \
      "grpcio-tools>=1.60" \
      "protobuf>=4.25" \
      "fastmcp>=3" \
      "mcp>=1.0" \
      "PyYAML"

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
