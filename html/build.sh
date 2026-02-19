#!/bin/bash
# html/build.sh — Assemble the single HTML file
#
# This is a convenience wrapper around build.py.
#
# Usage:
#   ./html/build.sh              # Build (auto-detects Go availability)
#   ./html/build.sh --no-go      # Skip Go WASM
#
# Prerequisites: Rust, wasm-pack (Go optional)

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$SCRIPT_DIR/.."

# Step 1: Build Rust WASM agent (if not already built)
if [ ! -f "$SCRIPT_DIR/pkg/wasm_agent_bg.wasm" ]; then
    echo "Building Rust WASM agent..."
    wasm-pack build "$ROOT/rust/wasm-agent" --target web --out-dir ../../html/pkg
fi

# Step 2: Build Go WASM (if Go is available and --no-go not passed)
GO_ARGS=""
GO_WASM_DIR="$SCRIPT_DIR/go_wasm"
GO_MODULE_DIR="/home/bkrabach/dev/amplifier-module-tool-document-builder-go"

if [[ "$*" == *"--no-go"* ]]; then
    GO_ARGS="--no-go"
elif command -v go &>/dev/null && [ -d "$GO_MODULE_DIR/wasm" ]; then
    echo "Building Go WASM document builder..."
    mkdir -p "$GO_WASM_DIR"
    cd "$GO_MODULE_DIR"
    GOOS=js GOARCH=wasm go build -o "$GO_WASM_DIR/document_builder.wasm" ./wasm/
    cp "$(go env GOROOT)/misc/wasm/wasm_exec.js" "$GO_WASM_DIR/"
    cd "$ROOT"
    GO_ARGS="--go-wasm-dir $GO_WASM_DIR"
    echo "Go WASM built successfully"
else
    echo "Go not available — skipping Go WASM build"
    GO_ARGS="--no-go"
fi

# Step 3: Assemble the HTML file
python3 "$SCRIPT_DIR/build.py" --root "$ROOT" $GO_ARGS
