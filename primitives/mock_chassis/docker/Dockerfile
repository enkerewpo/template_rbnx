# Minimum ROS 2 base for a robonix primitive. Add system packages /
# extra Python deps here as your driver grows. The package source is
# bind-mounted at /pkg by scripts/start.sh, so we don't COPY it.
FROM ros:humble-ros-base

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
