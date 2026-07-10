#!/usr/bin/env bash
# MINXG Rust build — Termux-friendly fallback.
# If cargo gets blocked by sandbox, build with rustc directly.

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUST="$ROOT/rust_core"
OUT="$RUST/dist"

mkdir -p "$OUT"

# Try cargo first (preferred)
if cd "$RUST" && cargo build --release 2>&1; then
    cp "$RUST/target/release/libminxg_rust.so" "$OUT/" 2>/dev/null || true
    cp "$RUST/target/release/libminxg_rust.dylib" "$OUT/" 2>/dev/null || true
    echo "Cargo build OK"
    ls -la "$OUT"
    exit 0
fi

echo "Cargo failed — trying manual rustc build..."

# Manual rustc approach: compile each source file individually
# This avoids cargo's build-script-execution restriction
SOURCES=(
    "$RUST/src/lib.rs"
    "$RUST/src/ga.rs"
    "$RUST/src/driver.rs"
    "$RUST/src/chaos.rs"
    "$RUST/src/fiber.rs"
    "$RUST/src/symbdiff.rs"
    "$RUST/src/mempool.rs"
    "$RUST/src/ffi.rs"
)

cd "$RUST"
rustc --edition 2021 \
    --crate-type cdylib \
    --crate-name minxg_rust \
    -o "$OUT/libminxg_rust.so" \
    -L /data/data/com.termux/files/usr/lib \
    "${SOURCES[@]}" \
    --cfg 'feature=""' \
    2>&1 | tail -20

if [ -f "$OUT/libminxg_rust.so" ]; then
    echo "Manual rustc build OK"
    ls -la "$OUT"
else
    echo "Build failed"
    exit 1
fi