# Dockerfile — MINXG v0.18.3
#
# Multi-stage build: Rust core → Python runtime → slim production image.
# Heavily inspired by hermes-agent/Dockerfile but adapted for Termux-native
# build path and Android cross-compilation awareness.
#
# Stages:
#   1. rust-builder   — compile rust_core/ → libminxg_rust_core.so
#   2. python-runner  — install Python deps + copy .so
#   3. minxg-final    — squash into minimal runtime (< 80 MB)
#
# Architecture: arm64 only for Termux/Android; x86_64 for CI/test.
# Build:  docker build -t minxg:0.18.3 -t minxg:latest .
# Run:    docker run -p 8080:8080 -v ./data:/data minxg:0.18.3

# ── Stage 1: Rust builder ────────────────────────────────────────
FROM rust:1.85-slim-bookworm AS rust-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    pkg-config libssl-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY rust_core/ rust_core/
COPY Cargo.lock Cargo.toml ./

RUN cd rust_core && cargo build --release \
 && strip target/release/libminxg_rust_core.so

# ── Stage 2: Python runner ───────────────────────────────────────
FROM python:3.11-slim-bookworm AS python-runner

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY minxg/ minxg/
COPY multiligua_cli/ multiligua_cli/
COPY multiling/ multiling/
COPY tools/ tools/
COPY tests/ tests/  # for health check
COPY pyproject.toml README.md ./

# Copy Rust .so from stage 1
COPY --from=rust-builder /build/rust_core/target/release/libminxg_rust_core.so /app/rust_core/target/release/

# Create data directory
RUN mkdir -p /data && chmod 777 /data

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "from minxg import VERSION; print(VERSION)" || exit 1

# Gateway port
EXPOSE 8080

ENV MINXG_DATA_DIR=/data
ENV MINXG_PROFILE=container
ENV PYTHONUNBUFFERED=1

# ── Entry point ─
# Users can override CMD to run gateway / chat / setup
ENTRYPOINT ["python", "-m", "multiligua_cli.main"]
CMD ["gateway", "--host", "0.0.0.0", "--port", "8080"]

# ── Labels ────────────────────────────────────────────────────────
LABEL org.opencontainers.image.title="MINXG"
LABEL org.opencontainers.image.description="Multi-language AI agent platform with Rust/C++/R/Julia/Datalog/Wasm/Go cores"
LABEL org.opencontainers.image.version="0.18.3"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.source="https://github.com/user/minxg"